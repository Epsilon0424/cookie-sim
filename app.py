import time
import html as _html
import streamlit as st
import pandas as pd
import cookie_simulator as sim
import re

st.set_page_config(page_title="쿠키 최적화 시뮬레이터", layout="wide")
STEP_FIXED = 7

st.markdown(
"""
<style>
/* =====================================================
   Base
===================================================== */
html, body, [data-testid="stAppViewContainer"]{
  background: #f3f4f6;
}

/* 카드 배경(흰색 유지) */
div[data-testid="stVerticalBlockBorderWrapper"] > div,
div[data-testid="stBorderedContainer"] > div{
  background: #ffffff !important;
  border-radius: 16px !important;
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
header[data-testid="stHeader"]{
  background: transparent !important;
}

/* columns gap */
div[data-testid="stHorizontalBlock"]{
  gap: 0.65rem !important;
}

/* st.container(border=True) card */
div[data-testid="stVerticalBlockBorderWrapper"]{
  background: #ffffff !important;
  border: none !important;
  border-radius: 14px !important;
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
  padding: 18px 18px 14px 18px;
}

/* Typography */
.h-title{
  font-size: 18px;
  font-weight: 800;
  margin: 0 0 2px 0;
}
.h-sub{
  font-size: 12px;
  color: #6b7280;
  margin: 0 0 0px 0;
}
.h-meta{
  font-size: 12px;
  color: #6b7280;
  margin: 0 0 14px 0;
}

/* metric */
div[data-testid="stMetricValue"]{
  font-size: 20px;
}

/* tabs */
button[data-baseweb="tab"]{
  font-size: 13px !important;
}

/* =====================================================
선택 UI (라벨 크게 / 값 작게 / 박스 높이 / 배경 진회색)
===================================================== */

/* 라벨(쿠키/시즈나이트/파티) */
.ctl-label{
  font-size: 14px !important;
  font-weight: 800 !important;
  color: #374151;
  margin: 10px 0 6px 0;
}

:root{
  --SEL_H: 30px;          /* 선택박스 높이 */
  --SEL_FONT: 13px;       /* 닫힌 상태 값(멜랑크림 쿠키 등) 폰트 */
  --MENU_FONT: 13px;      /* 펼친 옵션 폰트 */

  /* 탭 메뉴 아래 간격 통일 */
  --TAB_GAP: 10px;
}

/* 닫힌 상태: select 컨테이너(바깥 박스) */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
  min-height: var(--SEL_H) !important;
  height: var(--SEL_H) !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;

  background: #e5e7eb !important;        /* 조금 진한 회색 */
  box-shadow: none !important;

  display: flex !important;
  align-items: center !important;
}

/* selectbox 흰 테두리(기본 border/포커스 링) 제거 */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
  border: 0 !important;
  outline: none !important;
  box-shadow: none !important;   /* 포커스 링/테두리 느낌 제거 */
}

/* 포커스/클릭/hover 때도 다시 생기지 않게 */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover{
  border: 0 !important;
  outline: none !important;
  box-shadow: none !important;
}

/* 내부 combobox도 높이/정렬 맞추기 */
div[data-testid="stSelectbox"] div[role="combobox"]{
  min-height: var(--SEL_H) !important;
  height: var(--SEL_H) !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  display: flex !important;
  align-items: center !important;
  background: transparent !important;
}

/* 닫힌 상태 값 폰트: "전체를" 내려서 무조건 먹게 만들기 */
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  font-size: var(--SEL_FONT) !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] *{
  font-size: var(--SEL_FONT) !important;
  line-height: 1.5 !important;
}

/* =====================================================
드롭다운(펼친 옵션 목록) 폰트
===================================================== */
div[data-baseweb="menu"] *,
[role="listbox"] *,
li[role="option"]{
  font-size: var(--MENU_FONT) !important;
}

/* (선택) 옵션 hover 배경 */
li[role="option"]:hover{
  background: #f1f5f9 !important;
}

/* =====================================================
   버튼 톤
===================================================== */
.stButton > button[kind="primary"]{
  border-radius: 12px;
  height: 40px;
  font-weight: 800;
  background: #ff4b4b !important;
  border: none !important;
  color: #ffffff !important;
  box-shadow: 0 8px 18px rgba(255,75,75,0.20);
}
.stButton > button[kind="primary"]:hover{
  background: #ff3434 !important;
}
.stButton > button:not([kind="primary"]){
  border-radius: 12px;
  height: 40px;
  font-weight: 700;
  background: #ffffff !important;
  border: 1px solid #e5e7eb !important;
  color: #111827 !important;
}
.stButton > button:not([kind="primary"]):hover{
  border-color: #d1d5db !important;
  background: #f9fafb !important;
}

/* =====================================================
   라벨(pill) + 테이블 카드(끝-끝 맞춤)
===================================================== */
.stat-wrap{
  margin: 0px 0 14px 0;   /* 위쪽 여백 제거 */
}

/* stat-grid 탭별로 따로 margin 주지 말고 0으로 통일 */
.stat-grid{ margin-top: 0 !important; }

/* summary-grid도 0으로 통일(탭 패널이 gap을 관리) */
.summary-grid{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
  align-items: start;
  margin-top: 0 !important;
}

/* 탭 패널 상단 여백을 변수로 통일 */
div[data-testid="stTabs"] div[data-baseweb="tab-panel"]{
  padding-top: var(--TAB_GAP) !important;
}
div[data-testid="stTabs"] div[data-baseweb="tab-panel"] > div{
  margin-top: 0 !important;
  padding-top: 0 !important;
}

/* 잘못된 규칙(단위 없는 8) 제거/정상화 */
div[data-testid="stTabs"] div[data-baseweb="tab-panel"] .stat-pill{
  margin-top: 0 !important;
}

.stat-pill{
  display: block;
  width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 900;
  line-height: 1.2;
  color: #111827;
  box-shadow: 0 4px 10px rgba(0,0,0,0.06);
  margin: 0 0 8px 0;
}

/* table */
:root{ --ROW_H: 38px; --CELL_PX: 12px; }
.u-table{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 6px 16px rgba(0,0,0,0.03);
}
.u-table thead th,
.u-table tbody td{
  height: var(--ROW_H);
  padding: 0 var(--CELL_PX);
  line-height: var(--ROW_H);
  vertical-align: middle;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  color: #111827;
}
.u-table thead th{
  background: #f9fafb;
  color: #374151;
  font-weight: 800;
  border-bottom: 1px solid #e5e7eb;
}
.u-table tbody td{ border-bottom: 1px solid #eef2f7; }
.u-table tbody tr:last-child td{ border-bottom: none; }
.u-table.small thead th,
.u-table.small tbody td{ font-size: 11.5px; }
.u-empty{ font-size: 12px; color: #6b7280; padding: 10px 2px 0 2px; }

/* grid */
.stat-grid{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
  align-items: start;
}
.stat-grid .stat-wrap{ margin: 0 !important; }
@media (max-width: 980px){
  .stat-grid{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stat-grid .span-2{ grid-column: 1 / -1; }
}
@media (max-width: 640px){
  .stat-grid{ grid-template-columns: 1fr; }
  .stat-grid .span-2{ grid-column: auto; }
}

/* progress */
.prog-wrap{
  width: 100%;
  height: 18px;
  border-radius: 999px;
  background: #f1f5f9;
  border: 1px solid #e5e7eb;
  overflow: hidden;
  position: relative;
  box-shadow: 0 4px 10px rgba(0,0,0,0.06);
}
.prog-bar{
  height: 100%;
  width: 0%;
  background: #ff4b4b;
  transition: width 120ms ease;
}
.prog-text{
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 900;
  color: #ffffff;
  letter-spacing: 0.2px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.25);
  user-select: none;
}
.prog-sub{
  margin-top: 8px;
  font-size: 11px;
  color: #6b7280;
}

/* 중간 화면: 2열 + 마지막 카드만 한줄 전체 */
@media (max-width: 980px){
  .summary-grid{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .summary-grid .md-span-2{
    grid-column: 1 / -1;
  }
}

/* 작은 화면: 1열(세로 3개) */
@media (max-width: 640px){
  .summary-grid{
    grid-template-columns: 1fr;
  }
  .summary-grid .md-span-2{
    grid-column: auto;
  }
}
div[data-testid="stMarkdownContainer"] hr.u-divider{
  border: none !important;
  border-top: 1px solid #e5e7eb !important;

  margin-top: -4px !important;
  margin-bottom: 12px !important;
}

/* 실행 버튼 아래에 항상 공간 확보 */
.prog-slot{
  margin-top: 30px;
  height: 20px;
}
.prog-area{
  padding-top: -5px;      /* 버튼과 바 사이 간격 */
  padding-bottom: 20px;   /* 바와 카드 바닥 간격 (겹침 방지) */
}

:root{
  --accent: #ff3434;
  --accent-soft: rgba(255,52,52,0.10);
}

/* 테이블 헤더 밑줄 */
thead tr th{
  border-bottom: 2px solid rgba(255,52,52,0.18) !important;
}

</style>
""",
unsafe_allow_html=True,
)

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

def render_final_stats_grid(atk_df, crit_df, common_df, skill_df, strike_df):
    html = f"""
    <div class="stat-grid">
      <div>{labeled_table_html("공격력(계산 기준)", atk_df, small=False)}</div>
      <div>{labeled_table_html("치명타", crit_df, small=False)}</div>
      <div>{labeled_table_html("피해 보정(공통)", common_df, small=False)}</div>
      <div>{labeled_table_html("스킬 타입 피해 증가", skill_df, small=False)}</div>
      <div class="span-2">{labeled_table_html("속성강타 피해", strike_df, small=False)}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# =====================================================
# 요약표(잠재/조각): 1 이상만 표시
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
def _f(stats: dict, key: str, default=0.0) -> float:
    try:
        return float(stats.get(key, default))
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

def build_stat_tables(stats: dict):
    stats = stats or {}

    oa = _f(stats, "base_atk", 0.0)
    ea = _f(stats, "elem_atk", 0.0)

    atk_pct = _f(stats, "atk_pct", 0.0)
    final_atk_mult = _f(stats, "final_atk_mult", 0.0)

    atk_mul = 1.0 + atk_pct
    final_mul = 1.0 + final_atk_mult
    final_atk_input = (oa + ea) * atk_mul * final_mul

    crit_rate = _f(stats, "crit_rate", 0.0)
    crit_dmg = _f(stats, "crit_dmg", 0.0)
    crit_inc = max(0.0, crit_dmg - 1.0)

    all_elem_dmg = _f(stats, "all_elem_dmg", 1.0)
    armor_pen = _f(stats, "armor_pen", 0.0)
    def_reduction = _f(stats, "def_reduction", 0.0)
    final_dmg = _f(stats, "final_dmg", 0.0)

    basic_dmg = _f(stats, "basic_dmg", 0.0)
    special_dmg = _f(stats, "special_dmg", 0.0)
    ult_dmg = _f(stats, "ult_dmg", 0.0)
    passive_dmg = _f(stats, "passive_dmg", 0.0)

    strike = stats.get("element_strike_dmg", stats.get("element_strike", 0.0))
    try:
        strike = float(strike)
    except Exception:
        strike = 0.0

    def add_if_nonzero(rows, label, value_str, numeric_check):
        try:
            if abs(float(numeric_check)) < 1e-12:
                return
        except Exception:
            return
        rows.append([label, value_str])

    atk_df = pd.DataFrame(
        [
            ["OA(기본공)", _fmt_num(oa)],
            ["EA(속성공)", _fmt_num(ea)],
            ["공격력%", _fmt_pct(atk_pct)],
            ["최종공", _fmt_pct(final_atk_mult)],
            ["최종 공격력", _fmt_num(final_atk_input)],
        ],
        columns=["항목", "값"],
    )

    g2 = []
    add_if_nonzero(g2, "치확", _fmt_pct(crit_rate), crit_rate)
    add_if_nonzero(g2, "치피", _fmt_pct(crit_inc), crit_dmg)
    crit_df = pd.DataFrame(g2, columns=["항목", "값"])

    g3 = []
    add_if_nonzero(g3, "모든 속성 피해", f"{(all_elem_dmg-1)*100:.1f}%", all_elem_dmg - 1.0)
    add_if_nonzero(g3, "방관", _fmt_pct(armor_pen), armor_pen)
    add_if_nonzero(g3, "방깎", _fmt_pct(def_reduction), def_reduction)
    add_if_nonzero(g3, "최종피", _fmt_pct(final_dmg), final_dmg)
    common_df = pd.DataFrame(g3, columns=["항목", "값"])

    g4 = []
    add_if_nonzero(g4, "기본 공격 피해", _fmt_pct(basic_dmg), basic_dmg)
    add_if_nonzero(g4, "특수스킬 피해", _fmt_pct(special_dmg), special_dmg)
    add_if_nonzero(g4, "궁극기 피해", _fmt_pct(ult_dmg), ult_dmg)
    add_if_nonzero(g4, "패시브 피해", _fmt_pct(passive_dmg), passive_dmg)
    skill_df = pd.DataFrame(g4, columns=["항목", "값"])

    g5 = []
    add_if_nonzero(g5, "속성 강타 피해", _fmt_pct(strike), strike)
    strike_df = pd.DataFrame(g5, columns=["항목", "값"])

    return atk_df, crit_df, common_df, skill_df, strike_df

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

#  추가: 장비 선택 모드/장비 저장용
if "mode" not in st.session_state:
    st.session_state.mode = "최적(자동)"
if "equip" not in st.session_state:
    st.session_state.equip = ""

if "_cookie_prev" not in st.session_state:
    st.session_state._cookie_prev = st.session_state.cookie

def kind_of(cookie_name: str) -> str:
    return {"윈드파라거스 쿠키": "wind", "멜랑크림 쿠키": "melan", "이슬맛 쿠키": "isle"}.get(cookie_name, "melan")

def seaz_key(kind: str) -> str:
    return f"seaz_widget__{kind}"

def party1_key(kind: str) -> str:
    return f"party_slot1__{kind}"

def party2_key(kind: str) -> str:
    return f"party_slot2__{kind}"

# =====================================================
# 상단 타이틀
# =====================================================
st.markdown('<div class="h-title">쿠키 최적화 시뮬레이터</div>', unsafe_allow_html=True)
st.markdown('<div class="h-sub">쿠키 선택 → 장비 선택 모드/장비 선택 → 시즈나이트/파티 구성 → 실행</div>', unsafe_allow_html=True)
st.markdown('<div class="h-meta">기타 문의는 Epsilon24@gmail.com으로 주세요</div>', unsafe_allow_html=True)

# =====================================================
# 레이아웃: 좌/우
# =====================================================
left_col, right_col = st.columns([0.8, 2.4], gap="small")

# =====================================================
# 좌측: 선택
# =====================================================
with left_col:
    with st.container(border=True):
        st.markdown('<div class="h-title">선택</div>', unsafe_allow_html=True)

        st.markdown('<div class="ctl-label">쿠키</div>', unsafe_allow_html=True)
        cookie_options = ["멜랑크림 쿠키", "윈드파라거스 쿠키", "이슬맛 쿠키"]

        if "cookie_widget" not in st.session_state:
            st.session_state.cookie_widget = st.session_state.cookie

        cookie = st.selectbox(
            "쿠키",
            cookie_options,
            label_visibility="collapsed",
            key="cookie_widget",
        )

        if cookie != st.session_state._cookie_prev:
            st.session_state.cookie = cookie
            st.session_state._cookie_prev = cookie

            st.session_state.seaz = ""
            st.session_state.party = []
            st.session_state.best = None
            st.session_state.best_kind = None
            st.session_state.last_run = None

            #  쿠키 바뀌면 장비 선택 모드/장비도 기본값으로 리셋
            st.session_state.mode = "최적(자동)"
            st.session_state.equip = ""

            k2 = kind_of(cookie)
            st.session_state[seaz_key(k2)] = ""

            st.session_state[party1_key(k2)] = "없음"
            st.session_state[party2_key(k2)] = "없음"

            #  쿠키별 위젯 키도 리셋
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
        #  추가: 장비 선택 모드(최적/선택) + 선택 장비 선택 모드일 때 장비 선택
        # =====================================================
        st.markdown('<div class="ctl-label">장비 선택 장비 선택 모드</div>', unsafe_allow_html=True)

        mode_opts = ["최적(자동)", "선택(수동)"]
        if st.session_state.get(mk, "") not in mode_opts:
            st.session_state[mk] = mode_opts[0]

        mode = st.selectbox("장비 선택 장비 선택 모드", mode_opts, label_visibility="collapsed", key=mk)
        st.session_state.mode = mode

        equip_override = None
        if mode == "선택(수동)":
            st.markdown('<div class="ctl-label">장비</div>', unsafe_allow_html=True)

            # sim에 함수가 없을 수 있으니 안전하게 처리
            if cookie == "윈드파라거스 쿠키":
                equip_options = (getattr(sim, "wind_allowed_equips", lambda: [""])() or [""])
            elif cookie == "멜랑크림 쿠키":
                equip_options = (getattr(sim, "melan_allowed_equips", lambda: [""])() or [""])
            else:
                equip_options = ["전설의 유령해적 세트"]

            if st.session_state.get(ek, "") not in equip_options:
                st.session_state[ek] = equip_options[0]

            equip = st.selectbox("장비 선택", equip_options, label_visibility="collapsed", key=ek)
            st.session_state.equip = equip
            equip_override = equip
        else:
            st.session_state.equip = ""
            equip_override = None

        # =====================================================
        # 기존: 시즈나이트/파티
        # =====================================================
        st.markdown('<div class="ctl-label">시즈나이트</div>', unsafe_allow_html=True)

        if cookie == "윈드파라거스 쿠키":
            seaz_options = sim.wind_allowed_seaz() or [""]
            if st.session_state.get(sk, "") not in seaz_options:
                st.session_state[sk] = seaz_options[0]

            seaz = st.selectbox("시즈나이트 선택", seaz_options, label_visibility="collapsed", key=sk)
            st.session_state.seaz = seaz

            st.markdown('<div class="ctl-label">파티</div>', unsafe_allow_html=True)
            party_all = ["없음", "이슬맛 쿠키"]
            init_once(p1k, "이슬맛 쿠키")

            p1 = st.selectbox("파티 슬롯", party_all, label_visibility="collapsed", key=p1k)
            st.session_state.party = [x for x in [norm_none(p1)] if x]

        elif cookie == "멜랑크림 쿠키":
            seaz_options = [x for x in sim.SEAZNITES.keys() if x.startswith("바닐라몬드:")] or [""]

            PREFERRED_SEAZ = "바닐라몬드:추격자의 결의"

            cur = st.session_state.get(sk, "")
            if (not cur) or (cur not in seaz_options):
                st.session_state[sk] = PREFERRED_SEAZ if PREFERRED_SEAZ in seaz_options else seaz_options[0]

            seaz = st.selectbox("시즈나이트 선택", seaz_options, label_visibility="collapsed", key=sk)
            st.session_state.seaz = seaz

            st.markdown('<div class="ctl-label">파티</div>', unsafe_allow_html=True)

            party_all = ["없음", "이슬맛 쿠키", "윈드파라거스 쿠키"]

            init_once(p1k, "이슬맛 쿠키")
            init_once(p2k, "윈드파라거스 쿠키")

            p1 = st.selectbox("파티 슬롯 1", party_all, label_visibility="collapsed", key=p1k)

            if p1 == "이슬맛 쿠키":
                party2_opts = ["없음", "윈드파라거스 쿠키"]
            elif p1 == "윈드파라거스 쿠키":
                party2_opts = ["없음", "이슬맛 쿠키"]
            else:
                party2_opts = party_all

            if st.session_state.get(p2k, "없음") not in party2_opts:
                st.session_state[p2k] = "없음"

            p2 = st.selectbox("파티 슬롯 2", party2_opts, label_visibility="collapsed", key=p2k)

            if p1 != "없음" and p2 == p1:
                st.session_state[p2k] = "없음"
                p2 = "없음"

            party_list = [norm_none(p1), norm_none(p2)]
            party_list = [x for x in party_list if x]
            st.session_state.party = party_list

        else:
            fixed_seaz = getattr(sim, "FIXED_SEAZ_ISLE", "허브그린드:백마법사의 의지")
            st.session_state[sk] = fixed_seaz
            st.selectbox("시즈나이트 선택", [fixed_seaz], label_visibility="collapsed", disabled=True, key=sk)
            st.session_state.seaz = fixed_seaz

            st.markdown('<div class="ctl-label">파티</div>', unsafe_allow_html=True)
            party_all = ["없음", "윈드파라거스 쿠키"]
            init_once(p1k, "윈드파라거스 쿠키")

            p1 = st.selectbox("파티 슬롯", party_all, label_visibility="collapsed", key=p1k)
            st.session_state.party = [x for x in [norm_none(p1)] if x]

        st.markdown('<hr class="u-divider">', unsafe_allow_html=True)

        run = st.button("실행", type="primary", use_container_width=True)

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

            #  장비 선택 모드에 따른 장비 override
            equip_override_local = None
            if st.session_state.mode == "선택(수동)":
                equip_override_local = st.session_state.equip or None

            if kind_cookie == "wind":
                best = sim.optimize_wind_cycle(
                    seaz_name=st.session_state.seaz,
                    party=st.session_state.party,
                    step=STEP_FIXED,
                    progress_cb=cb,
                    equip_override=equip_override_local,   #  추가 (sim도 수정 필요)
                )
                best_kind = "wind"

            elif kind_cookie == "melan":
                best = sim.optimize_melan_cycle(
                    seaz_name=st.session_state.seaz,
                    party=st.session_state.party,
                    step=STEP_FIXED,
                    progress_cb=cb,
                    equip_override=equip_override_local,   #  추가 (sim도 수정 필요)
                )
                best_kind = "melan"

            else:
                best = sim.optimize_isle_shards_only(st.session_state.party)
                best_kind = "isle"
                if isinstance(best, dict):
                    best.setdefault("potentials", {"elem_atk": 2, "atk_pct": 2, "buff_amp": 4})
                    best.setdefault("unique_fixed", "정화된 에메랄딘의 기억")
                    best.setdefault("artifact_fixed", "비에 젖은 과거")

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
    with st.container(border=True):
        st.markdown('<div class="h-title">결과</div>', unsafe_allow_html=True)

        best = st.session_state.best
        kind = st.session_state.best_kind

        if not best:
            st.caption("설정 후 실행하면 결과가 표시됩니다.")
        else:
            if kind in ("wind", "melan"):
                c1, c2, c3 = st.columns(3, gap="small")
                c1.metric("DPS", f"{best.get('dps', 0):,.4f}")
                c2.metric("1사이클 시간(s)", f"{best.get('cycle_total_time', 0):,.4f}")
                c3.metric("1사이클 총딜", f"{best.get('cycle_total_damage', 0):,.4f}")
            else:
                c1, c2 = st.columns(2, gap="small")
                c1.metric("최종 공격력", f"{best.get('final_atk', 0):,.0f}")
                c2.metric("최대 보호막", f"{best.get('max_shield', 0):,.0f}")

            if kind in ("wind", "melan"):
                tab1, tab2, tab3 = st.tabs(["결과", "최종 스탯", "사이클 기여도"])
            else:
                tab1 = st.tabs(["결과"])[0]

            with tab1:
                def make_setting_df(best: dict, kind: str) -> pd.DataFrame:
                    party_txt = ", ".join(best.get("party", [])) if best.get("party") else "없음"

                    def add(rows, k, v):
                        v = "" if v is None else str(v).strip()
                        if v:
                            rows.append({"항목": k, "값": v})

                    rows = []
                    if kind in ("wind", "melan"):
                        add(rows, "장비 선택 모드", st.session_state.mode)  #  추가
                        # 선택(수동)일 때 사용자가 고른 장비도 같이 표시(참고)
                        if st.session_state.mode == "선택(수동)":
                            add(rows, "선택 장비", st.session_state.equip or "")
                        add(rows, "쿠키", best.get("cookie", ""))
                        add(rows, "장비(결과)", best.get("equip", ""))
                        add(rows, "시즈나이트", best.get("seaz", ""))
                        add(rows, "유니크 조각", best.get("unique", ""))
                        add(rows, "아티팩트", best.get("artifact", ""))
                        add(rows, "파티", party_txt)
                    else:
                        add(rows, "장비 선택 모드", st.session_state.mode)  #  추가
                        add(rows, "쿠키", "이슬맛 쿠키")
                        add(rows, "장비", best.get("equip_fixed", ""))
                        add(rows, "시즈나이트", best.get("seaz_fixed", getattr(sim, "FIXED_SEAZ_ISLE", "")))
                        add(rows, "유니크 조각", best.get("unique_fixed", "정화된 에메랄딘의 기억"))
                        add(rows, "아티팩트", best.get("artifact_fixed", "비에 젖은 과거"))
                        add(rows, "파티", party_txt)

                    return pd.DataFrame(rows, columns=["항목", "값"])

                setting_df = make_setting_df(best, kind)

                if kind in ("wind", "melan"):
                    p_df = pretty_potentials(best.get("potentials", {}))
                    s_df = pretty_shards(best.get("shards", {}))
                else:
                    pot = best.get("potentials") or {"elem_atk": 2, "atk_pct": 2, "buff_amp": 4}
                    p_df = pretty_potentials(pot)
                    s_df = pretty_shards(best.get("shards", {}))

                html = f"""
                <div class="summary-grid">
                  <div>{labeled_table_html("세팅", setting_df, small=False, col_ratio=(0.33, 0.67))}</div>
                  <div>{labeled_table_html("잠재력", p_df, small=True,  col_ratio=(0.55, 0.45))}</div>
                  <div class="md-span-2">{labeled_table_html("설탕유리조각", s_df, small=True, col_ratio=(0.55, 0.45))}</div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

            if kind in ("wind", "melan"):
                with tab2:
                    stats = best.get("stats", {})
                    if not stats:
                        st.caption("스탯 정보가 없습니다.")
                    else:
                        atk_df, crit_df, common_df, skill_df, strike_df = build_stat_tables(stats)
                        render_final_stats_grid(atk_df, crit_df, common_df, skill_df, strike_df)

            if kind in ("wind", "melan"):
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
            st.caption(f"마지막 실행: {st.session_state.last_run}")
