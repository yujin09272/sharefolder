import streamlit as st
import pandas as pd
import numpy as np
import datetime
import requests
import folium
from streamlit_folium import st_folium
import os
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# --- 경고(Warning) 제거 옵션 ---
pd.set_option('future.no_silent_downcasting', True)

# --- 핵심 설정 ---
API_KEY = "테스트본"
KST = datetime.timezone(datetime.timedelta(hours=9))
DATA_FILE_NAME = "소방청_구조활동현황_20241231.csv"  # 👉 유진님의 실제 CSV 파일명

# ==========================================
# 1. 세션 상태(Session State) 초기화
# ==========================================
if 'residents' not in st.session_state:
    st.session_state.residents = [
        {"이름": "김노인 (노인회장)", "연락처": "010-1111-2222"},
        {"이름": "박청년 (청년회장)", "연락처": "010-3333-4444"}
    ]

if 'editing_index' not in st.session_state:
    st.session_state.editing_index = None

ANIMAL_WARNING_DB = {
    3: {"동물": "멧돼지", "경고": "봄철 번식기로 예민한 시기입니다.", "대처": "우산이나 막대기를 펴서 몸을 크게 보이게 하고, 등을 보이며 뛰지 마세요."},
    4: {"동물": "멧돼지", "경고": "봄철 번식기로 예민한 시기입니다.", "대처": "우산이나 막대기를 펴서 몸을 크게 보이게 하고, 등을 보이며 뛰지 마세요."},
    5: {"동물": "뱀", "경고": "날씨가 따뜻해지며 뱀 활동이 시작됩니다.", "대처": "밭일 하실 때 반드시 두꺼운 장화와 긴 바지를 착용하세요."},
    6: {"동물": "뱀", "경고": "여름철 독사 활동이 왕성해집니다.", "대처": "풀숲을 지날 때는 지팡이로 먼저 풀을 헤치며 걸으세요."},
    7: {"동물": "뱀", "경고": "장마철 습한 곳에 뱀이 자주 출몰합니다.", "대처": "집 주변 돌무더기나 잡초를 제거하시고, 물린 경우 뛰지 말고 즉시 119에 신고하세요."},
    8: {"동물": "말벌", "경고": "여름~가을철 벌초 시기 말벌 쏘임 사고 급증!", "대처": "어두운 색 옷을 피하고, 단 냄새가 나는 음료를 곁에 두지 마세요."},
    9: {"동물": "말벌/진드기", "경고": "말벌 독성이 가장 강하고, 가을철 진드기 위험이 높습니다.", "대처": "벌초 시 챙이 넓은 모자를 쓰고, 작업 후에는 옷을 털고 꼭 샤워하세요."},
    10: {"동물": "진드기/멧돼지", "경고": "가을철 수확기 멧돼지 출몰 및 진드기 감염 주의", "대처": "풀밭에 겉옷을 벗어두거나 눕지 마세요."},
    11: {"동물": "야생동물 주의", "경고": "겨울을 앞두고 먹이 활동이 활발합니다.", "대처": "산 인접 밭에 음식물 쓰레기를 방치하지 마세요."},
}

# ==========================================
# 2. 데이터 수집 및 분석 엔진
# ==========================================
@st.cache_data(ttl=300)
def fetch_current_weather(auth_key, stn_id):
    now = datetime.datetime.now(KST)
    for hrs_ago in range(1, 4):
        tm_str = (now - datetime.timedelta(hours=hrs_ago)).strftime("%Y%m%d%H00")
        url = f"https://apihub-pub.kma.go.kr/api/typ01/url/awsh.php?tm={tm_str}&stn={stn_id}&help=1&authKey={auth_key}"
        try:
            resp = requests.get(url, timeout=15)
            text = resp.content.decode('euc-kr', errors='replace')
            if "AUTH_ERR" in text.upper() or "인증" in text: return None, None, f"인증키 오류: {text[:80]}"
            
            lines = text.split('\n')
            stn_idx = ta_idx = rn_idx = -1
            for line in lines:
                line = line.strip()
                if not line: continue
                if line.startswith('#'):
                    parts = line.replace('#', '').split()
                    if 'STN' in parts: stn_idx = parts.index('STN')
                    if 'TA' in parts: ta_idx = parts.index('TA')
                    if 'RN_DAY' in parts: rn_idx = parts.index('RN_DAY')
                    continue 
                if stn_idx != -1:
                    parts = line.split()
                    if len(parts) > max(stn_idx, ta_idx):
                        try:
                            ta = float(parts[ta_idx]) if parts[ta_idx] not in ['-99.0', '-99.9', '-99', '-9'] else np.nan
                            rn = float(parts[rn_idx]) if rn_idx != -1 and parts[rn_idx] not in ['-99.0', '-99.9', '-99', '-9'] else 0.0
                            return ta, rn, "정상"
                        except: pass
        except Exception as e: pass
    return None, None, "통신 지연"

def analyze_risks(temp, rain, month):
    weather_warn, forest_warn = [], []
    if temp is not None:
        if temp >= 33.0: weather_warn.append("폭염 🥵|한낮 야외 농사일을 멈추고 시원한 곳에서 휴식을 취하세요.")
        elif temp <= -12.0: weather_warn.append("한파 🥶|외출을 삼가고 수도관 동파에 주의하세요.")
    if rain is not None and rain >= 50.0:
        weather_warn.append(f"폭우 🌧️|오늘 비가 많이 왔습니다({rain}mm). 하천 주변 접근을 피하세요.")
    if not weather_warn and temp is not None:
        weather_warn.append(f"날씨 양호 ☀️|현재 기온 {temp}°C. 농사일 하시기 무난한 날씨입니다.")

    if month in [3, 4, 5, 11, 12] and rain is not None and rain < 2.0:
        forest_warn.append("산불 조심 🔥|비가 무척 건조합니다. 산림 인접지에서 쓰레기 소각을 절대 금지합니다.")
    elif rain is not None and rain >= 80.0:
        forest_warn.append("산사태 주의 ⚠️|지반이 약해졌습니다. 산비탈이나 급경사지 주변 거주 어르신은 마을회관으로 대피하세요.")
    else:
        forest_warn.append("산림 안전 🌲|현재 특별한 산불/산사태 위험 요소가 없습니다.")

    return weather_warn, forest_warn

# --- 👉 엑셀(CSV) 8만건 데이터 로드 및 3단계 리턴 엔진 ---
@st.cache_data(ttl=3600, show_spinner=False)
def load_and_process_data(file_path):
    # 빈 데이터프레임 3개를 리턴해야 에러가 안 남 (원본, 필터링, 지도용)
    if not os.path.exists(file_path):
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "FILE_NOT_FOUND"

    try:
        # 1. 원본 8만건 통째로 읽어오기 (3번째 탭 표시용)
        try:
            raw_df = pd.read_csv(file_path, encoding='cp949', low_memory=False)
        except:
            try:
                raw_df = pd.read_csv(file_path, encoding='euc-kr', low_memory=False)
            except:
                raw_df = pd.read_csv(file_path, encoding='utf-8', low_memory=False)
        
        # 분석을 위한 복사본
        df = raw_df.copy()
        df.columns = df.columns.str.strip().str.replace('\n', '').str.replace('\r', '')
        actual_cols = list(df.columns)
        
        # 2. 필수 컬럼 유연하게 찾기
        date_col = next((c for c in actual_cols if '년월일' in c or '일자' in c), None)
        si_col = next((c for c in actual_cols if '시도' in c or '발생장소_시' in c or c == '시'), None)
        gu_col = next((c for c in actual_cols if '시군구' in c or '발생장소_구' in c or c == '구'), None)
        dong_col = next((c for c in actual_cols if '읍면동' in c or '발생장소_동' in c or c == '동'), None)
        
        cause_col1 = next((c for c in actual_cols if '사고원인' in c and '코드' not in c), None)
        cause_col2 = next((c for c in actual_cols if '사고원인코드명' in c), None)
        
        if not cause_col1:
            return raw_df, pd.DataFrame(), pd.DataFrame(), f"사고원인 컬럼 없음 (현재: {actual_cols})"

        # 3. '벌/동물'만 필터링 
        search_series = df[cause_col1].astype(str)
        if cause_col2:
            search_series += " " + df[cause_col2].astype(str)
            
        mask = search_series.str.contains('벌|동물', regex=True, na=False)
        filtered_df = df[mask].copy()

        if filtered_df.empty:
            return raw_df, pd.DataFrame(), pd.DataFrame(), "NO_MATCHING_DATA"

        # 4. 전체 주소 및 상세정보 결합
        if cause_col2:
            filtered_df['사고상세'] = filtered_df[cause_col1].astype(str) + " - " + filtered_df[cause_col2].astype(str)
        else:
            filtered_df['사고상세'] = filtered_df[cause_col1].astype(str)

        def make_addr(row):
            parts = []
            if si_col and pd.notna(row[si_col]): parts.append(str(row[si_col]).strip())
            if gu_col and pd.notna(row[gu_col]): parts.append(str(row[gu_col]).strip())
            if dong_col and pd.notna(row[dong_col]): parts.append(str(row[dong_col]).strip())
            return " ".join(parts)
            
        filtered_df['전체주소'] = filtered_df.apply(make_addr, axis=1)

        def assign_type(text):
            text = str(text)
            if '벌' in text: return '벌집제거'
            elif '동물' in text: return '동물처리'
            return '기타'
        filtered_df['출동유형'] = search_series[mask].apply(assign_type)
        
        if date_col:
            filtered_df['출동일자'] = filtered_df[date_col].astype(str).str.split(' ').str[0]
        else:
            filtered_df['출동일자'] = "날짜 기록 없음"

        # 화면 표시에 쓰일 깔끔한 데이터프레임
        display_df = filtered_df[['출동일자', '출동유형', '전체주소', '사고상세']].copy()

        # ========================================================
        # 👉 5. 속도 개선 및 지도용: '영주시' 데이터만 추출
        # ========================================================
        yeongju_mask = filtered_df['전체주소'].str.contains('영주', na=False)
        map_df = filtered_df[yeongju_mask].drop_duplicates(subset=['전체주소', '출동유형']).copy()

        # 6. 영주시 데이터만 지오코딩
        lat_list, lng_list, acc_list = [], [], []
        yeongju_center_lat, yeongju_center_lng = 36.8056, 128.6240
        
        if not map_df.empty:
            geolocator = Nominatim(user_agent="yujin_dashboard_veryfast")
            unique_addrs = map_df['전체주소'].unique()
            addr_dict = {}
            
            for addr in unique_addrs:
                if not addr.strip(): continue
                clean_addr = addr.replace("경상북도", "경북")
                try:
                    loc = geolocator.geocode(f"대한민국 {clean_addr}", timeout=3)
                    if loc:
                        addr_dict[addr] = (loc.latitude, loc.longitude, "정상 매핑")
                except:
                    pass
                time.sleep(0.1)

            for idx, row in map_df.iterrows():
                addr = row['전체주소']
                if addr in addr_dict:
                    base_lat, base_lng, acc_str = addr_dict[addr]
                    lat_list.append(base_lat + np.random.uniform(-0.01, 0.01))
                    lng_list.append(base_lng + np.random.uniform(-0.01, 0.01))
                    acc_list.append(acc_str)
                else:
                    lat_list.append(yeongju_center_lat + np.random.uniform(-0.05, 0.05))
                    lng_list.append(yeongju_center_lng + np.random.uniform(-0.05, 0.05))
                    acc_list.append("영주 임의 표시")

            map_df['lat'] = lat_list
            map_df['lng'] = lng_list
            map_df['위치정확도'] = acc_list

        return raw_df, display_df, map_df, "SUCCESS"

    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), f"ERROR: {e}"

# ==========================================
# 4. 메인 화면 UI 구성
# ==========================================
st.set_page_config(page_title="어르신 안전 마을 방송국", layout="wide", page_icon="📢")

# 💡 강제 새로고침 버튼 
if st.button("🧹 화면이 옛날 코드 그대로일 때 클릭 (캐시 강제 초기화)", type="primary"):
    st.cache_data.clear()
    st.rerun()

st.title("📢 시골 마을 종합 안전 관제 대시보드")
st.markdown("실시간 기상 관측, 119 출동 데이터 연동 및 원클릭 마을 방송 시스템입니다.")

with st.container():
    st.markdown("### 📍 관제 지역 설정")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: village_name = st.text_input("마을 이름", "영주시")
    with col2: stn_id = st.number_input("기상청 AWS 지점번호", value=272, step=1)
    with col3: 
        st.write("")
        st.write("")
        update_btn = st.button("🔄 실시간 데이터 최신화", use_container_width=True)

current_month = datetime.datetime.now(KST).month

temp, rain, err_msg = fetch_current_weather(API_KEY, stn_id)
weather_warns, forest_warns = analyze_risks(temp, rain, current_month)
animal_alert = ANIMAL_WARNING_DB.get(current_month, {"동물": "해당없음", "경고": "특별히 주의할 야생동물이 없는 시기입니다.", "대처": "평소와 같이 안전에 유의하세요."})

# 👉 데이터 로딩 (스피너 표시)
with st.spinner('📂 엑셀 데이터를 불러오는 중입니다...'):
    raw_df, all_display_df, yeongju_map_df, status_msg = load_and_process_data(DATA_FILE_NAME)

st.markdown("---")

# 💡 탭을 3개로 늘렸습니다! 엑셀 확인용 탭 추가
tab1, tab2, tab3 = st.tabs(["🗺️ 마을 관제 지도 & 실시간 경보", "✉️ 마을 방송 / 주민 문자 발송", "📊 엑셀 전체 데이터 보기"])

# ---------------------------------------------------------
# [탭 1] 마을 관제 지도
# ---------------------------------------------------------
with tab1:
    map_col, data_col = st.columns([1.5, 1])
    
    with map_col:
        st.markdown(f"#### 📍 {village_name} 위험 생물 119 출동 관제 지도")
        
        if status_msg == "SUCCESS":
            st.success(f"✅ 영주시 관련 데이터 {len(yeongju_map_df)}건을 지도에 띄웠습니다.")
        elif status_msg == "FILE_NOT_FOUND":
            st.error(f"🔴 '{DATA_FILE_NAME}' 파일이 없습니다.")
        else:
            st.warning(f"🟡 지도 데이터 분석 실패: {status_msg}")
            
        st.caption("💡 원 위에 **마우스를 올리거나(Hover)** 클릭하면 출동 상세 정보가 뜹니다.")
        
        center_lat, center_lng = 36.8056, 128.6240 # 영주시 중심
        m = folium.Map(location=[center_lat, center_lng], zoom_start=11)
        
        folium.Marker(
            [center_lat, center_lng], 
            tooltip=f"{village_name} 중심", 
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)
        
        # 영주시 지도 데이터 그리기
        if not yeongju_map_df.empty:
            for idx, row in yeongju_map_df.iterrows():
                alert_color = "orange" if row['출동유형'] == '벌집제거' else "darkred"
                hover_info = f"🚨 {row['출동유형']} | 📅 {row['출동일자']} | 📍 {row['전체주소']} | 원인: {row['사고상세']}"
                
                popup_html = f"""
                <div style="font-family: sans-serif; min-width: 250px;">
                    <h4 style="margin-bottom: 5px; color: {alert_color};">🚨 119 출동: {row['출동유형']}</h4>
                    <p style="margin-top: 0; margin-bottom: 5px;"><b>📅 발생일자:</b> {row['출동일자']}</p>
                    <p style="margin-top: 0; margin-bottom: 5px;"><b>📍 지역:</b> {row['전체주소']}</p>
                    <p style="margin-top: 0; margin-bottom: 5px;"><b>🔍 사고상세:</b> {row['사고상세']}</p>
                </div>
                """
                folium.Circle(
                    location=[row['lat'], row['lng']],
                    radius=600, 
                    tooltip=hover_info, 
                    popup=folium.Popup(popup_html, max_width=350), 
                    color=alert_color, fill=True, fill_color=alert_color,
                    fill_opacity=0.5, border_width=1,
                ).add_to(m)
            
        st_folium(m, width="100%", height=450, returned_objects=[])

    with data_col:
        st.markdown(f"#### 🌡️ 실시간 관측 데이터 ({village_name})")
        if temp is not None:
            st.success(f"**현재 기온:** {temp} °C  |  **일 누적 강수량:** {rain} mm")
        else:
            st.error(f"기상 데이터 수신 실패: {err_msg}")
            
        for w in weather_warns:
            title, desc = w.split('|')
            if "양호" in title: st.info(f"**[{title}]** {desc}")
            else: st.error(f"**[{title}]** {desc}")
            
        for f in forest_warns:
            title, desc = f.split('|')
            if "안전" in title: st.info(f"**[{title}]** {desc}")
            else: st.warning(f"**[{title}]** {desc}")

# ---------------------------------------------------------
# [탭 2] 마을 방송 및 주민 문자 발송 시스템
# ---------------------------------------------------------
with tab2:
    st.markdown("### 📱 원클릭 마을 긴급 방송 및 스마트 문자 시스템")
    col_broadcast, col_sms = st.columns(2)
    
    with col_broadcast:
        st.markdown("#### 🎙️ 스마트 마을 스피커 방송")
        animal_names = ["말벌/벌집", "멧돼지", "뱀/살모사", "들개"]
        selected_animal = st.selectbox("방송할 위험 생물 선택:", animal_names, key="broadcast_select")
        
        if st.button("📢 즉시 마을 방송 송출하기", use_container_width=True, type="primary"):
            st.toast(f"🎙️ 아아, 이장입니다! 우리 마을 인근에 '{selected_animal}' 출몰이 확인되었습니다!", icon="🚨")
            st.success(f"✅ '{selected_animal}' 경고 안내 방송이 마을 스피커로 송출되었습니다.")

    with col_sms:
        st.markdown("#### ✉️ 어르신 맞춤형 SMS 전파")
        
        with st.expander("👥 마을 주민 연락처 관리 (추가/수정/삭제)", expanded=True):
            form_title = "➕ 새로운 주민 연락처 추가"
            button_text = "추가"
            default_name, default_phone = "", "010-"
            
            if st.session_state.editing_index is not None:
                form_title = "✏️ 주민 연락처 수정"
                button_text = "수정 완료"
                edit_data = st.session_state.residents[st.session_state.editing_index]
                default_name, default_phone = edit_data["이름"], edit_data["연락처"]

            with st.form("add_resident_form", clear_on_submit=True):
                st.write(f"**{form_title}**")
                c1, c2, c3 = st.columns([1, 1.5, 0.8])
                new_name = c1.text_input("이름", value=default_name, placeholder="홍길동")
                new_phone = c2.text_input("연락처", value=default_phone, placeholder="010-1234-5678")
                submitted = c3.form_submit_button(button_text, use_container_width=True)
                
                if submitted:
                    if new_name and new_phone:
                        if st.session_state.editing_index is not None:
                            st.session_state.residents[st.session_state.editing_index] = {"이름": new_name, "연락처": new_phone}
                            st.session_state.editing_index = None
                            st.toast(f"'{new_name}' 어르신 연락처 수정 완료.", icon="✏️")
                        else:
                            st.session_state.residents.append({"이름": new_name, "연락처": new_phone})
                            st.toast(f"'{new_name}' 어르신 추가 완료.", icon="➕")
                        st.rerun()
                    else:
                        st.error("이름과 연락처를 모두 입력해주세요.")
            
            if st.session_state.editing_index is not None:
                if st.button("❌ 수정 취소", use_container_width=True):
                    st.session_state.editing_index = None
                    st.rerun()

            st.write("---")
            st.write(f"**👥 현재 등록된 주민 목록 (총 {len(st.session_state.residents)}명)**")
            if st.session_state.residents:
                for i, resident in enumerate(st.session_state.residents):
                    r_col1, r_col2, r_col3, r_col4 = st.columns([1, 1.5, 0.5, 0.5])
                    r_col1.write(f"**{resident['이름']}**")
                    r_col2.write(f"{resident['연락처']}")
                    
                    if r_col3.button("✏️", key=f"edit_{i}"):
                        st.session_state.editing_index = i
                        st.rerun()
                        
                    if r_col4.button("🗑️", key=f"del_{i}"):
                        st.session_state.residents.pop(i)
                        st.toast(f"'{resident['이름']}' 어르신 삭제 완료.", icon="🗑️")
                        st.rerun()
            else:
                st.info("현재 등록된 연락처가 없습니다.")

        st.markdown("---")
        st.markdown("##### 📝 발송될 문자 내용")
        
        auto_sms = f"[{village_name} 안전알림]\n어르신들, 이장입니다.\n\n"
        for w in weather_warns:
            if "양호" not in w: auto_sms += f"👉 {w.split('|')[1]}\n"
        for f in forest_warns:
            if "안전" not in f: auto_sms += f"👉 {f.split('|')[1]}\n"
        if animal_alert["동물"] != "해당없음":
            auto_sms += f"👉 {animal_alert['대처']}\n"
            
        auto_sms += f"👉 최근 119 출동 데이터에 따라 인근 '{selected_animal}' 주의바랍니다.\n\n항상 건강 조심하십시오."

        sms_content = st.text_area("내용 확인 및 수정", auto_sms, height=180, label_visibility="collapsed", key="sms_area")
        
        if st.button("🚀 주소록에 등록된 전체 주민에게 문자 발송", use_container_width=True, type="primary", key="sms_send_btn"):
            if not st.session_state.residents:
                st.warning("⚠️ 연락처 관리에 주민을 먼저 등록해주세요.")
            else:
                st.balloons()
                st.success(f"✅ 총 **{len(st.session_state.residents)}명**의 어르신들에게 안내 문자가 발송되었습니다!")

# ---------------------------------------------------------
# 👉 [탭 3] 새롭게 추가된 '엑셀 전체 데이터 보기' 공간
# ---------------------------------------------------------
with tab3:
    st.markdown("### 📊 엑셀 원본 데이터 확인")
    st.write("파이썬 코드가 엑셀 파일을 정상적으로 읽어왔는지 확인하는 곳입니다.")
    
    if not raw_df.empty:
        st.success(f"✅ 엑셀 파일에서 총 **{len(raw_df):,}건**의 전체 데이터를 성공적으로 읽어왔습니다!")
        st.dataframe(raw_df, use_container_width=True, height=250)
    elif status_msg == "FILE_NOT_FOUND":
        st.error(f"🔴 '{DATA_FILE_NAME}' 파일을 찾을 수 없습니다. 파일명이나 위치를 확인해주세요.")
    else:
        st.error(f"🔴 데이터 불러오기 에러: {status_msg}")

    st.markdown("---")
    st.markdown("### 🐝 '벌' 및 '동물' 관련 추출 데이터")
    st.write("원본 데이터 중 벌/동물 관련 사고만 추려낸 결과입니다.")
    
    if not all_display_df.empty:
        st.info(f"🔍 벌/동물 관련 사고 총 **{len(all_display_df):,}건**이 추출되었습니다.")
        st.dataframe(all_display_df, use_container_width=True, height=300, hide_index=True)
    else:
        st.warning("벌/동물 관련 사고 내역이 없습니다.")
