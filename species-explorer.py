import streamlit as st
import pandas as pd
import os
import io
import sys
from datetime import datetime

# =====================================================================
# 1. 웹 페이지 기본 설정
# =====================================================================
st.set_page_config(page_title="사무소 생물종 출현 검색기", page_icon="🌳", layout="wide")

# 세션 상태 초기화 (데이터를 메모리에 기억해두는 역할)
if 'df' not in st.session_state:
    st.session_state.df = None
if 'ref_db' not in st.session_state:
    st.session_state.ref_db = None
if 'all_species' not in st.session_state:
    st.session_state.all_species = []

# =====================================================================
# 2. 핵심 로직: 기준 DB (멸종위기/교란종) 처리 함수
# =====================================================================
@st.cache_data
def load_auto_reference_db():
    """같은 폴더에 있는 기준 DB 파일을 자동으로 찾아 읽어옵니다."""
    search_dirs = [os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
    possible_files = ['Endangered&Invasive species.xlsx', 'Endangered&Invasive species.csv', 'species_reference_db.csv']
    
    for d in search_dirs:
        for file_name in possible_files:
            file_path = os.path.join(d, file_name)
            if os.path.exists(file_path):
                try:
                    if file_path.endswith('.csv'):
                        try:
                            temp_df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)
                        except UnicodeDecodeError:
                            temp_df = pd.read_csv(file_path, encoding='cp949', low_memory=False)
                    else:
                        temp_df = pd.read_excel(file_path, engine='openpyxl')
                        
                    # 열 이름 표준화
                    cols = temp_df.columns.tolist()
                    col_map = {}
                    for c in cols:
                        c_str = str(c).replace(" ", "")
                        if '국명' in c_str or '기준국명' in c_str: col_map[c] = '기준국명'
                        elif '멸종' in c_str or '위기' in c_str: col_map[c] = '멸종위기등급'
                        elif '교란' in c_str: col_map[c] = '교란종여부'
                    temp_df.rename(columns=col_map, inplace=True)
                    
                    if '기준국명' not in temp_df.columns:
                        continue
                        
                    if '멸종위기등급' not in temp_df.columns: temp_df['멸종위기등급'] = "-"
                    if '교란종여부' not in temp_df.columns: temp_df['교란종여부'] = "-"
                    
                    ref_df = temp_df[['기준국명', '멸종위기등급', '교란종여부']].copy()
                    ref_df['기준국명'] = ref_df['기준국명'].astype(str).str.strip()
                    ref_df.drop_duplicates(subset=['기준국명'], inplace=True)
                    return ref_df
                except Exception:
                    pass
    return None

@st.cache_data
def process_manual_ref_db(uploaded_file):
    """사용자가 직접 업로드한 기준 DB를 처리합니다."""
    try:
        if uploaded_file.name.endswith('.csv'):
            try:
                temp_df = pd.read_csv(uploaded_file, encoding='utf-8-sig', low_memory=False)
            except:
                temp_df = pd.read_csv(uploaded_file, encoding='cp949', low_memory=False)
        else:
            temp_df = pd.read_excel(uploaded_file, engine='openpyxl')
            
        cols = temp_df.columns.tolist()
        col_map = {}
        for c in cols:
            c_str = str(c).replace(" ", "")
            if '국명' in c_str or '기준국명' in c_str: col_map[c] = '기준국명'
            elif '멸종' in c_str or '위기' in c_str: col_map[c] = '멸종위기등급'
            elif '교란' in c_str: col_map[c] = '교란종여부'
        temp_df.rename(columns=col_map, inplace=True)
        
        if '기준국명' not in temp_df.columns:
            st.sidebar.error("'국명' 또는 '기준국명' 열이 없습니다.")
            return None
            
        if '멸종위기등급' not in temp_df.columns: temp_df['멸종위기등급'] = "-"
        if '교란종여부' not in temp_df.columns: temp_df['교란종여부'] = "-"
        
        ref_df = temp_df[['기준국명', '멸종위기등급', '교란종여부']].copy()
        ref_df['기준국명'] = ref_df['기준국명'].astype(str).str.strip()
        ref_df.drop_duplicates(subset=['기준국명'], inplace=True)
        return ref_df
    except Exception as e:
        st.sidebar.error(f"기준 DB 처리 오류: {e}")
        return None

# =====================================================================
# 3. 핵심 로직: 분석 데이터 병합 및 정제 함수
# =====================================================================
@st.cache_data
def process_main_data(uploaded_file):
    """여러 시트의 데이터를 통합하고 환경부/NIBR 기준으로 정제합니다."""
    try:
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8-sig', low_memory=False)
            except UnicodeDecodeError:
                df = pd.read_csv(uploaded_file, encoding='cp949', low_memory=False)
        else:
            xls = pd.ExcelFile(uploaded_file, engine='openpyxl')
            target_sheets = ["sheet1", "sheet2", "sheet3", "고등균류", "리스트"]
            valid_sheets = [s for s in xls.sheet_names if s in target_sheets]
            if not valid_sheets:
                valid_sheets = xls.sheet_names
            
            df_list = []
            for sheet in valid_sheets:
                temp_df = pd.read_excel(xls, sheet_name=sheet)
                df_list.append(temp_df)
            df = pd.concat(df_list, ignore_index=True)

        cols = df.columns.tolist()
        
        # 필수 열 검사
        base_required = ['국립공원명', '기준국명']
        if not all(col in cols for col in base_required):
            if '국명' in cols and '국립공원명' in cols:
                df.rename(columns={'국명': '기준국명'}, inplace=True)
            else:
                st.error(f"필수 열이 없습니다: {base_required} 또는 ['국립공원명', '국명']")
                return None

        # 시간 데이터 인식
        time_candidates = ['연도', '날짜', '조사일', '조사일시', '일시', '조사일자', '년도']
        time_col = next((c for c in time_candidates if c in cols), None)
        if not time_col:
            st.error(f"시간 정보가 없습니다. 엑셀에 {time_candidates} 중 하나가 있어야 합니다.")
            return None

        task_col = '과제명' if '과제명' in df.columns else '과제' if '과제' in df.columns else None
        sci_col = '기준학명' if '기준학명' in cols else '학명' if '학명' in cols else None
        count_col = '개체수'

        current_year = datetime.now().year
        raw_years = df[time_col].astype(str).str.extract(r'(\d{4})')[0]
        df['연도_temp'] = pd.to_numeric(raw_years, errors='coerce')
        df = df[(df['연도_temp'] >= 1900) & (df['연도_temp'] <= current_year)]
        df['연도'] = df['연도_temp'].astype(int).astype(str)
        
        df = df.dropna(subset=['연도', '국립공원명', '기준국명'])

        # 오류종 및 공원명없음 제거
        df = df[~df['국립공원명'].astype(str).str.contains('공원명없음', na=False)]
        df = df[~df['기준국명'].astype(str).str.contains('오류종', na=False)]
        df['기준국명'] = df['기준국명'].astype(str).str.strip()
        df = df.drop_duplicates()

        # 개체수 정제
        if count_col in df.columns:
            clean_counts = df[count_col].astype(str).str.replace(',', '', regex=False).str.replace(' ', '', regex=False)
            extracted_counts = clean_counts.str.extract(r'(\d+)')[0]
            df[count_col] = pd.to_numeric(extracted_counts, errors='coerce').fillna(0)

        # 그룹화 (데이터 제한 없음)
        agg_dict = {}
        if task_col:
            agg_dict[task_col] = lambda x: ', '.join(sorted(set(x.dropna().astype(str))))
        if count_col in df.columns:
            agg_dict[count_col] = 'sum'
        if sci_col:
            agg_dict[sci_col] = 'first'

        if agg_dict:
            df = df.groupby(['국립공원명', '연도', '기준국명'], as_index=False).agg(agg_dict)
        else:
            df = df.drop_duplicates(subset=['국립공원명', '연도', '기준국명'])

        # 결과 출력을 위한 컬럼명 표준화 보장
        rename_dict = {}
        if task_col: rename_dict[task_col] = '발견 과제'
        if sci_col: rename_dict[sci_col] = '기준학명'
        df.rename(columns=rename_dict, inplace=True)
        
        return df
    except Exception as e:
        st.error(f"파일 처리 중 오류 발생: {e}")
        return None

# 엑셀 다운로드를 위한 변환 함수
@st.cache_data
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='검색결과')
    return output.getvalue()

# =====================================================================
# 4. 화면 UI 구성
# =====================================================================

# 최초 1회 기준 DB 자동 로드
if st.session_state.ref_db is None:
    st.session_state.ref_db = load_auto_reference_db()

st.title("🌳 국립공원 생물종 출현 검색기")
st.markdown("**환경부 및 국립생물자원관(NIBR) 기준 적용** | 데이터 수량 무제한 통합 분석")
st.divider()

# 좌측 사이드바: 파일 업로드 및 설정
with st.sidebar:
    st.header("⚙️ 데이터 설정")
    
    # 기준 DB 수동 등록
    if st.session_state.ref_db is not None:
        st.success(f"✅ 기준 DB 자동 적용됨 (총 {len(st.session_state.ref_db):,}종)")
    else:
        st.info("기본 기준 DB가 없습니다.")
    
    with st.expander("기준 DB (멸종/교란) 수동 변경"):
        ref_file = st.file_uploader("기준 DB 엑셀/CSV 업로드", type=['xlsx', 'xls', 'csv'], key="ref_uploader")
        if ref_file:
            new_ref = process_manual_ref_db(ref_file)
            if new_ref is not None:
                st.session_state.ref_db = new_ref
                st.success("기준 DB 갱신 완료!")

    st.markdown("---")
    
    # 메인 데이터 업로드
    st.subheader("📂 1. 분석할 데이터 불러오기")
    main_file = st.file_uploader("조사 데이터 엑셀/CSV 드래그 앤 드롭", type=['xlsx', 'xls', 'csv'])
    
    if main_file:
        with st.spinner("데이터를 최초 1회 취합하고 정제하는 중입니다... (이후부터는 즉시 로딩됩니다)"):
            processed_df = process_main_data(main_file)
            if processed_df is not None:
                st.session_state.df = processed_df
                
                # 검색용 종명 리스트 추출
                kor_names = processed_df['기준국명'].dropna().astype(str).unique().tolist()
                sci_names = processed_df['기준학명'].dropna().astype(str).unique().tolist() if '기준학명' in processed_df.columns else []
                combined = set(kor_names + sci_names)
                st.session_state.all_species = sorted([s for s in combined if str(s).strip() and str(s).strip() != '-'])
                
                st.success(f"데이터 로드 완료! (유효 데이터: {len(processed_df):,}건)")

# 메인 화면: 검색 및 결과 표출
if st.session_state.df is not None:
    st.subheader("🔍 2. 분류군(특정 종) 출현 검색")
    
    df = st.session_state.df
    park_list = ["전체 국립공원"] + sorted(df['국립공원명'].unique().tolist())
    
    col1, col2 = st.columns([1, 2])
    with col1:
        selected_park = st.selectbox("국립공원명", park_list)
    with col2:
        # 타이핑 시 실시간 자동완성 지원
        search_term = st.selectbox("종명 (국명 또는 학명 입력)", [""] + st.session_state.all_species)

    search_btn = st.button("🔍 출현 기록 검색", type="primary")

    # 버튼을 누르거나, 검색창에서 Enter를 쳐서 search_term에 값이 들어오면 즉시 실행되도록 수정 (search_btn 조건 해제)
    if search_term:
        # 검색 필터링 (대소문자 무시)
        mask = df['기준국명'].str.contains(search_term, na=False, case=False)
        if '기준학명' in df.columns:
            mask = mask | df['기준학명'].astype(str).str.contains(search_term, na=False, case=False)
            
        search_df = df[mask]
        
        if selected_park != "전체 국립공원":
            search_df = search_df[search_df['국립공원명'] == selected_park]
            
        search_df = search_df.sort_values(by=['기준국명', '연도', '국립공원명'], ascending=[True, False, True])
        
        if search_df.empty:
            st.warning(f"'{search_term}'에 대한 출현 기록이 없습니다.")
        else:
            # 멸종위기 / 교란종 정보 결합
            if st.session_state.ref_db is not None:
                search_df = pd.merge(search_df, st.session_state.ref_db, on='기준국명', how='left')
                search_df['멸종위기등급'] = search_df['멸종위기등급'].fillna("-")
                search_df['교란종여부'] = search_df['교란종여부'].fillna("-")
            else:
                search_df['멸종위기등급'] = "-"
                search_df['교란종여부'] = "-"

            # 출력용 컬럼 순서 정렬
            display_cols = ['국립공원명', '연도', '기준국명', '기준학명']
            if '발견 과제' in search_df.columns: display_cols.append('발견 과제')
            if '개체수' in search_df.columns: display_cols.append('개체수')
            display_cols.extend(['멸종위기등급', '교란종여부'])
            
            # 최종 출력할 컬럼만 필터링 (존재하는 컬럼만)
            final_cols = [c for c in display_cols if c in search_df.columns]
            final_result = search_df[final_cols]
            
            # 최근 연도 미출현 안내 메시지 처리
            recent_year = df['연도'].max() if selected_park == "전체 국립공원" else df[df['국립공원명'] == selected_park]['연도'].max()
            has_recent = (final_result['연도'] == str(recent_year)).any()
            
            if not has_recent:
                st.info(f"💡 주의: '{search_term}' 종은 최근 조사 연도({recent_year}년)에 출현 기록이 없습니다.")

            st.success(f"검색 완료: 총 {len(final_result):,}건 발견")
            
            # 모든 내용을 생략 없이 표로 출력
            st.dataframe(final_result, use_container_width=True, hide_index=True)
            
            # 엑셀 저장 버튼
            excel_data = to_excel(final_result)
            st.download_button(
                label="📁 엑셀(.xlsx)로 저장",
                data=excel_data,
                file_name=f"검색결과_{search_term}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("👈 왼쪽 사이드바에서 엑셀/CSV 데이터를 먼저 업로드해 주세요.")
