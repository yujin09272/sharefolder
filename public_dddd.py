import streamlit as st
import pandas as pd
import numpy as np
import datetime
import requests
import folium
from streamlit_folium import st_folium

# --- 경고(Warning) 제거 옵션 ---
pd.set_option('future.no_silent_downcasting', True)

# --- 핵심 설정: API 키 ---
API_KEY = "테스트본"
KST = datetime.timezone(datetime.timedelta(hours=9))

# ==========================================
# 1. 세션 상태(Session State) 초기화 (데이터 유지)
# ==========================================
# 주민 연락처 저장소
if 'residents' not in st.session_state:
    st.session_state.residents = [
        {"이름": "김노인 (노인회장)", "연락처": "010-1111-2222"},
        {"이름": "박청년 (청년회장)", "연락처": "010-3333-4444"}
    ]

# 현재 수정 중인 주민의 인덱스 저장 (None이면 수정 중 아님)
if 'editing_index' not in st.session_state:
    st.session_state.editing_index = None

# ==========================================
# 2. 통합 데이터 (야생동물 DB 및 최근 출몰 데이터)
# ==========================================
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

# 최근 출몰 데이터 (위치는 범위 표시를 위해 대략적인 지점 사용)
species_data = [
    {
        "name": "살모사", 
        "status": "최근 목격", 
        "color": "red",
        "lat": 37.3455, "lng": 127.9250, # 출몰 중심점
        "radius": 150, # 👉 대략적인 범위 (미터 단위 원 반지름)
        "details": "- 피해: 치명적 맹독 보유\n- 대처: 긴 바지/장화 착용, 발견 시 우회"
    },
    {
        "name": "등검은말벌", 
        "status": "신규 출현", 
        "color": "orange",
        "lat": 37.3380, "lng": 127.9150,
        "radius": 200, # 👉 대략적인 범위
        "details": "- 피해: 양봉 농가 피해, 쏘임 주의\n- 대처: 머리 감싸고 빠르게 20m 이상 이탈"
    },
    {
        "name": "멧돼지", 
        "status": "경로 이탈 탐지", 
        "color": "darkred",
        "lat": 37.3470, "lng": 127.9100,
        "radius": 300, # 👉 대략적인 범위
        "details": "- 피해: 농작물 피해, 야간 출몰 주의\n- 대처: 소리 지르지 말고 바위/나무 뒤로 대피"
    }
]

# ==========================================
# 3. 데이터 수집 및 분석 엔진
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
        forest_warn.append("산불 조심 🔥|비가 오지 않아 산이 매우 건조합니다. 산림 인접지에서 쓰레기 소각을 절대 금지합니다.")
    elif rain is not None and rain >= 80.0:
        forest_warn.append("산사태 주의 ⚠️|지반이 약해졌습니다. 산비탈이나 급경사지 주변 거주 어르신은 마을회관으로 대피하세요.")
    else:
        forest_warn.append("산림 안전 🌲|현재 특별한 산불/산사태 위험 요소가 없습니다.")

    return weather_warn, forest_warn


# ==========================================
# 4. 메인 화면 UI 구성 (Streamlit 웹 레이아웃)
# ==========================================
st.set_page_config(page_title="어르신 안전 마을 방송국", layout="wide", page_icon="📢")

st.title("📢 시골 마을 종합 안전 관제 대시보드")
st.markdown("실시간 기상 관측, 생태 위험 데이터 연동 및 원클릭 마을 방송/문자 전파 시스템입니다.")

with st.container():
    st.markdown("### 📍 관제 지역 설정")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: village_name = st.text_input("마을 이름", "원주시 호저면")
    with col2: stn_id = st.number_input("기상청 AWS 지점번호", value=114, step=1)
    with col3: 
        st.write("")
        st.write("")
        update_btn = st.button("🔄 실시간 데이터 최신화", use_container_width=True)

current_month = datetime.datetime.now(KST).month

# 데이터 수집 및 분석 실행
temp, rain, err_msg = fetch_current_weather(API_KEY, stn_id)
weather_warns, forest_warns = analyze_risks(temp, rain, current_month)
animal_alert = ANIMAL_WARNING_DB.get(current_month, {"동물": "해당없음", "경고": "특별히 주의할 야생동물이 없는 시기입니다.", "대처": "평소와 같이 안전에 유의하세요."})

st.markdown("---")

tab1, tab2 = st.tabs(["🗺️ 마을 관제 지도 & 실시간 경보", "✉️ 마을 방송 / 주민 문자 발송"])

# ---------------------------------------------------------
# [탭 1] 마을 관제 지도 & 실시간 알림판
# ---------------------------------------------------------
with tab1:
    map_col, data_col = st.columns([1.5, 1])
    
    with map_col:
        st.markdown("#### 📍 우리 마을 위험 생물 출몰 관제 지도")
        st.caption("💡 지도 위의 **주황색 원**은 위험 생물의 대략적인 출몰 범위를 나타냅니다. (원을 클릭하면 상세 정보 확인)")
        
        center_lat, center_lng = 37.3422, 127.9202
        m = folium.Map(location=[center_lat, center_lng], zoom_start=14)
        
        # 내 위치(마을 회관) - 여기는 정확한 핀 유지
        folium.Marker(
            [center_lat, center_lng], 
            tooltip="현재 내 위치 (마을 회관)", 
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)
        
        # 👉 [변경 사항] 위험 생물 마커 대신 투명한 원(범위) 표시
        for animal in species_data:
            popup_html = f"""
            <div style="font-family: sans-serif; min-width: 200px;">
                <h4 style="margin-bottom: 5px; color: {animal['color']};">🚨 {animal['name']} ({animal['status']})</h4>
                <p style="margin-top: 0; line-height: 1.5;">{animal['details'].replace('\n', '<br>')}</p>
                <p style="font-size: 11px; color: gray;">* 원 내부 영역은 대략적인 출몰 예상 범위입니다.</p>
            </div>
            """
            
            # 투명한 원으로 범위 표시
            folium.Circle(
                location=[animal['lat'], animal['lng']],
                radius=animal['radius'], # 데이터에 설정된 반지름 적용
                tooltip=f"⚠️ {animal['name']} 출몰 범위 (클릭)",
                popup=folium.Popup(popup_html, max_width=300),
                color=animal['color'], # 원 테두리 색상
                fill=True,
                fill_color=animal['color'], # 원 내부 채우기 색상
                fill_opacity=0.2, # 👉 투명도 설정 (0에 가까울수록 투명)
                border_width=1,
            ).add_to(m)
            
        st_folium(m, width="100%", height=450, returned_objects=[])

    with data_col:
        st.markdown(f"#### 🌡️ {village_name} 실시간 관측 데이터")
        if temp is not None:
            st.success(f"**현재 기온:** {temp} °C  |  **일 누적 강수량:** {rain} mm")
        else:
            st.error(f"기상 데이터 수신 실패: {err_msg}")
            
        st.markdown("#### 🚨 실시간 재난 알림")
        for w in weather_warns:
            title, desc = w.split('|')
            if "양호" in title: st.info(f"**[{title}]** {desc}")
            else: st.error(f"**[{title}]** {desc}")
            
        for f in forest_warns:
            title, desc = f.split('|')
            if "안전" in title: st.info(f"**[{title}]** {desc}")
            else: st.warning(f"**[{title}]** {desc}")
            
        st.markdown("#### 🐍 월별 야생동물 주의보")
        if animal_alert["동물"] != "해당없음":
            st.warning(f"**[{current_month}월 주의: {animal_alert['동물']}]**\n\n{animal_alert['경고']}\n\n👉 **대처:** {animal_alert['대처']}")
        else:
            st.info("현재 특별히 주의보가 발령된 야생동물이 없습니다.")

# ---------------------------------------------------------
# [탭 2] 마을 방송 및 주민 문자 발송 시스템 (수정/삭제 기능 추가)
# ---------------------------------------------------------
with tab2:
    st.markdown("### 📱 원클릭 마을 긴급 방송 및 스마트 문자 시스템")
    
    col_broadcast, col_sms = st.columns(2)
    
    with col_broadcast:
        st.markdown("#### 🎙️ 스마트 마을 스피커 방송")
        animal_names = [animal['name'] for animal in species_data]
        selected_animal = st.selectbox("방송할 위험 생물 선택:", animal_names, key="broadcast_select")
        
        if st.button("📢 즉시 마을 방송 송출하기", use_container_width=True, type="primary"):
            st.toast(f"🎙️ 아아, 이장입니다! 우리 마을 인근에 '{selected_animal}' 출몰이 확인되었습니다!", icon="🚨")
            st.success(f"✅ '{selected_animal}' 경고 안내 방송이 마을 스피커로 송출되었습니다.")

    with col_sms:
        st.markdown("#### ✉️ 어르신 맞춤형 SMS 전파")
        
        # --- 👉 [변경 사항] 주민 연락처 관리 UI 강화 (추가/수정/삭제) ---
        with st.expander("👥 마을 주민 연락처 관리 (추가/수정/삭제)", expanded=True):
            
            # 1. 주민 추가 및 수정 폼
            form_title = "➕ 새로운 주민 연락처 추가"
            button_text = "추가"
            default_name = ""
            default_phone = "010-"
            
            # 수정 모드일 때 폼 내용 변경
            if st.session_state.editing_index is not None:
                form_title = "✏️ 주민 연락처 수정"
                button_text = "수정 완료"
                edit_data = st.session_state.residents[st.session_state.editing_index]
                default_name = edit_data["이름"]
                default_phone = edit_data["연락처"]

            with st.form("add_resident_form", clear_on_submit=True):
                st.write(f"**{form_title}**")
                c1, c2, c3 = st.columns([1, 1.5, 0.8])
                new_name = c1.text_input("이름", value=default_name, placeholder="홍길동")
                new_phone = c2.text_input("연락처", value=default_phone, placeholder="010-1234-5678")
                submitted = c3.form_submit_button(button_text, use_container_width=True)
                
                if submitted:
                    if new_name and new_phone:
                        if st.session_state.editing_index is not None:
                            # 👉 수정 로직
                            st.session_state.residents[st.session_state.editing_index] = {"이름": new_name, "연락처": new_phone}
                            st.session_state.editing_index = None # 수정 모드 종료
                            st.toast(f"'{new_name}' 어르신 연락처가 수정되었습니다.", icon="✏️")
                        else:
                            # 👉 추가 로직
                            st.session_state.residents.append({"이름": new_name, "연락처": new_phone})
                            st.toast(f"'{new_name}' 어르신이 주소록에 추가되었습니다.", icon="➕")
                        st.rerun() # 화면 새로고침
                    else:
                        st.error("이름과 연락처를 모두 입력해주세요.")
            
            if st.session_state.editing_index is not None:
                if st.button("❌ 수정 취소", use_container_width=True):
                    st.session_state.editing_index = None
                    st.rerun()

            st.write("---")
            
            # 2. 👉 주민 목록 출력 (수정/삭제 버튼 포함)
            st.write(f"**👥 현재 등록된 주민 목록 (총 {len(st.session_state.residents)}명)**")
            if st.session_state.residents:
                # 표 디자인 대신 알아보기 쉬운 리스트 형태와 버튼 배치
                for i, resident in enumerate(st.session_state.residents):
                    r_col1, r_col2, r_col3, r_col4 = st.columns([1, 1.5, 0.5, 0.5])
                    r_col1.write(f"**{resident['이름']}**")
                    r_col2.write(f"{resident['연락처']}")
                    
                    # ✏️ 수정 버튼
                    if r_col3.button("✏️", key=f"edit_{i}", help=f"'{resident['이름']}' 수정"):
                        st.session_state.editing_index = i
                        st.rerun()
                        
                    # 🗑️ 삭제 버튼
                    if r_col4.button("🗑️", key=f"del_{i}", help=f"'{resident['이름']}' 삭제"):
                        st.session_state.residents.pop(i)
                        st.toast(f"'{resident['이름']}' 어르신 연락처가 삭제되었습니다.", icon="🗑️")
                        st.rerun()
            else:
                st.info("현재 등록된 연락처가 없습니다.")

        st.markdown("---")
        
        # 발송 문자 자동 조합
        st.markdown("##### 📝 발송될 문자 내용")
        
        auto_sms = f"[{village_name} 안전알림]\n어르신들, 이장입니다.\n\n"
        for w in weather_warns:
            if "양호" not in w: auto_sms += f"👉 {w.split('|')[1]}\n"
        for f in forest_warns:
            if "안전" not in f: auto_sms += f"👉 {f.split('|')[1]}\n"
        if animal_alert["동물"] != "해당없음":
            auto_sms += f"👉 {animal_alert['대처']}\n"
            
        auto_sms += f"👉 현재 지도에 표시된 '{selected_animal}' 출몰 범위 인근을 지날 때 특별히 주의바랍니다.\n"
        auto_sms += "\n항상 건강 조심하십시오."

        sms_content = st.text_area("내용 확인 및 수정", auto_sms, height=180, label_visibility="collapsed", key="sms_area")
        
        # 실제 문자 발송 버튼
        if st.button("🚀 주소록에 등록된 전체 주민에게 문자 발송", use_container_width=True, type="primary", key="sms_send_btn"):
            if not st.session_state.residents:
                st.warning("⚠️ 연락처 관리에 주민을 먼저 등록해주세요.")
            else:
                resident_count = len(st.session_state.residents)
                st.balloons() # 성공 축하 애니메이션
                st.success(f"✅ 총 **{resident_count}명**의 마을 어르신들에게 성공적으로 안내 문자가 발송되었습니다! (UI 테스트 모드)")