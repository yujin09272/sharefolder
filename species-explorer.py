import pandas as pd
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
import threading
import os
import sys
from datetime import datetime
import numpy as np

# 윈도우 환경 드래그 앤 드롭을 위한 라이브러리
try:
    import windnd
except ImportError:
    pass

class ModernEcoAnalyzer:
    def __init__(self, root):
        """
        프로그램이 처음 실행될 때 기본 환경을 세팅합니다.
        환경부 및 국립생물자원관(NIBR) 데이터 기준을 완벽하게 준수합니다.
        """
        self.root = root
        self.root.title("🐰 사무소 생물종 출현 검색기🐰")
        self.root.geometry("1100x750")
        
        # ---------------------------------------------------------
        # 전역 데이터 관리 변수 초기화
        # ---------------------------------------------------------
        self.df = None                   
        self.last_search_df = None       
        self.tab2_export_data = None     
        self.all_species = []            # 전체 종 목록 (콤보박스 검색용)
        
        # 기준 DB 변수 (멸종위기, 교란종 등)
        self.ref_db = None
        
        # ---------------------------------------------------------
        # 엑셀 열 이름 동적 인식 변수
        # ---------------------------------------------------------
        self.task_col = None             
        self.time_col = None             
        self.sci_col = None              # 메인 데이터의 학명/기준학명 열 인식
        
        # '개체수'라는 열만 엄격하게 사용
        self.count_col = '개체수'        
        
        # 현재 연도 설정
        self.current_year = datetime.now().year
        
        # ---------------------------------------------------------
        # 기본 폰트 크기 및 테마 상태 설정
        # ---------------------------------------------------------
        self.base_font_size = 11  # 전체 기본 글씨 크기
        self.title_font_size = 20 # 제목 글씨 크기
        self.current_theme = "sandstone" # 현재 적용된 테마 상태 저장
        
        self.setup_fonts()
        
        # UI 세팅 전에 지정된 이름의 파일이 있으면 자동으로 먼저 읽어옵니다.
        self.auto_load_reference_db()
        self.setup_ui()

    def setup_fonts(self):
        """글씨 크기를 동적으로 조절하고 표 칸 크기도 함께 맞추는 함수"""
        style = tb.Style()
        
        # 폰트 크기에 비례하여 표의 세로 칸(행) 높이를 아주 넉넉하게 계산합니다.
        dynamic_row_height = int(self.base_font_size * 2.5) + 5
        
        # 전체 기본 폰트
        style.configure('.', font=('맑은 고딕', self.base_font_size))
        
        # 기본 Treeview 스타일 업데이트
        style.configure('Treeview', font=('맑은 고딕', self.base_font_size), rowheight=dynamic_row_height)
        style.configure('Treeview.Heading', font=('맑은 고딕', self.base_font_size, 'bold'), relief="raised", borderwidth=1)
        
        # bootstyle="success" 가 적용된 Treeview 전용 스타일도 명시적으로 업데이트
        style.configure('success.Treeview', font=('맑은 고딕', self.base_font_size), rowheight=dynamic_row_height)
        style.configure('success.Treeview.Heading', font=('맑은 고딕', self.base_font_size, 'bold'), relief="raised", borderwidth=1)

        # UI가 이미 생성되어 있다면 개별 라벨들의 폰트도 업데이트
        if hasattr(self, 'header_lbl'):
            self.header_lbl.config(font=("맑은 고딕", self.title_font_size, "bold"))
        if hasattr(self, 'zoom_lbl'):
            self.zoom_lbl.config(font=("맑은 고딕", self.base_font_size))
        if hasattr(self, 'status_lbl'):
            self.status_lbl.config(font=("맑은 고딕", self.base_font_size))
        if hasattr(self, 'progress_lbl'):
            self.progress_lbl.config(font=("맑은 고딕", self.base_font_size, "bold"))

    def zoom_in(self):
        """글씨 크기 및 표 칸 크기 확대"""
        if self.base_font_size < 24: # 최대 크기 제한
            self.base_font_size += 1
            self.title_font_size += 1
            self.setup_fonts()

    def zoom_out(self):
        """글씨 크기 및 표 칸 크기 축소"""
        if self.base_font_size > 8: # 최소 크기 제한
            self.base_font_size -= 1
            self.title_font_size -= 1
            self.setup_fonts()

    def toggle_theme(self):
        """테마를 밝은 모드(sandstone)와 다크 모드(darkly) 사이에서 전환합니다."""
        style = tb.Style()
        if self.current_theme == "sandstone":
            self.current_theme = "darkly"
            style.theme_use("darkly")
            # 다크 테마일 때 버튼 색상을 진하게(solid) 변경
            self.theme_btn.config(text="☀️", bootstyle="secondary")
            self.zoom_out_btn.config(bootstyle="secondary")
            self.zoom_in_btn.config(bootstyle="secondary")
            # 다크 테마에서 스크롤바(가로/세로 툴바)가 잘 보이도록 밝고 둥근 스타일로 변경
            if hasattr(self, 'v_scroll2') and hasattr(self, 'h_scroll2'):
                self.v_scroll2.config(bootstyle="light-round")
                self.h_scroll2.config(bootstyle="light-round")
        else:
            self.current_theme = "sandstone"
            style.theme_use("sandstone")
            # 밝은 테마일 때 원래대로 테두리형(outline) 복구
            self.theme_btn.config(text="🌙", bootstyle="secondary-outline")
            self.zoom_out_btn.config(bootstyle="secondary-outline")
            self.zoom_in_btn.config(bootstyle="secondary-outline")
            # 밝은 테마일 때 스크롤바 원상 복구
            if hasattr(self, 'v_scroll2') and hasattr(self, 'h_scroll2'):
                self.v_scroll2.config(bootstyle="default")
                self.h_scroll2.config(bootstyle="default")
            
        # 테마가 변경되면 커스텀 폰트 및 높이 설정이 초기화되므로 다시 적용해줍니다.
        self.setup_fonts()

    def auto_load_reference_db(self):
        """
        프로그램 시작 시 폴더에 'Endangered&Invasive species.xlsx' 또는 '.csv'가 있으면 
        사용자 조작 없이 자동으로 기준 DB를 메모리에 로드합니다.
        """
        # 스크립트가 실행된 실제 폴더 위치를 정확하게 찾습니다.
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            script_dir = os.path.abspath(".")
            
        current_dir = os.getcwd()
        
        # 실행 위치와 현재 위치 모두에서 파일을 탐색합니다.
        search_dirs = [script_dir, current_dir]
        possible_files = ['Endangered&Invasive species.xlsx', 'Endangered&Invasive species.csv', 'species_reference_db.csv']
        
        for d in search_dirs:
            for file_name in possible_files:
                file_path = os.path.join(d, file_name)
                
                if os.path.exists(file_path):
                    try:
                        if file_path.endswith('.csv'):
                            # 한글 인코딩 깨짐을 방지하기 위해 두 가지 방식을 시도합니다.
                            try:
                                temp_df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)
                            except UnicodeDecodeError:
                                temp_df = pd.read_csv(file_path, encoding='cp949', low_memory=False)
                        else:
                            temp_df = pd.read_excel(file_path, engine='openpyxl')
                            
                        cols = temp_df.columns.tolist()
                        col_map = {}
                        for c in cols:
                            c_str = str(c).replace(" ", "")
                            if '국명' in c_str or '기준국명' in c_str: col_map[c] = '기준국명'
                            elif '멸종' in c_str or '위기' in c_str: col_map[c] = '멸종위기등급'
                            elif '교란' in c_str: col_map[c] = '교란종여부'
                        
                        temp_df.rename(columns=col_map, inplace=True)
                        
                        # 국명 열이 없으면 이 파일은 무시하고 다음 파일을 찾습니다.
                        if '기준국명' not in temp_df.columns:
                            continue 
                            
                        if '멸종위기등급' not in temp_df.columns: temp_df['멸종위기등급'] = "-"
                        if '교란종여부' not in temp_df.columns: temp_df['교란종여부'] = "-"
                        
                        self.ref_db = temp_df[['기준국명', '멸종위기등급', '교란종여부']].copy()
                        self.ref_db['기준국명'] = self.ref_db['기준국명'].astype(str).str.strip()
                        self.ref_db.drop_duplicates(subset=['기준국명'], inplace=True)
                        
                        # 성공적으로 로드했으면 탐색을 즉시 종료합니다.
                        return 
                    except Exception:
                        pass # 실패하더라도 프로그램이 꺼지지 않게 조용히 넘깁니다.

    def setup_ui(self):
        """
        전체 UI 레이아웃, 상태바, 탭 메뉴 등을 화면에 그립니다.
        """
        # 타이틀 영역
        header_frame = tb.Frame(self.root, padding=(20, 20, 20, 10))
        header_frame.pack(fill=X)
        
        self.header_lbl = tb.Label(header_frame, text="🌳국립공원 생물종 검색기🌳", font=("맑은 고딕", self.title_font_size, "bold"), bootstyle="success")
        self.header_lbl.pack(side=LEFT)
        
        # 확대/축소 및 테마 전환 컨트롤 영역 추가
        zoom_frame = tb.Frame(header_frame)
        zoom_frame.pack(side=RIGHT, pady=5)
        
        # 다크/라이트 테마 전환 버튼
        self.theme_btn = tb.Button(zoom_frame, text="🌙", bootstyle="secondary-outline", command=self.toggle_theme, padding=(10, 2))
        self.theme_btn.pack(side=LEFT, padx=(0, 15))

        self.zoom_lbl = tb.Label(zoom_frame, text="🔍 화면 배율:", font=("맑은 고딕", self.base_font_size))
        self.zoom_lbl.pack(side=LEFT, padx=5)
        
        self.zoom_out_btn = tb.Button(zoom_frame, text=" - ", bootstyle="secondary-outline", command=self.zoom_out, padding=(10, 2))
        self.zoom_out_btn.pack(side=LEFT, padx=2)
        
        self.zoom_in_btn = tb.Button(zoom_frame, text=" + ", bootstyle="secondary-outline", command=self.zoom_in, padding=(10, 2))
        self.zoom_in_btn.pack(side=LEFT, padx=2)

        # ---------------------------------------------------------
        # 깔끔한 가로 툴바(Toolbar) 프레임 추가
        # ---------------------------------------------------------
        toolbar_frame = tb.Frame(self.root, padding=(20, 0, 20, 10))
        toolbar_frame.pack(fill=X)
        
        # 1. 기존 파일 탐색기 버튼
        self.load_btn = tb.Button(toolbar_frame, text="📂 엑셀/CSV 데이터 불러오기", bootstyle="success", command=self.load_data)
        self.load_btn.pack(side=LEFT, padx=(0, 5))

        # 2. 드래그 앤 드롭 존
        self.drop_zone = tb.Label(
            toolbar_frame, 
            text="📥 이곳에 분석할 엑셀/CSV 파일을 드래그 앤 드롭하세요", 
            bootstyle="success-inverse", 
            padding=(15, 6),
            relief="flat"
        )
        self.drop_zone.pack(side=LEFT, padx=(0, 5))

        # 3. 드롭 엔진 연결
        if 'windnd' in sys.modules:
            windnd.hook_dropfiles(self.drop_zone, self.on_file_drop)
            windnd.hook_dropfiles(self.load_btn, self.on_file_drop) # 덤으로 버튼 위에 올려도 인식되도록 설정
        else:
            self.drop_zone.config(text="⚠️ 터미널에 pip install windnd 를 입력해야 드래그 기능이 켜집니다", bootstyle="warning-inverse")
        
        # 4. 기준 DB 버튼
        btn_text = "✅ 기준 DB 자동적용됨" if self.ref_db is not None else "⚙️ 기준 DB(멸종/교란) 수동 등록"
        btn_style = "info" if self.ref_db is not None else "info-outline"
        
        self.ref_btn = tb.Button(toolbar_frame, text=btn_text, bootstyle=btn_style, command=self.update_reference_db)
        self.ref_btn.pack(side=LEFT, padx=5)

        # 툴바와 아래 콘텐츠를 분리하는 시각적 구분선
        tb.Separator(self.root, bootstyle="default").pack(fill=X, padx=20, pady=(0, 10))

        # 상태 안내 메시지
        self.status_lbl = tb.Label(
            self.root, 
            text="대기 중... 데이터를 불러와주세요. (여러 시트의 데이터를 한 번에 통합 분석합니다)", 
            font=("맑은 고딕", self.base_font_size), 
            bootstyle="secondary"
        )
        self.status_lbl.pack(fill=X, padx=20)

        # ---------------------------------------------------------
        # 데이터 로딩 진행률 표시 바
        # ---------------------------------------------------------
        self.progress_frame = tb.Frame(self.root)
        self.progress_frame.pack(fill=X, padx=20, pady=(5, 5))
        
        self.progress_bar = tb.Progressbar(self.progress_frame, bootstyle="success-striped", mode="determinate", maximum=100)
        self.progress_bar.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        
        self.progress_lbl = tb.Label(self.progress_frame, text="", font=("맑은 고딕", self.base_font_size, "bold"), bootstyle="success")
        self.progress_lbl.pack(side=RIGHT)

        self.notebook = tb.Notebook(self.root, bootstyle="success")
        self.notebook.pack(fill=BOTH, expand=True, padx=20, pady=10)
        
        self.tab2 = tb.Frame(self.notebook, padding=15)
        self.notebook.add(self.tab2, text="🔍 분류군(특정 종) 출현 검색")

        self.setup_tab2()

    def on_file_drop(self, files):
        """드래그 앤 드롭으로 파일이 들어왔을 때 실행되는 함수입니다."""
        if not files: return
        
        try:
            # 윈도우 환경에서 드롭된 파일은 cp949 인코딩 바이트로 전달됩니다.
            file_path = files[0].decode('cp949')
        except Exception:
            file_path = files[0].decode('utf-8', errors='ignore')

        # 확장자 검사
        ext = os.path.splitext(file_path)[-1].lower()
        if ext not in ['.xlsx', '.xls', '.csv']:
            messagebox.showerror("오류", "엑셀(.xlsx, .xls) 또는 CSV(.csv) 파일만 분석할 수 있습니다.")
            return

        self.load_btn.config(state="disabled")
        self.status_lbl.config(text="데이터를 읽어오는 중입니다. 파일 크기에 따라 시간이 소요됩니다...", bootstyle="warning")
        self.update_progress_ui(0)

        # 데이터 처리 쓰레드 시작
        threading.Thread(target=self._process_data_thread, args=(file_path,), daemon=True).start()

    def update_reference_db(self):
        """사용자가 수동으로 기준 DB 엑셀을 업로드하면 로컬 CSV로 저장하고 갱신합니다."""
        file_path = filedialog.askopenfilename(title="기준 DB(멸종/교란) 선택", filetypes=[("Excel Files", "*.xlsx;*.xls"), ("CSV Files", "*.csv")])
        if not file_path: return
        
        try:
            if file_path.endswith('.csv'):
                try:
                    temp_df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)
                except UnicodeDecodeError:
                    temp_df = pd.read_csv(file_path, encoding='cp949', low_memory=False)
            else:
                temp_df = pd.read_excel(file_path, engine='openpyxl')
            
            cols = temp_df.columns.tolist()
            col_map = {}
            for c in cols:
                c_str = str(c).replace(" ", "")
                if '국명' in c_str or '기준국명' in c_str: col_map[c] = '기준국명'
                elif '멸종' in c_str or '위기' in c_str: col_map[c] = '멸종위기등급'
                elif '교란' in c_str: col_map[c] = '교란종여부'
            
            temp_df.rename(columns=col_map, inplace=True)
            
            if '기준국명' not in temp_df.columns:
                messagebox.showerror("오류", "선택한 파일에 '국명' 또는 '기준국명' 열이 존재하지 않습니다.")
                return
                
            if '멸종위기등급' not in temp_df.columns: temp_df['멸종위기등급'] = "-"
            if '교란종여부' not in temp_df.columns: temp_df['교란종여부'] = "-"
            
            self.ref_db = temp_df[['기준국명', '멸종위기등급', '교란종여부']].copy()
            self.ref_db['기준국명'] = self.ref_db['기준국명'].astype(str).str.strip()
            self.ref_db.drop_duplicates(subset=['기준국명'], inplace=True)
            
            # 다음번 실행 시에도 자동으로 불러올 수 있도록 로컬 파일 백업
            self.ref_db.to_csv("species_reference_db.csv", index=False, encoding='utf-8-sig')
            
            # 버튼 UI 업데이트
            self.ref_btn.config(text="✅ 기준 DB 적용완료", bootstyle="info")
            messagebox.showinfo("성공", f"기준 DB가 성공적으로 등록되었습니다. (총 {len(self.ref_db)}종)\n이제 출현 검색 시 멸종위기 및 교란종 정보가 표시됩니다.")
            
        except Exception as e:
            messagebox.showerror("오류", f"기준 DB 등록 중 오류가 발생했습니다:\n{e}")

    def _get_species_info(self, species_name):
        """기준 DB에서 특정 종의 멸종위기등급과 교란종 여부를 가져옵니다."""
        endangered = "-"
        alien = "-"
        if self.ref_db is not None and not self.ref_db.empty:
            match = self.ref_db[self.ref_db['기준국명'] == species_name]
            if not match.empty:
                val_e = match['멸종위기등급'].iloc[0]
                val_a = match['교란종여부'].iloc[0]
                
                endangered = str(val_e) if pd.notna(val_e) else "-"
                alien = str(val_a) if pd.notna(val_a) else "-"
        return endangered, alien

    def filter_species(self, event):
        """종명 콤보박스에 입력된 텍스트를 기반으로 드롭다운 목록을 실시간 필터링합니다."""
        # 방향키, 엔터 등 기능키는 무시
        if event.keysym in ('Up', 'Down', 'Return', 'Left', 'Right', 'Tab'):
            return
            
        typed_value = self.species_combo.get()
        
        if not self.all_species:
            return
            
        if typed_value == '':
            self.species_combo['values'] = self.all_species
        else:
            # 입력한 글자(국명 또는 학명)가 포함된 종만 필터링 (대소문자 구분 없이)
            typed_lower = typed_value.lower()
            filtered = [s for s in self.all_species if typed_lower in s.lower()]
            self.species_combo['values'] = filtered

    def setup_tab2(self):
        """
        '분류군(특정 종) 출현 검색' 화면의 컨트롤러와 표(Treeview)를 구성합니다.
        """
        control_frame = tb.Frame(self.tab2)
        control_frame.pack(fill=X, pady=(0, 15))
        
        tb.Label(control_frame, text="국립공원명:").pack(side=LEFT, padx=5)
        self.park_combo_tab2 = tb.Combobox(control_frame, state="readonly", width=15)
        self.park_combo_tab2.pack(side=LEFT, padx=5)
        
        # '종명' 콤보박스 및 검색(필터링) 기능 바인딩
        tb.Label(control_frame, text="종명:").pack(side=LEFT, padx=(15, 5))
        self.species_combo = tb.Combobox(control_frame, width=25)
        self.species_combo.pack(side=LEFT, padx=5)
        
        self.species_combo.bind('<KeyRelease>', self.filter_species)
        self.species_combo.bind("<Return>", lambda event: self.search_species())
        
        tb.Button(control_frame, text="🔍 출현 기록 검색", bootstyle="warning", command=self.search_species).pack(side=LEFT, padx=10)
        tb.Button(control_frame, text="📁 엑셀 저장", bootstyle="warning", command=self.export_search_results).pack(side=RIGHT, padx=5)

        tree_frame2 = tb.Frame(self.tab2)
        tree_frame2.pack(fill=BOTH, expand=True)

        # 가로, 세로 스크롤바 추가 및 인스턴스 변수로 변경(다크 테마 전환 시 접근 가능하게)
        self.v_scroll2 = tb.Scrollbar(tree_frame2, orient=VERTICAL)
        self.v_scroll2.pack(side=RIGHT, fill=Y)
        
        self.h_scroll2 = tb.Scrollbar(tree_frame2, orient=HORIZONTAL)
        self.h_scroll2.pack(side=BOTTOM, fill=X)

        # 기준학명, 멸종위기등급, 교란종여부 컬럼
        columns = ("Park", "Year", "Species", "SciName", "Task", "Count", "Endangered", "Alien")
        self.tree2 = tb.Treeview(tree_frame2, columns=columns, show="headings", bootstyle="success",
                                 yscrollcommand=self.v_scroll2.set, xscrollcommand=self.h_scroll2.set)
        self.tree2.pack(side=LEFT, fill=BOTH, expand=True)

        self.v_scroll2.config(command=self.tree2.yview)
        self.h_scroll2.config(command=self.tree2.xview)
        
        self.tree2.heading("Park", text="국립공원명")
        self.tree2.heading("Year", text="발견 연도")
        self.tree2.heading("Species", text="기준국명")
        self.tree2.heading("SciName", text="기준학명")
        self.tree2.heading("Task", text="발견 과제")
        self.tree2.heading("Count", text="개체수")
        self.tree2.heading("Endangered", text="멸종위기등급")
        self.tree2.heading("Alien", text="교란종여부")
        
        # 열 크기 조절 지원 (가로 스크롤을 위해 최소 너비 확보)
        self.tree2.column("Park", width=120, anchor=CENTER, stretch=False, minwidth=100)
        self.tree2.column("Year", width=80, anchor=CENTER, stretch=False, minwidth=60)
        self.tree2.column("Species", width=180, anchor=W, stretch=False, minwidth=150)
        self.tree2.column("SciName", width=200, anchor=W, stretch=False, minwidth=150)
        self.tree2.column("Task", width=200, anchor=W, stretch=True, minwidth=200)
        self.tree2.column("Count", width=80, anchor=CENTER, stretch=False, minwidth=60)
        self.tree2.column("Endangered", width=100, anchor=CENTER, stretch=False, minwidth=100)
        self.tree2.column("Alien", width=80, anchor=CENTER, stretch=False, minwidth=80)

    def update_progress_ui(self, percent):
        """
        데이터 처리 진행률을 상태바에 업데이트합니다.
        """
        self.progress_bar['value'] = percent
        if percent < 100:
            self.progress_lbl.config(text=f"{percent}% 데이터 취합 및 정제 중...")
        else:
            self.progress_lbl.config(text=f"{percent}% 완료되었습니다!")

    def load_data(self):
        """
        사용자가 파일 탐색기에서 엑셀/CSV 파일을 선택하면 데이터 처리를 시작합니다.
        """
        file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx;*.xls"), ("CSV Files", "*.csv")])
        if not file_path: return

        self.load_btn.config(state="disabled")
        self.status_lbl.config(text="데이터를 읽어오는 중입니다. 파일 크기에 따라 시간이 소요됩니다...", bootstyle="warning")
        self.update_progress_ui(0)

        threading.Thread(target=self._process_data_thread, args=(file_path,), daemon=True).start()

    def _process_data_thread(self, file_path):
        """
        백그라운드에서 엑셀 데이터를 읽고 정제하는 핵심 로직입니다.
        """
        try:
            self.root.after(0, self.update_progress_ui, 5)

            ext = os.path.splitext(file_path)[-1].lower()
            
            if ext == '.csv': 
                try:
                    self.df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)
                except UnicodeDecodeError:
                    self.df = pd.read_csv(file_path, encoding='cp949', low_memory=False)
            else: 
                xls = pd.ExcelFile(file_path, engine='openpyxl')
                target_sheets = ["sheet1", "sheet2", "sheet3", "고등균류", "리스트"]
                valid_sheets = [s for s in xls.sheet_names if s in target_sheets]
                
                if not valid_sheets:
                    valid_sheets = xls.sheet_names
                
                df_list = []
                for sheet in valid_sheets:
                    temp_df = pd.read_excel(xls, sheet_name=sheet)
                    df_list.append(temp_df)
                
                self.df = pd.concat(df_list, ignore_index=True)

            self.root.after(0, self.update_progress_ui, 30)

            cols = self.df.columns.tolist()
            
            # 필수 열 검사
            base_required = ['국립공원명', '기준국명']
            if not all(col in cols for col in base_required):
                if '국명' in cols and '국립공원명' in cols:
                    self.df.rename(columns={'국명': '기준국명'}, inplace=True)
                else:
                    self.root.after(0, lambda: messagebox.showerror("오류", f"필수 열이 없습니다: {base_required} 또는 ['국립공원명', '국명']"))
                    self.root.after(0, lambda: self.status_lbl.config(text="데이터 로드 실패", bootstyle="danger"))
                    self.root.after(0, lambda: self.load_btn.config(state="normal"))
                    return

            # 시간 데이터 인식
            time_candidates = ['연도', '날짜', '조사일', '조사일시', '일시', '조사일자', '년도']
            self.time_col = next((c for c in time_candidates if c in cols), None)
            
            if not self.time_col:
                self.root.after(0, lambda: messagebox.showerror("오류", f"시간 정보가 없습니다. 엑셀에 {time_candidates} 중 하나가 있어야 합니다."))
                self.root.after(0, lambda: self.status_lbl.config(text="시간 정보 누락", bootstyle="danger"))
                self.root.after(0, lambda: self.load_btn.config(state="normal"))
                return

            self.task_col = '과제명' if '과제명' in self.df.columns else '과제' if '과제' in self.df.columns else None
            
            # 메인 데이터에서 기준학명 또는 학명 열 인식
            self.sci_col = '기준학명' if '기준학명' in cols else '학명' if '학명' in cols else None
            
            self.root.after(0, self.update_progress_ui, 50)
            
            raw_years = self.df[self.time_col].astype(str).str.extract(r'(\d{4})')[0]
            self.df['연도_temp'] = pd.to_numeric(raw_years, errors='coerce')
            self.df = self.df[(self.df['연도_temp'] >= 1900) & (self.df['연도_temp'] <= self.current_year)]
            self.df['연도'] = self.df['연도_temp'].astype(int).astype(str)
            
            self.df = self.df.dropna(subset=['연도', '국립공원명', '기준국명'])

            # 오류종 및 공원명없음 제거 처리
            self.df = self.df[~self.df['국립공원명'].astype(str).str.contains('공원명없음', na=False)]
            self.df = self.df[~self.df['기준국명'].astype(str).str.contains('오류종', na=False)]
            self.df['기준국명'] = self.df['기준국명'].astype(str).str.strip()

            self.df = self.df.drop_duplicates()

            # ★ 버그 수정: 쉼표와 공백을 완전히 제거한 후 숫자 추출 ★
            if self.count_col in self.df.columns:
                clean_counts = self.df[self.count_col].astype(str).str.replace(',', '', regex=False).str.replace(' ', '', regex=False)
                extracted_counts = clean_counts.str.extract(r'(\d+)')[0]
                self.df[self.count_col] = pd.to_numeric(extracted_counts, errors='coerce').fillna(0)

            self.root.after(0, self.update_progress_ui, 80)

            agg_dict = {}
            if self.task_col:
                agg_dict[self.task_col] = lambda x: ', '.join(sorted(set(x.dropna().astype(str))))
            
            if self.count_col in self.df.columns:
                agg_dict[self.count_col] = 'sum'
                
            # 학명 열이 존재하면 그룹화 시 첫 번째 값 유지
            if self.sci_col:
                agg_dict[self.sci_col] = 'first'

            if agg_dict:
                self.df = self.df.groupby(['국립공원명', '연도', '기준국명'], as_index=False).agg(agg_dict)
            else:
                self.df = self.df.drop_duplicates(subset=['국립공원명', '연도', '기준국명'])

            self.root.after(0, self._finalize_loading)

        except Exception as e:
            self.root.after(0, lambda err=e: messagebox.showerror("오류", f"파일 처리 중 문제 발생:\n{err}"))
            self.root.after(0, lambda: self.status_lbl.config(text="데이터 로드 실패", bootstyle="danger"))
            self.root.after(0, lambda: self.load_btn.config(state="normal"))

    def _finalize_loading(self):
        self.update_progress_ui(100)
        
        # 공원 목록 업데이트
        park_list = sorted(self.df['국립공원명'].unique().tolist())
        self.park_combo_tab2['values'] = ["전체 국립공원"] + park_list
        self.park_combo_tab2.current(0)
        
        # 종명 목록 업데이트 (콤보박스 자동완성용 - 국명 및 학명 모두 포함)
        kor_names = self.df['기준국명'].dropna().astype(str).unique().tolist()
        sci_names = []
        if self.sci_col and self.sci_col in self.df.columns:
            sci_names = self.df[self.sci_col].dropna().astype(str).unique().tolist()
            
        combined_species = set(kor_names + sci_names)
        # '-' 같은 무의미한 빈칸 값은 제외
        self.all_species = sorted([s for s in combined_species if str(s).strip() and str(s).strip() != '-'])
        self.species_combo['values'] = self.all_species

        msg = f"✅ 파일 불러오기 완료! (유효 데이터: {len(self.df):,}건)"
        self.status_lbl.config(text=msg, bootstyle="success")
        
        self.load_btn.config(state="normal")

    def search_species(self):
        if self.df is None: return

        selected_park = self.park_combo_tab2.get()
        search_term = self.species_combo.get().strip()

        if not search_term: return

        # 국명 또는 학명에 검색어가 포함된 데이터 필터링 (대소문자 무시)
        mask = self.df['기준국명'].str.contains(search_term, na=False, case=False)
        if self.sci_col and self.sci_col in self.df.columns:
            mask = mask | self.df[self.sci_col].astype(str).str.contains(search_term, na=False, case=False)
            
        search_df = self.df[mask]
        
        if selected_park != "전체 국립공원":
            search_df = search_df[search_df['국립공원명'] == selected_park]

        search_df = search_df.sort_values(by=['기준국명', '연도', '국립공원명'], ascending=[True, False, True])
        self.last_search_df = search_df

        for item in self.tree2.get_children(): 
            self.tree2.delete(item)

        recent_year_val = self.df['연도'].max() if selected_park == "전체 국립공원" else self.df[self.df['국립공원명'] == selected_park]['연도'].max()
        
        has_recent = False
        if not search_df.empty:
            has_recent = (search_df['연도'] == str(recent_year_val)).any()

        self.tab2_export_data = []
        solid_line = "━" * 50
        
        previous_species = "NOT_FOUND_MSG" if not has_recent else None

        if not has_recent:
            msg = f"{recent_year_val}년에 출현 기록 없음"
            park_display = selected_park if selected_park != "전체 국립공원" else "-"
            # 빈칸 채우기용 (총 8개 컬럼)
            self.tree2.insert("", "end", values=(park_display, "-", msg, "-", "-", "-", "-", "-"))
            
            sep_row = {
                "국립공원명": park_display,
                "연도": "-",
                "기준국명": msg,
                "기준학명": "-",
                "발견 과제": "-",
                "개체수": "-",
                "멸종위기등급": "-",
                "교란종여부": "-"
            }
            if not self.task_col: del sep_row["발견 과제"]
            if self.count_col not in self.df.columns: del sep_row["개체수"]
            self.tab2_export_data.append(sep_row)

        if search_df.empty:
            messagebox.showinfo("결과", f"'{search_term}' 출현 기록이 전혀 없습니다.")
            return

        for _, row in search_df.iterrows():
            current_species = row['기준국명']
            task_info = row[self.task_col] if self.task_col else "-"
            count_info = int(row[self.count_col]) if self.count_col in self.df.columns else "-"
            
            # 메인 데이터에서 기준학명 읽어오기
            sci_info = row[self.sci_col] if self.sci_col and self.sci_col in row and pd.notna(row[self.sci_col]) else "-"
            
            # 기준 DB 정보 가져오기 (멸종위기,교란종)
            endangered_status, alien_status = self._get_species_info(current_species)

            if previous_species is not None and previous_species != current_species:
                self.tree2.insert("", "end", values=(solid_line, solid_line, solid_line, solid_line, solid_line, solid_line, solid_line, solid_line))
                
                sep_row = {
                    "국립공원명": solid_line,
                    "연도": solid_line,
                    "기준국명": solid_line,
                    "기준학명": solid_line,
                    "발견 과제": solid_line,
                    "개체수": solid_line,
                    "멸종위기등급": solid_line,
                    "교란종여부": solid_line
                }
                if not self.task_col: del sep_row["발견 과제"]
                if self.count_col not in self.df.columns: del sep_row["개체수"]
                self.tab2_export_data.append(sep_row)
            
            # Treeview 데이터 삽입
            self.tree2.insert("", "end", values=(row['국립공원명'], row['연도'], current_species, sci_info, task_info, count_info, endangered_status, alien_status))
            
            export_row = {
                "국립공원명": row['국립공원명'],
                "연도": row['연도'],
                "기준국명": current_species,
                "기준학명": sci_info,
                "발견 과제": task_info,
                "개체수": count_info,
                "멸종위기등급": endangered_status,
                "교란종여부": alien_status
            }
            if not self.task_col: del export_row["발견 과제"]
            if self.count_col not in self.df.columns: del export_row["개체수"]
            
            self.tab2_export_data.append(export_row)
            previous_species = current_species
            
        self.status_lbl.config(text=f"🔍 검색 완료: 총 {len(search_df)}건", bootstyle="info")

    def export_search_results(self):
        if not self.tab2_export_data:
            messagebox.showwarning("경고", "먼저 출현 기록을 검색해주세요.")
            return
        
        search_term = self.species_combo.get().strip()
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"검색결과_{search_term}.xlsx", filetypes=[("Excel Files", "*.xlsx")])
        
        if save_path:
            export_df = pd.DataFrame(self.tab2_export_data)
            export_df.to_excel(save_path, index=False)
            messagebox.showinfo("성공", "검색 결과가 엑셀로 저장되었습니다.")

if __name__ == "__main__":
    app_root = tb.Window(themename="sandstone")
    app = ModernEcoAnalyzer(app_root)
    app_root.mainloop()
