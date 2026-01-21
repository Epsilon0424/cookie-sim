import time
import html as _html
import streamlit as st
import pandas as pd
import cookie_simulator as sim

st.set_page_config(page_title="THE ABYSS COOKIE LAB", layout="wide")
STEP_FIXED = 2

def render_table_card(title: str, rows: list[tuple[str, str]]):
    if not rows:
        return False

    with st.container(border=True):
        st.markdown(f'<div class="h-title">{title}</div>', unsafe_allow_html=True)
        df = pd.DataFrame(rows, columns=["항목", "값"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    return True

def render_cards_flow(cards, per_row=3):
    i = 0
    while i < len(cards):
        chunk = cards[i:i+per_row]
        cols = st.columns(len(chunk), gap="small")
        for col, render_fn in zip(cols, chunk):
            with col:
                render_fn()
        i += per_row

st.markdown(
"""
<style>
/* =====================================================
   0) Font (Pretendard) + Variables
===================================================== */
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css");

:root{
  /* Font */
  --FONT_FAMILY: "Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", "Helvetica Neue",
                 Arial, sans-serif;

  --FS_APP: 14px; 
  --FS_XS: 11px;
  --FS_SM: 12px;
  --FS_MD: 13px;
  --FS_LG: 16px;
  --FS_XL: 19px;

  --FW_R: 500;
  --FW_M: 600;
  --FW_B: 700;
  --FW_XB: 800;

  /* Page */
  --PAGE_BG: #f3f4f6;

  /* Outer shell */
  --SHELL_BG: #f9fafb;
  --SHELL_RADIUS: 16px;
  --SHELL_SHADOW: 0 8px 24px rgba(0,0,0,0.06);

  /* Panels (선택/결과) */
  --PANEL_BG: #f3f4f6;
  --PANEL_BORDER: #eef2f7;
  --PANEL_RADIUS: 14px;
  --PANEL_PAD: 18px;

  /* Cards */
  --CARD_BG: #ffffff;
  --CARD_RADIUS: 14px;
  --CARD_SHADOW: 0 8px 24px rgba(0,0,0,0.06);

  /* Selectbox */
  --SEL_H: 34px;
  --SEL_FONT: 13px;
  --MENU_FONT: 12px;

  /* Layout */
  --COL_GAP: 1.0rem;
  --TAB_GAP: 10px;

  /* Accent */
  --accent: #ff3434;
  --accent-soft: rgba(255,52,52,0.10);

  /* Progress */
  --PROG_H: 16px;
  --PROG_BG: #e5e7eb;
  --PROG_BORDER: #d1d5db;
  --PROG_FG1: #4b5563;   /* 다크 그레이 */
  --PROG_FG2: #111827;   /* 더 진한 그레이 */
}

/* =====================================================
   1) Global font apply
===================================================== */
html, body, [data-testid="stAppViewContainer"]{
  font-family: var(--FONT_FAMILY) !important;
  font-size: var(--FS_APP) !important;
  background: var(--PAGE_BG) !important;
}
[data-testid="stAppViewContainer"] *{
  font-family: var(--FONT_FAMILY) !important;
}

/* Main container */
section.main > div.block-container,
[data-testid="stMainBlockContainer"],
[data-testid="stAppViewContainer"] .block-container{
  max-width: 1400px !important;
  margin-left: auto !important;
  margin-right: auto !important;
  padding-top: 2.6rem !important;
  padding-bottom: 3.2rem !important;
  padding-left: 2.2rem !important;
  padding-right: 2.2rem !important;
}

/* Header */
header[data-testid="stHeader"]{ background: transparent !important; }

/* =====================================================
   2) Outer shell
===================================================== */
.st-key-outer_shell{
  background: var(--SHELL_BG) !important;
  border: 0 !important;
  border-radius: var(--SHELL_RADIUS) !important;
  box-shadow: var(--SHELL_SHADOW) !important;
  padding: 18px !important;
}
.st-key-outer_shell > div{
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  padding: 0 !important;
}

/* =====================================================
   3) Layout columns
===================================================== */
div[data-testid="stHorizontalBlock"]{
  gap: var(--COL_GAP) !important;
  align-items: flex-start !important;
}

/* =====================================================
   4) Default cards (border=True 컨테이너 공통)
===================================================== */
div[data-testid="stVerticalBlockBorderWrapper"]{
  background: var(--CARD_BG) !important;
  border: none !important;
  border-radius: var(--CARD_RADIUS) !important;
  box-shadow: var(--CARD_SHADOW) !important;
  padding: 18px 18px 14px 18px !important;
}

/* panel_select/result는 카드 스타일 제외 */
.st-key-panel_select,
.st-key-panel_result{
  background: var(--PANEL_BG) !important;
  border: 1px solid var(--PANEL_BORDER) !important;
  border-radius: var(--PANEL_RADIUS) !important;
  box-shadow: none !important;
  padding: var(--PANEL_PAD) !important;
}
.st-key-panel_select > div,
.st-key-panel_result > div{
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  margin-top: 0 !important;
  padding-top: 0 !important;
}

/* =====================================================
   5) Typography (크기/두께만 튜닝)
===================================================== */
.h-title{
  font-size: var(--FS_LG);
  font-weight: var(--FW_XB);
  letter-spacing: -0.2px;
  margin: 0 0 2px 0;
}
.title-card .h-title{
  font-size: var(--FS_XL);
  letter-spacing: -0.35px;
}
/* 타이틀 카드 안내문(2줄) = Notes 본문 크기랑 동일하게 */
.title-card .h-sub,
.title-card .h-meta{
  font-size: var(--FS_SM) !important;   /* Notes와 동일 */
  line-height: 1.55 !important;        /* Notes와 동일한 느낌 */
  font-weight: 600 !important;         /* Notes처럼 가볍게 */
  color: #6b7280;
}

/* metric */
div[data-testid="stMetricLabel"]{
  font-size: var(--FS_SM) !important;
  font-weight: var(--FW_B) !important;
  color: #6b7280 !important;
}
div[data-testid="stMetricValue"]{
  font-size: 20px !important;
  font-weight: var(--FW_XB) !important;
  letter-spacing: -0.2px !important;
}

/* tabs */
:root{ --TAB_FONT: 13px; --TAB_WEIGHT: 750; }
div[data-testid="stTabs"] button[data-baseweb="tab"],
div[data-testid="stTabs"] button[data-baseweb="tab"] *{
  font-size: var(--TAB_FONT) !important;
  font-weight: var(--TAB_WEIGHT) !important;
}
[data-testid="stCaptionContainer"]{
  font-size: var(--FS_SM) !important;
  line-height: 1.45 !important;
}

/* title card */
.title-card{
  background: var(--SHELL_BG) !important;
  border-radius: var(--CARD_RADIUS) !important;
  box-shadow: var(--CARD_SHADOW) !important;
  padding: 14px 18px !important;
  margin: 0 0 14px 0 !important;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.title-card .h-title,
.title-card .h-sub,
.title-card .h-meta{ margin: 0 !important; }
.title-card{ gap: 3px; }

/* =====================================================
   6) Select UI
===================================================== */
.ctl-label{
  font-size: var(--FS_MD) !important;
  font-weight: var(--FW_XB) !important;
  color: #374151;
  margin: 10px 0 6px 0;
}

/* 닫힌 상태 select 박스 */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
  min-height: var(--SEL_H) !important;
  height: var(--SEL_H) !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  background: #e5e7eb !important;
  border: 0 !important;
  outline: none !important;
  box-shadow: none !important;
  display: flex !important;
  align-items: center !important;
  border-radius: 10px !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover{
  border: 0 !important;
  outline: none !important;
  box-shadow: none !important;
}
div[data-testid="stSelectbox"] div[role="combobox"]{
  min-height: var(--SEL_H) !important;
  height: var(--SEL_H) !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  display: flex !important;
  align-items: center !important;
  background: transparent !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  font-size: var(--SEL_FONT) !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] *{
  font-size: var(--SEL_FONT) !important;
  line-height: 1.5 !important;
  font-weight: var(--FW_M) !important;
}

/* 메뉴(팝업) 전체 */
div[data-baseweb="popover"] *{
  font-family: var(--FONT_FAMILY) !important;
}

/* 옵션 리스트(열린 상태) 폰트 크기/두께 */
div[data-baseweb="menu"] *,
[role="listbox"] *,
li[role="option"]{
  font-size: var(--MENU_FONT) !important; 
  line-height: 1.35 !important;
}

/* 옵션 한 줄 높이(간격)도 바꾸고 싶으면 */
li[role="option"]{
  padding-top: 8px !important;
  padding-bottom: 8px !important;
}

/* 선택된 옵션(하이라이트) */
li[role="option"][aria-selected="true"]{
  font-weight: var(--FW_B) !important;
}

/* Party(파티 슬롯 1/2) 간격 줄이기 */
:root{ --PARTY_GAP: 6px; }

/* 파티 그룹 안의 selectbox elementContainer는 밑간격을 0으로 */
.st-key-party_group div[data-testid="stElementContainer"]:has(div[data-testid="stSelectbox"]){
  margin-bottom: 0 !important;
}

/* "첫번째 selectbox" 바로 다음에 오는 "두번째 selectbox"만 위로 당김 */
.st-key-party_group
  div[data-testid="stElementContainer"]:has(div[data-testid="stSelectbox"])
  + div[data-testid="stElementContainer"]:has(div[data-testid="stSelectbox"]){
  margin-top: calc(var(--PARTY_GAP) * -1) !important;
}

/* =====================================================
   7) Buttons
===================================================== */
.stButton > button[kind="primary"]{
  border-radius: 12px;
  height: 40px;
  font-weight: var(--FW_XB);
  background: #ff4b4b !important;
  border: none !important;
  color: #ffffff !important;
  box-shadow: 0 8px 18px rgba(255,75,75,0.20);
}
.stButton > button[kind="primary"]:hover{ background: #ff3434 !important; }
.stButton > button:not([kind="primary"]){
  border-radius: 12px;
  height: 40px;
  font-weight: var(--FW_B);
  background: #ffffff !important;
  border: 1px solid #e5e7eb !important;
  color: #111827 !important;
}
.stButton > button:not([kind="primary"]):hover{
  border-color: #d1d5db !important;
  background: #f9fafb !important;
}
.st-key-run_btn button,
.st-key-run_btn button *{
  font-weight: 700 !important;
}

/* =====================================================
   8) Divider + Tabs spacing
===================================================== */
div[data-testid="stMarkdownContainer"] hr.u-divider{
  border: none !important;
  border-top: 1px solid #e5e7eb !important;
  margin-top: -4px !important;
  margin-bottom: 12px !important;
}
div[data-testid="stTabs"] div[data-baseweb="tab-panel"]{ padding-top: var(--TAB_GAP) !important; }
div[data-testid="stTabs"] div[data-baseweb="tab-panel"] > div{
  margin-top: 0 !important;
  padding-top: 0 !important;
}

/* =====================================================
   9) Tables / pills
===================================================== */
.stat-wrap{ margin: 0px 0 14px 0; }
.stat-pill{
  display: block;
  width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  padding: 10px 12px;
  font-size: var(--FS_SM);
  font-weight: 800 !important;
  line-height: 1.2;
  color: #111827;
  box-shadow: 0 4px 10px rgba(0,0,0,0.06);
  margin: 0 0 8px 0;
}

:root{ --ROW_H: 32px; --CELL_PX: 12px; }

.u-table{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
  background: #ffffff;
  border: 0.5px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 6px 16px rgba(0,0,0,0.03);
}

/* 공통 */
.u-table thead th,
.u-table tbody td{
  height: var(--ROW_H);
  padding: 0 var(--CELL_PX);
  line-height: var(--ROW_H);
  vertical-align: middle;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: var(--FS_SM);
  color: #111827;
}

/* 헤더만 굵게 */
.u-table thead th{
  background: #f9fafb;
  color: #374151;
  font-weight: 800 !important; /* 또는 var(--FW_XB) */
  border-bottom: 1px solid #e5e7eb;
}

/* 본문은 얇게 */
.u-table tbody td{
  font-weight: 400 !important;
  border-bottom: 1px solid #eef2f7;
}

.u-table tbody td:first-child{
  font-weight: var(--FW_B) !important;   /* 700 */
  color: #374151;
}

.u-table tbody tr:last-child td{ border-bottom: none; }
.u-empty{ font-size: var(--FS_SM); color: #6b7280; padding: 10px 2px 0 2px; }

/* 테이블 헤더 밑줄(강조) */
thead tr th{ border-bottom: 2px solid rgba(255,52,52,0.18) !important; }

/* =====================================================
   10) Progress bar (+ shimmer)
===================================================== */
.prog-wrap{
  width: 100%;
  height: 18px;
  border-radius: 5px;
  background: #f1f5f9;
  border: 1px solid #e5e7eb;
  overflow: hidden;
  position: relative;
  box-shadow: 0 4px 10px rgba(0,0,0,0.06);
}

.prog-bar{
  height: 100%;
  width: 0%;
  background: #4b5563;
  transition: width 120ms ease;
  position: relative;
  overflow: hidden;
}

/* Shimmer overlay */
.prog-bar::after{
  content:"";
  position:absolute;
  inset:0;
  background: linear-gradient(
    120deg,
    rgba(255,255,255,0) 0%,
    rgba(255,255,255,0.35) 45%,
    rgba(255,255,255,0) 90%
  );
  transform: translateX(-60%);
  animation: prog_shimmer 1.15s ease-in-out infinite;
  opacity: 0.75;
  pointer-events: none;
}

@keyframes prog_shimmer{
  0%   { transform: translateX(-60%); }
  100% { transform: translateX(160%); }
}

.prog-text{
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: 0.2px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.25);
  user-select: none;
}

.prog-area{
  padding: 0 !important;
  margin: 0px 0 8px 0 !important;
}

/* =====================================================
   11) Responsive grids
===================================================== */
.summary-grid{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
  align-items: start;
  margin-top: 0 !important;
}
.stat-grid{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
  align-items: start;
  margin-top: 0 !important;
}
.stat-grid .stat-wrap{ margin: 0 !important; }

@media (max-width: 980px){
  .summary-grid{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .summary-grid .md-span-2{ grid-column: 1 / -1; }

  .stat-grid{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stat-grid .span-2{ grid-column: 1 / -1; }
}
@media (max-width: 640px){
  .summary-grid{ grid-template-columns: 1fr; }
  .summary-grid .md-span-2{ grid-column: auto; }

  .stat-grid{ grid-template-columns: 1fr; }
  .stat-grid .span-2{ grid-column: auto; }
}

/* =====================================================
   Bottom global note (outer 밖, title-card 스타일)
===================================================== */
.global-note{
  background: var(--SHELL_BG) !important;
  border-radius: var(--CARD_RADIUS) !important;
  box-shadow: var(--CARD_SHADOW) !important;
  padding: 14px 18px !important;
  margin: 0px 0 0 0 !important;
}
.global-note .note-title{
  font-size: var(--FS_MD);
  font-weight: var(--FW_XB);
  color: #111827;
  margin: 0 0 6px 0;
}
.global-note .note-text{
  font-size: var(--FS_SM);
  font-weight: 400;
  color: #4b5563;
  line-height: 1.55;
  margin: 0;
}
.global-note .note-text b{
  font-weight: var(--FW_B);
  color: #374151;
}
.global-note .note-text code{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono","Courier New", monospace;
  font-size: calc(var(--FS_SM) - 1px);
  background: #f9fafb;
  border: 1px solid #eef2f7;
  padding: 1px 6px;
  border-radius: 8px;
}
</style>
""",
unsafe_allow_html=True,
)

import time
import html as _html
import streamlit as st
import pandas as pd
import cookie_simulator as sim


# =====================================================
# 유틸: 한글 매핑
# =====================================================
def _kr_or_key(mapping: dict, k: str) -> str:
    return mapping.get(k, k)


# =====================================================
# 파티 슬롯 selectbox 기본값 1회만 넣기
# =====================================================
def init_once(key: str, value):
    flag = f"_init_once__{key}"
    if flag in st.session_state:
        return
    st.session_state[key] = value
    st.session_state[flag] = True


def norm_none(x: str) -> str:
    return "" if (x is None or x == "없음") else x


# =====================================================
# 유틸: DF -> HTML Table (n컬럼 지원, tooltip 포함)
# =====================================================
def hide_breeder_when_not_wind(cookie_name: str, options: list[str]) -> list[str]:
    # 윈드파라거스일 때만 "믿음직한 브리더" 노출
    if cookie_name == "윈드파라거스 쿠키":
        return options
    return [x for x in options if "믿음직한 브리더" not in str(x)]


def df_to_html_table(
    df: pd.DataFrame,
    small: bool = False,
    col_ratio=(0.38, 0.62),
    col_widths=None
) -> str:
    if df is None or df.empty:
        return ""

    safe = df.copy().reset_index(drop=True)

    def cell_html(x):
        s = "" if x is None else str(x)
        esc = _html.escape(s)
        tip = _html.escape(s)
        return f'<td title="{tip}">{esc}</td>'

    cls = "u-table small" if small else "u-table"
    ncol = len(safe.columns)

    widths = None
    if col_widths is not None and isinstance(col_widths, (list, tuple)) and len(col_widths) == ncol:
        widths = list(col_widths)
    elif ncol == 2 and col_ratio is not None and len(col_ratio) == 2:
        widths = [float(col_ratio[0]), float(col_ratio[1])]
    else:
        widths = [1.0 / ncol] * ncol

    ssum = sum(widths) if widths else 1.0
    widths = [(w / ssum) for w in widths]

    col_tags = "".join([f"<col style='width:{int(w*100)}%'>" for w in widths])
    colgroup = f"<colgroup>{col_tags}</colgroup>"

    ths = "".join([f"<th>{_html.escape(str(c))}</th>" for c in safe.columns])

    rows_html = []
    for _, row in safe.iterrows():
        tds = "".join([cell_html(row[c]) for c in safe.columns])
        rows_html.append(f"<tr>{tds}</tr>")

    body = "".join(rows_html)
    return f"""
<table class="{cls}">
  {colgroup}
  <thead><tr>{ths}</tr></thead>
  <tbody>{body}</tbody>
</table>
""".strip()


def render_labeled_table(
    title: str,
    df: pd.DataFrame,
    small: bool = False,
    col_ratio=(0.38, 0.62),
    col_widths=None
):
    pill = f'<div class="stat-pill">{_html.escape(title)}</div>'

    if df is None or df.empty:
        body = '<div class="u-empty">표시할 항목 없음</div>'
    else:
        body = df_to_html_table(df, small=small, col_ratio=col_ratio, col_widths=col_widths)

    html = f"""
    <div class="stat-wrap">
      {pill}
      {body}
    </div>
    """.strip()

    st.markdown(html, unsafe_allow_html=True)


# =====================================================
# 최종스탯 grid 전용: HTML 생성/렌더
# =====================================================
def labeled_table_html(title: str, df: pd.DataFrame, small: bool = False, col_ratio=(0.38, 0.62), col_widths=None) -> str:
    pill = f'<div class="stat-pill">{_html.escape(title)}</div>'
    if df is None or df.empty:
        body = '<div class="u-empty">표시할 항목 없음</div>'
    else:
        body = df_to_html_table(df, small=small, col_ratio=col_ratio, col_widths=col_widths)
    return f'<div class="stat-wrap">{pill}{body}</div>'


def labeled_table_html_optional(
    title: str,
    df: pd.DataFrame,
    small: bool = False,
    col_ratio=(0.38, 0.62),
    col_widths=None
) -> str:
    if df is None or df.empty:
        return ""

    pill = f'<div class="stat-pill">{_html.escape(title)}</div>'
    body = df_to_html_table(df, small=small, col_ratio=col_ratio, col_widths=col_widths)
    return f'<div class="stat-wrap">{pill}{body}</div>'


def render_final_stats_grid(atk_df, crit_df, common_df, skill_df, surv_df, amp_df):
    items = []

    def add(title, df):
        block = labeled_table_html_optional(title, df, small=False)
        if block:
            items.append(f"<div>{block}</div>")

    add("공격력", atk_df)
    add("치명타", crit_df)
    add("피해 보정", common_df)
    add("스킬 타입 피해 증가", skill_df)
    add("(파티) 보호막 / 방어", surv_df)
    add("(파티) 버프 / 디버프 증폭", amp_df)

    html = "<div class='stat-grid'>" + "".join(items) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


# =====================================================
# 요약표(잠재/조각)
# =====================================================
def pretty_potentials(pot: dict) -> pd.DataFrame:
    rows = []
    for k, v in (pot or {}).items():
        try:
            iv = int(v)
        except Exception:
            continue
        if iv >= 1:
            rows.append({"항목": _kr_or_key(getattr(sim, "POTENTIAL_KR", {}), k), "값": iv})
    return pd.DataFrame(rows, columns=["항목", "값"])


def pretty_shards(shards: dict) -> pd.DataFrame:
    rows = []
    for k, v in (shards or {}).items():
        try:
            iv = int(v)
        except Exception:
            continue
        if iv >= 1:
            rows.append({"항목": _kr_or_key(getattr(sim, "SHARD_KR", {}), k), "값": iv})
    return pd.DataFrame(rows, columns=["항목", "값"])


# =====================================================
# 사이클 breakdown 표 (비율 포함)
# =====================================================
def cycle_breakdown_df(cb: dict) -> pd.DataFrame:
    name_map = {
        "breakdown_basic": "기본공격",
        "breakdown_special": "특수스킬",
        "breakdown_ult": "궁극기",
        "breakdown_charge": "차징",
        "breakdown_passive": "패시브",
        "breakdown_proc": "발동(세트/효과)",
        "breakdown_strike": "속성강타",
        "breakdown_unique": "유니크",
    }

    rows = []
    total = 0.0
    for k, v in (cb or {}).items():
        if not str(k).startswith("breakdown_"):
            continue
        try:
            fv = float(v)
        except Exception:
            continue
        if abs(fv) < 1e-12:
            continue
        total += fv
        rows.append((name_map.get(k, k.replace("breakdown_", "")), fv))

    if not rows or total == 0:
        return pd.DataFrame(columns=["항목", "딜", "비율(%)"])

    out = []
    for label, fv in sorted(rows, key=lambda x: x[1], reverse=True):
        pct = fv / total * 100.0
        out.append({"항목": label, "딜": f"{fv:,.4f}", "비율(%)": f"{pct:.2f}"})
    return pd.DataFrame(out, columns=["항목", "딜", "비율(%)"])


# =====================================================
# 최종스탯 그룹 (0인 항목 제거)
# =====================================================
def build_stat_tables(stats: dict, cookie_name: str = "", party=None):
    stats = stats or {}
    party = party or []

    eff = sim.summarize_effective_stats(stats).get("numeric", {})

    def _f(d: dict, k: str, default=0.0) -> float:
        try:
            return float(d.get(k, default))
        except Exception:
            return float(default)

    def _fmt_num(x: float) -> str:
        if abs(x) >= 1000:
            s = f"{x:,.2f}"
            return s.rstrip("0").rstrip(".")
        s = f"{x:.4f}"
        return s.rstrip("0").rstrip(".")

    def _fmt_pct(x: float) -> str:
        return f"{x*100:.1f}%"

    def add_if_nonzero(rows, label, value_str, numeric_check, eps=1e-12):
        try:
            if abs(float(numeric_check)) < eps:
                return
        except Exception:
            return
        rows.append([label, value_str])

    # =========================
    # 공격력 (표시=합, 최종공격력 계산=곱환산)
    # =========================
    OA = _f(stats, "base_atk", 0.0) + _f(stats, "equip_atk_flat", 0.0)
    EA = _f(stats, "base_elem_atk", 0.0) + _f(stats, "elem_atk", 0.0)

    atk_pct_sum   = eff.get("atk_pct_sum", 0.0)         # 화면 표시용: 합(+)
    atk_pct_equiv = eff.get("atk_pct_equiv", 0.0)       # 최종공 계산용: 등가(%)
    final_atk_add = eff.get("final_atk_mult_add", 0.0)

    final_atk_input = (OA + EA) * (1.0 + atk_pct_equiv) * (1.0 + final_atk_add)

    atk_rows = []
    add_if_nonzero(atk_rows, "OA(기본공)", _fmt_num(OA), OA)
    add_if_nonzero(atk_rows, "EA(속성공)", _fmt_num(EA), EA)
    add_if_nonzero(atk_rows, "공격력%", _fmt_pct(atk_pct_sum), atk_pct_sum)
    add_if_nonzero(atk_rows, "공격력 증가%", _fmt_pct(final_atk_add), final_atk_add)
    add_if_nonzero(atk_rows, "최종 공격력", _fmt_num(final_atk_input), final_atk_input)
    atk_df = pd.DataFrame(atk_rows, columns=["항목", "값"])

    # =========================
    # 치명
    # =========================
    crit_rows = []
    add_if_nonzero(crit_rows, "치명타 확률", _fmt_pct(float(eff.get("eff_crit_rate", 0.0))), float(eff.get("eff_crit_rate", 0.0)))

    cd_eff = float(eff.get("eff_crit_dmg", 1.0))
    add_if_nonzero(crit_rows, "치명타 피해", _fmt_pct(cd_eff - 1.0), cd_eff - 1.0)
    crit_df = pd.DataFrame(crit_rows, columns=["항목", "값"])

    # =========================
    # 피해 보정
    # =========================
    common_rows = []
    add_if_nonzero(common_rows, "모든 속성 피해", _fmt_pct(float(eff.get("eff_all_elem_dmg", 0.0))), float(eff.get("eff_all_elem_dmg", 0.0)))
    add_if_nonzero(common_rows, "방어력 관통", _fmt_pct(float(eff.get("eff_armor_pen", 0.0))), float(eff.get("eff_armor_pen", 0.0)))

    add_if_nonzero(common_rows, "방어력 감소", _fmt_pct(float(eff.get("eff_def_reduction", 0.0))), float(eff.get("eff_def_reduction", 0.0)))
    add_if_nonzero(common_rows, "속성 내성 감소", _fmt_pct(float(eff.get("eff_elem_res_reduction", 0.0))), float(eff.get("eff_elem_res_reduction", 0.0)))
    add_if_nonzero(common_rows, "표식 저항 감소", _fmt_pct(float(eff.get("eff_mark_res_reduction", 0.0))), float(eff.get("eff_mark_res_reduction", 0.0)))

    add_if_nonzero(common_rows, "피해량", _fmt_pct(float(eff.get("dmg_bonus", 0.0))), float(eff.get("dmg_bonus", 0.0)))
    add_if_nonzero(common_rows, "최종 피해", _fmt_pct(float(eff.get("final_dmg_sum", 0.0))), float(eff.get("final_dmg_sum", 0.0)))
    add_if_nonzero(common_rows, "속성강타 피해", _fmt_pct(float(eff.get("element_strike_dmg", 0.0))), float(eff.get("element_strike_dmg", 0.0)))

    common_df = pd.DataFrame(common_rows, columns=["항목", "값"])

    # =========================
    # 스킬 타입 피해 증가
    # =========================
    skill_rows = []
    add_if_nonzero(skill_rows, "기본공격 피해", _fmt_pct(_f(stats, "basic_dmg", 0.0)), _f(stats, "basic_dmg", 0.0))
    add_if_nonzero(skill_rows, "특수스킬 피해", _fmt_pct(_f(stats, "special_dmg", 0.0)), _f(stats, "special_dmg", 0.0))
    add_if_nonzero(skill_rows, "궁극기 피해", _fmt_pct(_f(stats, "ult_dmg", 0.0)), _f(stats, "ult_dmg", 0.0))
    add_if_nonzero(skill_rows, "패시브 피해", _fmt_pct(_f(stats, "passive_dmg", 0.0)), _f(stats, "passive_dmg", 0.0))
    skill_df = pd.DataFrame(skill_rows, columns=["항목", "값"])

    # =========================
    # 보호막/방어
    # =========================
    surv_rows = []
    add_if_nonzero(surv_rows, "보호막 %", _fmt_pct(_f(stats, "shield_pct", 0.0)), _f(stats, "shield_pct", 0.0))
    add_if_nonzero(surv_rows, "방어력 %", _fmt_pct(_f(stats, "def_pct", 0.0)), _f(stats, "def_pct", 0.0))
    surv_df = pd.DataFrame(surv_rows, columns=["항목", "값"])

    # =========================
    # 버프/디버프 증폭
    # =========================
    def pick_num(*keys, default=0.0):
        for k in keys:
            if k in eff and eff.get(k) is not None:
                try:
                    return float(eff.get(k))
                except Exception:
                    pass
        for k in keys:
            if k in stats and stats.get(k) is not None:
                try:
                    return float(stats.get(k))
                except Exception:
                    pass
        return float(default)

    buff_amp = pick_num("party_buff_amp_total", "buff_amp_total")
    debuff_amp = pick_num("party_debuff_amp_total", "debuff_amp_total")

    amp_rows = []
    add_if_nonzero(amp_rows, "버프 증폭", _fmt_pct(buff_amp), buff_amp)
    add_if_nonzero(amp_rows, "디버프 증폭", _fmt_pct(debuff_amp), debuff_amp)
    amp_df = pd.DataFrame(amp_rows, columns=["항목", "값"])

    return atk_df, crit_df, common_df, skill_df, surv_df, amp_df


# =====================================================
#  추가: 장비 선택 모드/장비 위젯 키 (쿠키별 분리)
# =====================================================
def mode_key(kind: str) -> str:
    return f"mode_widget__{kind}"


def equip_key(kind: str) -> str:
    return f"equip_widget__{kind}"


# =====================================================
# 세션 상태 (쿠키별 widget key 분리)
# =====================================================
if "cookie" not in st.session_state:
    st.session_state.cookie = "멜랑크림 쿠키"
if "seaz" not in st.session_state:
    st.session_state.seaz = ""
if "party" not in st.session_state:
    st.session_state.party = []
if "best" not in st.session_state:
    st.session_state.best = None
if "best_kind" not in st.session_state:
    st.session_state.best_kind = None
if "last_run" not in st.session_state:
    st.session_state.last_run = None

if "mode" not in st.session_state:
    st.session_state.mode = "최적(자동)"
if "equip" not in st.session_state:
    st.session_state.equip = ""

if "_cookie_prev" not in st.session_state:
    st.session_state._cookie_prev = st.session_state.cookie


def kind_of(cookie_name: str) -> str:
    return {
        "윈드파라거스 쿠키": "wind",
        "멜랑크림 쿠키": "melan",
        "흑보리맛 쿠키": "bb",
        "이슬맛 쿠키": "isle",
        "샬롯맛 쿠키": "char",
    }.get(cookie_name, "char")


def seaz_key(kind: str) -> str:
    return f"seaz_widget__{kind}"


def party1_key(kind: str) -> str:
    return f"party_slot1__{kind}"


def party2_key(kind: str) -> str:
    return f"party_slot2__{kind}"


# =====================================================
# 상단 타이틀
# =====================================================
st.markdown("""
<div class="title-card">
  <div class="h-title">THE ABYSS COOKIE LAB</div>
  <div class="h-sub">쿠키 선택 → 장비 선택 모드/장비 선택 → 시즈나이트/파티 구성 → 실행</div>
</div>
""", unsafe_allow_html=True)


# =====================================================
# 레이아웃: 좌/우
# =====================================================
with st.container(key="outer_shell", border=False):
    left_col, right_col = st.columns([0.8, 2.4], gap="small")

    # =====================================================
    # 좌측: 선택
    # =====================================================
    with left_col:
        with st.container(key="panel_select", border=True):
            st.markdown('<div class="h-title">SELECT</div>', unsafe_allow_html=True)

            st.markdown('<div class="ctl-label">쿠키</div>', unsafe_allow_html=True)
            cookie_options = ["멜랑크림 쿠키", "윈드파라거스 쿠키", "흑보리맛 쿠키", "이슬맛 쿠키", "샬롯맛 쿠키"]

            if "cookie_widget" not in st.session_state:
                st.session_state.cookie_widget = st.session_state.cookie

            cookie = st.selectbox("쿠키", cookie_options, label_visibility="collapsed", key="cookie_widget")

            if cookie != st.session_state._cookie_prev:
                st.session_state.cookie = cookie
                st.session_state._cookie_prev = cookie

                st.session_state.seaz = ""
                st.session_state.party = []
                st.session_state.best = None
                st.session_state.best_kind = None
                st.session_state.last_run = None

                st.session_state.mode = "최적(자동)"
                st.session_state.equip = ""

                k2 = kind_of(cookie)
                st.session_state[seaz_key(k2)] = ""

                # kind별 파티 기본값 (역할 고정: 서폿1/스트1/딜러2)
                # - 딜러(멜랑/흑보리): 서폿(이슬/샬롯) + 스트(윈드) 고정
                # - 스트(윈드): 서폿(이슬/샬롯) 1명
                # - 서폿(이슬/샬롯): 스트(윈드) 고정
                if k2 in ("melan", "bb"):
                    st.session_state[party1_key(k2)] = "샬롯맛 쿠키"        # 서폿(선택)
                    st.session_state[party2_key(k2)] = "윈드파라거스 쿠키"  # 스트(고정)
                elif k2 == "wind":
                    st.session_state[party1_key(k2)] = "샬롯맛 쿠키"        # 서폿(선택)
                elif k2 == "isle":
                    st.session_state[party1_key(k2)] = "윈드파라거스 쿠키"  # 스트(고정)
                elif k2 == "char":
                    st.session_state[party1_key(k2)] = "윈드파라거스 쿠키"  # 스트(고정)

                st.session_state[mode_key(k2)] = "최적(자동)"
                st.session_state[equip_key(k2)] = ""
                st.rerun()

            k = kind_of(cookie)
            sk = seaz_key(k)
            p1k = party1_key(k)
            p2k = party2_key(k)
            mk = mode_key(k)
            ek = equip_key(k)

            # =====================================================
            # 장비 선택 모드
            # =====================================================
            st.markdown('<div class="ctl-label">장비 선택 모드</div>', unsafe_allow_html=True)

            mode_opts = ["최적(자동)", "선택(수동)"]
            if st.session_state.get(mk, "") not in mode_opts:
                st.session_state[mk] = mode_opts[0]

            mode = st.selectbox("장비 선택 모드", mode_opts, label_visibility="collapsed", key=mk)
            st.session_state.mode = mode

            equip_override = None

            # 샬롯/이슬은 장비를 해적셋으로 고정
            if cookie in ("이슬맛 쿠키", "샬롯맛 쿠키"):
                fixed_opts = ["전설의 유령해적 세트"]

                if st.session_state.get(ek, "") not in fixed_opts:
                    st.session_state[ek] = fixed_opts[0]
                st.session_state.equip = fixed_opts[0]
                equip_override = fixed_opts[0]

                if mode == "선택(수동)":
                    st.markdown('<div class="ctl-label">장비</div>', unsafe_allow_html=True)
                    st.selectbox("장비 선택", fixed_opts, label_visibility="collapsed", key=ek, disabled=True)

            else:
                # 나머지는 기존 로직 그대로 (최적/선택 모드)
                if mode == "선택(수동)":
                    st.markdown('<div class="ctl-label">장비</div>', unsafe_allow_html=True)

                    if cookie == "윈드파라거스 쿠키":
                        equip_options = (getattr(sim, "wind_allowed_equips", lambda: [""])() or [""])
                    elif cookie == "멜랑크림 쿠키":
                        equip_options = (getattr(sim, "melan_allowed_equips", lambda: [""])() or [""])
                    elif cookie == "흑보리맛 쿠키":
                        equip_options = (getattr(sim, "black_barley_allowed_equips", lambda: [""])() or [""])
                    else:
                        pass

                    if st.session_state.get(ek, "") not in equip_options:
                        st.session_state[ek] = equip_options[0]

                    equip = st.selectbox("장비 선택", equip_options, label_visibility="collapsed", key=ek)
                    st.session_state.equip = equip
                    equip_override = equip
                else:
                    st.session_state.equip = ""
                    equip_override = None

            # =====================================================
            # 시즈나이트/파티
            # =====================================================
            st.markdown('<div class="ctl-label">시즈나이트</div>', unsafe_allow_html=True)

            # -------------------------
            # 1) 윈드(스트)
            # -------------------------
            if cookie == "윈드파라거스 쿠키":
                seaz_options = (getattr(sim, "wind_allowed_seaz", lambda: [""])() or [""])
                seaz_options = hide_breeder_when_not_wind(cookie, seaz_options) or [""]

                if st.session_state.get(sk, "") not in seaz_options:
                    st.session_state[sk] = seaz_options[0]

                seaz = st.selectbox("시즈나이트 선택", seaz_options, label_visibility="collapsed", key=sk)
                st.session_state.seaz = seaz

                # 파티: 서폿 1명만 (이슬/샬롯)
                st.markdown('<div class="ctl-label">파티</div>', unsafe_allow_html=True)
                support_opts = ["이슬맛 쿠키", "샬롯맛 쿠키"]
                init_once(p1k, "샬롯맛 쿠키")
                if st.session_state.get(p1k, support_opts[0]) not in support_opts:
                    st.session_state[p1k] = support_opts[0]
                sup = st.selectbox("파티(서폿)", support_opts, label_visibility="collapsed", key=p1k)
                st.session_state.party = [sup]

            # -------------------------
            # 2) 멜랑/흑보리(딜러)
            # -------------------------
            elif cookie == "멜랑크림 쿠키":
                seaz_options = [x for x in getattr(sim, "SEAZNITES", {}).keys() if str(x).startswith("바닐라몬드:")]
                seaz_options = hide_breeder_when_not_wind(cookie, seaz_options) or [""]

                PREFERRED_SEAZ = "바닐라몬드:추격자의 결의"
                cur = st.session_state.get(sk, "")
                if (not cur) or (cur not in seaz_options):
                    st.session_state[sk] = PREFERRED_SEAZ if PREFERRED_SEAZ in seaz_options else seaz_options[0]

                seaz = st.selectbox("시즈나이트 선택", seaz_options, label_visibility="collapsed", key=sk)
                st.session_state.seaz = seaz

                with st.container(key="party_group", border=False):
                    st.markdown('<div class="ctl-label">파티</div>', unsafe_allow_html=True)

                    # 역할 고정: 서폿 1(이슬/샬롯 선택) + 스트 1(윈드 고정)
                    support_opts = ["이슬맛 쿠키", "샬롯맛 쿠키"]
                    init_once(p1k, "샬롯맛 쿠키")
                    if st.session_state.get(p1k, support_opts[0]) not in support_opts:
                        st.session_state[p1k] = support_opts[0]
                    sup = st.selectbox("파티(서폿)", support_opts, label_visibility="collapsed", key=p1k)

                    init_once(p2k, "윈드파라거스 쿠키")
                    st.selectbox("파티(스트)", ["윈드파라거스 쿠키"], label_visibility="collapsed", disabled=True, key=p2k)

                    st.session_state.party = [sup, "윈드파라거스 쿠키"]

            elif cookie == "흑보리맛 쿠키":
                seaz_options = (
                    getattr(sim, "black_barley_allowed_seaz", lambda: None)()
                    or [x for x in getattr(sim, "SEAZNITES", {}).keys() if str(x).startswith("페퍼루비:")]
                )
                seaz_options = hide_breeder_when_not_wind(cookie, seaz_options) or [""]

                PREFERRED_SEAZ = "페퍼루비:영예로운 기사도"
                cur = st.session_state.get(sk, "")
                if (not cur) or (cur not in seaz_options):
                    st.session_state[sk] = (PREFERRED_SEAZ if (PREFERRED_SEAZ and PREFERRED_SEAZ in seaz_options) else seaz_options[0])

                seaz = st.selectbox("시즈나이트 선택", seaz_options, label_visibility="collapsed", key=sk)
                st.session_state.seaz = seaz

                with st.container(key="party_group", border=False):
                    st.markdown('<div class="ctl-label">파티</div>', unsafe_allow_html=True)

                    support_opts = ["이슬맛 쿠키", "샬롯맛 쿠키"]
                    init_once(p1k, "샬롯맛 쿠키")
                    if st.session_state.get(p1k, support_opts[0]) not in support_opts:
                        st.session_state[p1k] = support_opts[0]
                    sup = st.selectbox("파티(서폿)", support_opts, label_visibility="collapsed", key=p1k)

                    init_once(p2k, "윈드파라거스 쿠키")
                    st.selectbox("파티(스트)", ["윈드파라거스 쿠키"], label_visibility="collapsed", disabled=True, key=p2k)

                    st.session_state.party = [sup, "윈드파라거스 쿠키"]

            # -------------------------
            # 3) 이슬(서폿) / 샬롯(서폿)
            # -------------------------
            elif cookie == "이슬맛 쿠키":
                fixed_seaz = getattr(sim, "FIXED_SEAZ_ISLE", "허브그린드:백마법사의 의지")
                fixed_list = hide_breeder_when_not_wind(cookie, [fixed_seaz])
                st.session_state[sk] = fixed_list[0]
                st.selectbox("시즈나이트 선택", fixed_list, label_visibility="collapsed", disabled=True, key=sk)
                st.session_state.seaz = fixed_list[0]

                st.markdown('<div class="ctl-label">파티</div>', unsafe_allow_html=True)
                init_once(p1k, "윈드파라거스 쿠키")
                st.selectbox("파티(스트)", ["윈드파라거스 쿠키"], label_visibility="collapsed", disabled=True, key=p1k)
                st.session_state.party = ["윈드파라거스 쿠키"]

            elif cookie == "샬롯맛 쿠키":
                # 샬롯 메인 시뮬 + 역할 고정(서폿) => 파티는 스트(윈드) 고정

                # 1) 원본 옵션 불러오기
                all_opts = (
                    getattr(sim, "char_allowed_seaz", lambda: None)()
                    or list(getattr(sim, "SEAZNITES", {}).keys())
                    or [""]
                )

                # 2) 허브그린드만 노출
                seaz_options = [x for x in all_opts if str(x).startswith("허브그린드:")]

                # 3) 혹시 비면(데이터 없을 때) 최소 1개는 유지
                if not seaz_options:
                    fallback = getattr(sim, "FIXED_SEAZ_ISLE", "허브그린드:백마법사의 의지")
                    seaz_options = [fallback]

                # (기존 필터 유지)
                seaz_options = hide_breeder_when_not_wind(cookie, seaz_options) or [seaz_options[0]]

                cur = st.session_state.get(sk, "")
                if (not cur) or (cur not in seaz_options):
                    st.session_state[sk] = seaz_options[0]

                seaz = st.selectbox("시즈나이트 선택", seaz_options, label_visibility="collapsed", key=sk)
                st.session_state.seaz = seaz

                st.markdown('<div class="ctl-label">파티</div>', unsafe_allow_html=True)
                init_once(p1k, "윈드파라거스 쿠키")
                st.selectbox("파티(스트)", ["윈드파라거스 쿠키"], label_visibility="collapsed", disabled=True, key=p1k)
                st.session_state.party = ["윈드파라거스 쿠키"]

            else:
                raise ValueError(f"지원하지 않는 쿠키: {cookie}")

            st.markdown('<hr class="u-divider">', unsafe_allow_html=True)

            run = st.button("실행", type="primary", use_container_width=True, key="run_btn")
            progress_slot = st.empty()

            def _progress_html(pct: int) -> str:
                pct = max(0, min(100, int(pct)))
                return f"""
                <div class="prog-area">
                <div class="prog-wrap">
                    <div class="prog-bar" style="width:{pct}%;"></div>
                    <div class="prog-text">{pct}%</div>
                </div>
                </div>
                """.strip()

            def run_with_progress(kind_cookie: str):
                progress_slot.markdown(_progress_html(0), unsafe_allow_html=True)

                def cb(p: float):
                    p = max(0.0, min(1.0, float(p)))
                    progress_slot.markdown(_progress_html(int(p * 100)), unsafe_allow_html=True)

                best = None
                best_kind = None

                # 핵심 수정: 수동모드가 아니어도 session_state.equip 이 있으면 override로 넘김
                # - 샬롯/이슬은 UI에서 해적셋 고정이라 st.session_state.equip에 값이 들어가 있음
                equip_override_local = st.session_state.equip or None

                if kind_cookie == "wind":
                    best = sim.optimize_wind_cycle(
                        seaz_name=st.session_state.seaz,
                        party=st.session_state.party,
                        step=STEP_FIXED,
                        progress_cb=cb,
                        equip_override=equip_override_local,
                    )
                    best_kind = "wind"

                elif kind_cookie == "melan":
                    best = sim.optimize_melan_cycle(
                        seaz_name=st.session_state.seaz,
                        party=st.session_state.party,
                        step=STEP_FIXED,
                        progress_cb=cb,
                        equip_override=equip_override_local,
                    )
                    best_kind = "melan"

                elif kind_cookie == "bb":
                    fn = getattr(sim, "optimize_black_barley_cycle", None)
                    if fn is None:
                        raise ValueError("sim.optimize_black_barley_cycle 가 없습니다.")
                    best = fn(
                        seaz_name=st.session_state.seaz,
                        party=st.session_state.party,
                        step=STEP_FIXED,
                        progress_cb=cb,
                        equip_override=equip_override_local,
                    )
                    best_kind = "bb"

                elif kind_cookie == "isle":
                    best = sim.optimize_isle_cycle(
                        seaz_name=st.session_state.seaz,
                        party=st.session_state.party,
                        step=STEP_FIXED,
                        progress_cb=cb,
                        equip_override=equip_override_local,
                    )
                    best_kind = "isle"

                elif kind_cookie == "char":
                    fn = getattr(sim, "optimize_char_cycle", None)
                    if fn is None:
                        raise ValueError("sim.optimize_char_cycle 가 없습니다. cookie_simulator.py에 추가해 주세요.")
                    best = fn(
                        seaz_name=st.session_state.seaz,
                        party=st.session_state.party,
                        step=STEP_FIXED,
                        progress_cb=cb,
                        equip_override=equip_override_local,
                    )
                    best_kind = "char"

                else:
                    raise ValueError(f"지원하지 않는 kind_cookie: {kind_cookie}")

                # -----------------------------------------------------
                # 공통 후처리(필요한 것만)
                # -----------------------------------------------------
                # 잠재 고정은 서폿(이슬/샬롯)만
                if isinstance(best, dict) and best_kind in ("isle", "char"):
                    best["potentials"] = {"elem_atk": 2, "atk_pct": 2, "buff_amp": 4}

                # -----------------------------------------------------
                # 이슬/샬롯: 유니크 + 설탕유리조각 "자동으로 뽑기"
                # - sim에 함수가 있으면 그걸 쓰고,
                # - 없으면(=아직 구현 안했으면) 그냥 비워둠
                # -----------------------------------------------------
                if isinstance(best, dict) and best_kind in ("isle", "char"):
                    # 장비 고정 보강 (표시/저장용)
                    if best_kind == "isle":
                        best.setdefault("equip_fixed", "전설의 유령해적 세트")
                        best.setdefault("artifact_fixed", "비에 젖은 과거")
                    else:
                        best.setdefault("equip", "전설의 유령해적 세트")

                    # 1) 유니크 자동 선택
                    pick_unique = getattr(sim, "pick_best_support_unique", None)
                    if callable(pick_unique):
                        u = pick_unique(
                            cookie_kr=("이슬맛 쿠키" if best_kind == "isle" else "샬롯맛 쿠키"),
                            party=st.session_state.party,
                        )
                        if u and (not best.get("unique")):
                            best["unique"] = u

                    # 2) 설탕유리조각 자동 선택
                    pick_shards = getattr(sim, "pick_best_support_shards", None)
                    if callable(pick_shards):
                        sh = pick_shards(
                            cookie_kr=("이슬맛 쿠키" if best_kind == "isle" else "샬롯맛 쿠키"),
                            party=st.session_state.party,
                            equip="전설의 유령해적 세트",
                        )
                        if isinstance(sh, dict) and (not best.get("shards")):
                            best["shards"] = sh

                progress_slot.markdown(_progress_html(100), unsafe_allow_html=True)
                return best, best_kind

            if run:
                kk = kind_of(st.session_state.cookie)
                best, best_kind = run_with_progress(kk)

                st.session_state.best = best
                st.session_state.best_kind = best_kind
                st.session_state.last_run = time.strftime("%Y-%m-%d %H:%M:%S")
                st.rerun()

    # =====================================================
    # 우측: 결과
    # =====================================================
    with right_col:
        with st.container(key="panel_result", border=True):
            st.markdown('<div class="h-title">RESULT</div>', unsafe_allow_html=True)

            best = st.session_state.best
            kind = st.session_state.best_kind

            if not best:
                st.caption("설정 후 실행하면 결과가 표시됩니다.")
            else:
                if kind in ("wind", "melan", "bb"):
                    c1, c2, c3 = st.columns(3, gap="small")
                    c1.metric("DPS", f"{best.get('dps', 0):,.4f}")
                    c2.metric("1사이클 시간(s)", f"{best.get('cycle_total_time', 0):,.4f}")
                    c3.metric("1사이클 총딜", f"{best.get('cycle_total_damage', 0):,.4f}")

                elif kind == "isle":
                    c1, c2, c3 = st.columns(3, gap="small")
                    c1.metric("보호막량", f"{best.get('max_shield', 0):,.0f}")
                    c2.metric("DPS", f"{best.get('dps', 0):,.4f}")
                    c3.metric("1사이클 총딜", f"{best.get('cycle_total_damage', 0):,.4f}")

                elif kind == "char":
                    c1, c2, c3 = st.columns(3, gap="small")
                    c1.metric("회복량", f"{best.get('max_heal', 0):,.0f}")   # ← 샬롯 최적화 결과에 넣을 키
                    c2.metric("DPS", f"{best.get('dps', 0):,.4f}")          # 필요 없으면 빼도 됨
                    c3.metric("1사이클 총딜", f"{best.get('cycle_total_damage', 0):,.4f}")

                if kind in ("wind", "melan", "bb", "isle", "char"):
                    tab1, tab2, tab3 = st.tabs(["결과", "최종 스탯", "사이클 기여도"])
                else:
                    tab1, tab2, tab3 = st.tabs(["결과", "최종 스탯", "사이클 기여도"])

                with tab1:
                    def make_setting_df(best: dict, kind: str) -> pd.DataFrame:
                        party_txt = ", ".join(best.get("party", [])) if best.get("party") else "없음"

                        def add(rows, k, v):
                            v = "" if v is None else str(v).strip()
                            if v:
                                rows.append({"항목": k, "값": v})

                        rows = []
                        if kind in ("wind", "melan", "bb", "char"):
                            add(rows, "장비 선택 모드", st.session_state.mode)
                            add(rows, "쿠키", best.get("cookie", ""))
                            add(rows, "장비", best.get("equip", ""))
                            add(rows, "시즈나이트", best.get("seaz", ""))
                            add(rows, "유니크 조각", best.get("unique", ""))
                            add(rows, "아티팩트", best.get("artifact", ""))
                            add(rows, "파티", party_txt)
                        elif kind in ("isle",):
                            add(rows, "장비 선택 모드", st.session_state.mode)
                            add(rows, "쿠키", "이슬맛 쿠키")
                            add(rows, "장비", best.get("equip_fixed", ""))
                            add(rows, "시즈나이트", best.get("seaz_fixed", getattr(sim, "FIXED_SEAZ_ISLE", "")))
                            u = best.get("unique", "") or best.get("unique_fixed", "")
                            add(rows, "유니크 조각", u)
                            add(rows, "아티팩트", best.get("artifact_fixed", "비에 젖은 과거"))
                            add(rows, "파티", party_txt)

                        return pd.DataFrame(rows, columns=["항목", "값"])

                    setting_df = make_setting_df(best, kind)

                    if kind in ("wind", "melan", "bb", "char"):
                        p_df = pretty_potentials(best.get("potentials", {}))
                        s_df = pretty_shards(best.get("shards", {}))
                    elif kind in ("isle",):
                        pot = best.get("potentials") or {"elem_atk": 2, "atk_pct": 2, "buff_amp": 4}
                        p_df = pretty_potentials(pot)
                        s_df = pretty_shards(best.get("shards", {}))
                    else:
                        p_df = pd.DataFrame(columns=["항목", "값"])
                        s_df = pd.DataFrame(columns=["항목", "값"])

                    html = f"""
                    <div class="summary-grid">
                    <div>{labeled_table_html("세팅", setting_df, small=False, col_ratio=(0.33, 0.67))}</div>
                    <div>{labeled_table_html("잠재력", p_df, small=True,  col_ratio=(0.55, 0.45))}</div>
                    <div class="md-span-2">{labeled_table_html("설탕유리조각", s_df, small=True, col_ratio=(0.55, 0.45))}</div>
                    </div>
                    """
                    st.markdown(html, unsafe_allow_html=True)

                if kind in ("wind", "melan", "bb", "isle", "char"):
                    with tab2:
                        stats = best.get("stats", {})
                        if not stats:
                            st.caption("스탯 정보가 없습니다.")
                        else:
                            atk_df, crit_df, common_df, skill_df, surv_df, amp_df = build_stat_tables(
                                best["stats"],
                                best.get("cookie", ""),
                                best.get("party", st.session_state.party)
                            )
                            render_final_stats_grid(atk_df, crit_df, common_df, skill_df, surv_df, amp_df)

                if kind in ("wind", "melan", "bb", "isle", "char"):
                    with tab3:
                        cb = best.get("cycle_breakdown", {})
                        df = cycle_breakdown_df(cb)

                        render_labeled_table(
                            "사이클 내 딜 기여도",
                            df,
                            small=False,
                            col_widths=(0.48, 0.32, 0.20),
                        )

            if st.session_state.last_run:
                st.caption(f"실행: {st.session_state.last_run}")


# =====================================================
# Global note (outer_shell 밖)
# =====================================================
st.markdown(
"""
<div class="global-note">
  <div class="note-title">Notes</div>
  <p class="note-text">
    • 일부 스탯은 가산/배율 적용이 섞여 있어 표시값과 실제 적용값이 다를 수 있습니다.<br/>
    • 기타 문의 : <b>Epsilon24@gmail.com</b>
  </p>
</div>
""",
unsafe_allow_html=True,
)
