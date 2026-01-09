# cookie_simulator.py
# =====================================================
# 쿠키 최적화 시뮬레이터 (모듈)
#  - 공통: base_damage_only + 속성강타 + 유니크(초당 추가딜 계수)
#  - 쿠키: 윈드파라거스 / 멜랑크림 / 이슬(보호막)
# =====================================================
from typing import Tuple
from typing import Optional, List, Dict, Callable, Union, Sequence

# =====================================================
# 0) 전역 설정(토글/상수)
# =====================================================

MODE_ALWAYS  = "ALWAYS"   # 항상 켜짐(업타임 1.0)
MODE_AVERAGE = "AVERAGE"  # duration/cooldown 평균 업타임
MODE_TRIGGER = "TRIGGER"  # 기대 업타임을 직접 넣거나, proc_interval로 근사
MODE_CUSTOM  = "CUSTOM"   # 사용자가 value로 고정

UPTIME_CONFIG = {
    # 이슬: 파티 치피 +56% (항상이라고 가정)
    "PARTY_ISLE_CRITDMG_0p56": {"mode": MODE_ALWAYS},

    # 이슬: (가정) 시즈로 최종공 +25%, 모속피 +30% (상시)
    "PARTY_ISLE_SEAZ_ATK25_ALL30": {
        "mode": MODE_ALWAYS,     # 필요하면 MODE_AVERAGE로 변경
        "duration": 15.0,
        "cooldown": 25.0,
    },

    # 윈파 파티 버프(방관/최종/치피) 상시라고 가정
    "PARTY_WIND_ARMOR224_FINAL3125_CRIT40": {"mode": MODE_ALWAYS},

    # (예시) 윈파 시즈 브리더 효과를 따로 업타임으로 다루고 싶으면 여기 사용
    "WIND_SEAZ_BREEDER_EFFECT": {"mode": MODE_ALWAYS},
}

# 황금 예복 세트 효과를 '파티 전체 오라'라고 가정하면 True
GOLDEN_SET_TEAM_AURA = True

# 보스 표식 속성저항(가정)
BOSS_MARK_ELEMENT_RESIST = 0.40

# 기본공격피해 스택 방식(현재: 기본피는 (1+a)(1+b)-1 형태로 누적)
BASIC_DMG_STACKING_MODE = "ADD"  # "ADD" or "MULT_BONUS"

# 나비스(강화 표식) 효과: 속성 강타 피해 +30%
NAVIS_ENHANCED_MARK_STRIKE_BONUS = 0.30

# =====================================================
# 0.1) 설탕셋(달콤한 설탕 깃털복) 발동형 옵션 파라미터
# - 기본공격 적중 시 20% 확률로 공격력 50% 추가피해 (EV로 처리)
# =====================================================
SUGAR_SET_PROC_CHANCE = 0.20
SUGAR_SET_PROC_ATK_COEFF = 0.50  # unit 기준 단순화(=unit*0.5)

# =====================================================
# 0.2) 아르곤 유니크 파라미터
# =====================================================
ARGON_AURA_DURATION = 15.0     # 오라 지속시간(초)
ARGON_PROC_HITS = 5            # 5회 적중마다
ARGON_BONUS_PER_PROC = 0.50    # 추가피해 50% (unit 기준 단순화)
ARGON_DMG_REDUCTION = 0.30     # 받피감 30% (딜 모델에는 미반영)

# =====================================================
# 1) 공통 유틸
# =====================================================

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def get_uptime(key: str) -> float:
    """UPTIME_CONFIG 기반 업타임 계산(0~1)."""
    cfg = UPTIME_CONFIG.get(key, {"mode": MODE_ALWAYS})
    mode = cfg.get("mode", MODE_ALWAYS)

    if mode == MODE_ALWAYS:
        return 1.0

    if mode == MODE_AVERAGE:
        dur = float(cfg.get("duration", 0.0))
        cd  = float(cfg.get("cooldown", 1.0))
        if cd <= 0:
            return 1.0
        return clamp(dur / cd, 0.0, 1.0)

    if mode == MODE_TRIGGER:
        if "expected_uptime" in cfg:
            return clamp(float(cfg["expected_uptime"]), 0.0, 1.0)
        dur = float(cfg.get("duration", 0.0))
        interval = float(cfg.get("proc_interval", 1.0))
        if interval <= 0:
            return 1.0
        return clamp(dur / interval, 0.0, 1.0)

    if mode == MODE_CUSTOM:
        return clamp(float(cfg.get("value", 1.0)), 0.0, 1.0)

    return 1.0

def add_stat(stats: Dict[str, float], k: str, v: float):
    v = float(v)
    if k == "basic_dmg" and BASIC_DMG_STACKING_MODE == "ADD":
        # 기본피는 (1+a)(1+b)-1 로 누적
        stats[k] = (1.0 + stats.get(k, 0.0)) * (1.0 + v) - 1.0
    else:
        stats[k] = stats.get(k, 0.0) + v

def add(stats: Dict[str, float], bonus: Dict[str, float]):
    """dict 형태 bonus를 stats에 누적."""
    for k, v in bonus.items():
        add_stat(stats, k, float(v))

def _resolve_equip_list_override(
    equip_override: Optional[Union[str, Sequence[str]]],
    default_equips: List[str]
) -> List[str]:
    """
    equip_override:
      - None: 기본 목록 사용
      - str: 해당 장비 1개로 고정
      - list/tuple 등: 그 목록으로 제한(기본 목록과 교집합)
    """
    if equip_override is None:
        return list(default_equips)

    # 문자열이면 단일 고정
    if isinstance(equip_override, str):
        return [equip_override]

    # 리스트/튜플 등 시퀀스면 필터링
    requested = [str(x) for x in equip_override]
    # 기본 허용 목록과 교집합(순서는 requested 우선)
    allowed_set = set(default_equips)
    filtered = [x for x in requested if x in allowed_set]
    return filtered
# =====================================================
# 2) 공통 데이터(쿠키/속성/직업/형태)
# =====================================================

COOKIES = {
    "윈드파라거스 쿠키": "wind_paragus",
    "이슬맛 쿠키": "isle",
    "멜랑크림 쿠키": "melan_cream",
}

COOKIE_ELEMENT = {
    "윈드파라거스 쿠키": "wind",
    "이슬맛 쿠키": "water",
    "멜랑크림 쿠키": "dark",
}

# 윈파 표식(강화 표식)이 "바람 속성"이라고 가정
WIND_MARK_ELEMENT = "wind"

COOKIE_TYPE = {
    "윈드파라거스 쿠키": "magic",
    "이슬맛 쿠키": "support",
    "멜랑크림 쿠키": "slash",
}

COOKIE_ROLE = {
    "윈드파라거스 쿠키": "strike",
    "이슬맛 쿠키": "support",
    "멜랑크림 쿠키": "dps",
}

# 초당 타수(히트 수) — 아르곤(5타마다) 기대값 계산용
COOKIE_HITS_PER_SEC = {
    "멜랑크림 쿠키": 3.0,
    "윈드파라거스 쿠키": 11.0 / 2.5,  # 4.4
}

# 유니크/오라 업타임 계산에 쓰는 "궁 쿨" (간단 모델)
ULT_COOLDOWN = {
    "윈드파라거스 쿠키": 30.0,
    "멜랑크림 쿠키": 30.0,
}

# =====================================================
# 3) 공통: 설탕유리조각(41칸) / 잠재력(8칸)
# =====================================================

TOTAL_SLOTS = 49
UNIQUE_SLOTS = 8
NORMAL_SLOTS = 41

SHARD_INC = {
    "crit_rate": 0.048,
    "crit_dmg": 0.08,
    "all_elem_dmg": 0.048,
    "basic_dmg": 0.048,
    "special_dmg": 0.048,
    "ult_dmg": 0.048,
    "passive_dmg": 0.048,
    "atk_pct": 0.064,
    "elem_atk": 24,
    "def_pct": 0.04,
    "shield_pct": 0.032
}

SHARD_KR = {
    "crit_rate": "치명타 확률",
    "crit_dmg": "치명타 피해",
    "all_elem_dmg": "모든 속성 피해",
    "basic_dmg": "기본 공격 피해",
    "special_dmg": "특수 스킬 피해",
    "ult_dmg": "궁극기 피해",
    "passive_dmg": "패시브 스킬 피해",
    "atk_pct": "공격력 %",
    "elem_atk": "속성 공격력",
    "def_pct": "방어력 %",
    "shield_pct": "보호막 %"
}

POTENTIAL_INC = {
    "atk_pct": 0.20,
    "crit_rate": 0.15,
    "crit_dmg": 0.25,
    "armor_pen": 0.08,
    "elem_atk": 80,
    "buff_amp": 0.0,
    "debuff_amp": 0.0,
}

POTENTIAL_KR = {
    "atk_pct": "공격력 %",
    "crit_rate": "치명타 확률",
    "crit_dmg": "치명타 피해",
    "armor_pen": "방어력 관통",
    "elem_atk": "속성 공격력",
    "buff_amp": "버프 증폭",
    "debuff_amp": "디버프 증폭",
}

# =====================================================
# 4) 공통: 장비 세트
# =====================================================

EQUIP_SETS = {
    "달콤한 설탕 깃털복": {
        "head": {"base": {"all_elem_dmg": 0.312}, "unique": {"atk_pct": 0.30}},
        "top":  {"base": {"def_pct": 0.52},       "unique": {"armor_pen": 0.15}},
        "bottom":{"base": {"hp_pct": 0.52},       "unique": {"elem_atk": 96}},
        "set_effect": {"base": {"all_elem_dmg": 0.20}}
    },
    "미지의 방랑자": {
        "head": {"base": {"all_elem_dmg": 0.312}, "unique": {"crit_dmg": 0.375}},
        "top":  {"base": {"def_pct": 0.52},       "unique": {"all_elem_dmg": 0.225}},
        "bottom":{"base": {"hp_pct": 0.52},       "unique": {"elem_atk": 120}},
        "set_effect": {"base": {"crit_rate": 0.15}}
    },
    "수상한 사냥꾼": {
        "head": {"base": {"all_elem_dmg": 0.312}, "unique": {"basic_dmg": 0.225}},
        "top":  {"base": {"def_flat": 525},       "unique": {"crit_rate": 0.225}},
        "bottom":{"base": {"hp_pct": 0.52},       "unique": {"crit_dmg": 0.375}},
        "set_effect": {"base": {"atk_pct": 0.20}}
    },
    "시간관리국의 제복": {
        "head": {"base": {"all_elem_dmg": 0.312}, "unique": {"atk_pct": 0.30}},
        "top":  {"base": {"def_pct": 0.52},       "unique": {"elem_atk": 120}},
        "bottom":{"base": {"hp_pct": 0.52},       "unique": {"all_elem_dmg": 0.225}},
        "set_effect": {"base": {"atk_pct": 0.15}}
    },
    "전설의 유령해적 세트": {
        "head": {"base": {}, "unique": {}},
        "top":  {"base": {}, "unique": {}},
        "bottom":{"base": {}, "unique": {}},
        "set_effect": {"base": {"all_elem_dmg": 0.30, "def_reduction": 0.10}}
    },
    "황금 예복 세트": {
        "head": {"base": {"all_elem_dmg": 0.312}, "unique": {"crit_rate": 0.225}},
        "top":  {"base": {"def_pct": 0.52},       "unique": {"special_dmg": 0.225}},
        "bottom":{"base": {"hp_pct": 0.52},       "unique": {"ult_dmg": 0.225}},
        "set_effect": {"base": {"element_strike_dmg": 0.25, "debuff_amp": 0.15}}
    },
}

# =====================================================
# 5) 공통: 시즈나이트
# =====================================================

PEPPER_RUBY_SUB     = {"basic_dmg": 0.30, "crit_dmg": 0.25}
RICH_CORAL_SUB      = {"element_strike_dmg": 0.25, "special_dmg": 0.15, "ult_dmg": 0.15}
VANILLA_MONDE_SUB   = {"passive_dmg": 0.30, "crit_dmg": 0.25}

SEAZNITES = {
    "페퍼루비:믿음직한 브리더": {"passive": {"ally_all_elem_dmg": 0.15, "element_strike_dmg": 0.75}, "sub": PEPPER_RUBY_SUB},
    "페퍼루비:듬직한 격투가":   {"passive": {"special_dmg": 0.30, "ult_dmg": 0.30}, "sub": PEPPER_RUBY_SUB},
    "페퍼루비:사냥꾼의 본능":   {"passive": {"final_dmg_stack": 0.05, "max_stacks": 6}, "sub": PEPPER_RUBY_SUB},
    "페퍼루비:위대한 통치자":   {"passive": {"ult_dmg": 0.60}, "sub": PEPPER_RUBY_SUB},
    "페퍼루비:거침없는 습격자": {"passive": {"special_dmg": 0.40, "ult_dmg": 0.20}, "sub": PEPPER_RUBY_SUB},
    "페퍼루비:영예로운 기사도": {"passive": {"basic_dmg": 0.40, "special_dmg": 0.20}, "sub": PEPPER_RUBY_SUB},
    "페퍼루비:돌진하는 전차":   {"passive": {"final_dmg": 0.12, "atk_spd": 0.12, "move_spd": 0.12}, "sub": PEPPER_RUBY_SUB},
    "페퍼루비:추격자의 결의":   {"passive": {"final_dmg": 0.30, "move_spd": 0.10}, "sub": PEPPER_RUBY_SUB},

    "리치코랄:믿음직한 브리더": {"passive": {"ally_all_elem_dmg": 0.15, "element_strike_dmg": 0.75}, "sub": RICH_CORAL_SUB},

    "바닐라몬드:믿음직한 브리더": {"passive": {"ally_all_elem_dmg": 0.15, "element_strike_dmg": 0.75}, "sub": VANILLA_MONDE_SUB},
    "바닐라몬드:듬직한 격투가":   {"passive": {"special_dmg": 0.30, "ult_dmg": 0.30}, "sub": VANILLA_MONDE_SUB},
    "바닐라몬드:사냥꾼의 본능":   {"passive": {"final_dmg_stack": 0.05, "max_stacks": 6}, "sub": VANILLA_MONDE_SUB},
    "바닐라몬드:위대한 통치자":   {"passive": {"ult_dmg": 0.60}, "sub": VANILLA_MONDE_SUB},
    "바닐라몬드:거침없는 습격자": {"passive": {"special_dmg": 0.40, "ult_dmg": 0.20}, "sub": VANILLA_MONDE_SUB},
    "바닐라몬드:영예로운 기사도": {"passive": {"basic_dmg": 0.40, "special_dmg": 0.20}, "sub": VANILLA_MONDE_SUB},
    "바닐라몬드:돌진하는 전차":   {"passive": {"final_dmg": 0.12, "atk_spd": 0.12, "move_spd": 0.12}, "sub": VANILLA_MONDE_SUB},
    "바닐라몬드:추격자의 결의":   {"passive": {"final_dmg": 0.30, "move_spd": 0.10}, "sub": VANILLA_MONDE_SUB},
}

# =====================================================
# 6) 공통: 아티팩트
# =====================================================

ARTIFACTS = {
    "NONE": {"stats": {}},

    "끝나지 않는 죽음의 밤": {
        "stats": {
            "atk_pct": 0.40,
            "crit_rate": 0.30,
            "crit_dmg": 0.80,
        }
    },

    "이어지는 마음": {
        "stats": {
            "atk_pct": 0.40,
            "debuff_amp": 0.25,
            "crit_dmg": 0.50,
        },
        "emeraldin": {
            "crit_dmg_bonus": 0.40,
            "duration": 18.0,
        }
    },
}

def apply_artifact(stats: Dict[str, float], artifact_name: str):
    a = ARTIFACTS.get(artifact_name, ARTIFACTS["NONE"])
    add(stats, a.get("stats", {}))

# =====================================================
# 7) 공통: 유니크 설탕유리조각
# =====================================================

UNIQUE_SHARDS = {
    "NONE": {"type": "none", "allowed_roles": ["any"], "allowed_types": ["any"]},

    "아르고의 기억": {
        "type": "argo",
        "allowed_roles": ["dps"],
        "allowed_types": ["slash", "strike"],
        "aura_duration": ARGON_AURA_DURATION,
        "proc_hits": ARGON_PROC_HITS,
        "bonus_per_proc": ARGON_BONUS_PER_PROC,
        "dmg_reduction": ARGON_DMG_REDUCTION,
    },

    "아스파라거스 숲의 기억": {
        "type": "asparagus_forest",
        "allowed_roles": ["dps"],
        "allowed_types": ["any"],
        "atk_per_stack": 0.012,
        "max_stacks": 10,
        "tornado_mult": 4.5,
    },

    "나비스의 기억": {
        "type": "navis_memory",
        "allowed_roles": ["strike"],
        "allowed_types": ["any"],
        "strike_bonus": NAVIS_ENHANCED_MARK_STRIKE_BONUS,  # 0.30
    },

    "로스베이컨맛 쿠키의 기억": {
        "type": "ross_bacon_memory",
        "allowed_roles": ["dps"],
        "allowed_types": ["shoot", "magic"],
        "proc_interval": 3.0,
        "projectile_coeff": 4.0 * 3,
    },
}

def is_unique_allowed(cookie_name_kr: str, unique_name: str) -> bool:
    u = UNIQUE_SHARDS[unique_name]
    roles = u.get("allowed_roles", ["any"])
    types = u.get("allowed_types", ["any"])

    if "any" in roles and "any" in types:
        return True

    role = COOKIE_ROLE.get(cookie_name_kr, "unknown")
    ctype = COOKIE_TYPE.get(cookie_name_kr, "unknown")

    role_ok = ("any" in roles) or (role in roles)
    type_ok = ("any" in types) or (ctype in types)
    return role_ok and type_ok

def apply_unique(stats: Dict[str, float], cookie_name_kr: str, unique_name: str):
    if unique_name not in UNIQUE_SHARDS:
        return

    u = UNIQUE_SHARDS[unique_name]
    ut = u.get("type", "none")
    if ut == "none":
        return

    if not is_unique_allowed(cookie_name_kr, unique_name):
        return

    stats.setdefault("unique_extra_coeff", 0.0)

    if ut == "asparagus_forest":
        atk_bonus = float(u.get("atk_per_stack", 0.0)) * int(u.get("max_stacks", 0))
        stats["atk_pct"] += atk_bonus

        ult_cd = float(ULT_COOLDOWN.get(cookie_name_kr, 30.0))
        if ult_cd > 0:
            stats["unique_extra_coeff"] += float(u.get("tornado_mult", 0.0)) / ult_cd

    elif ut == "navis_memory":
        stats["element_strike_dmg"] += float(u.get("strike_bonus", 0.0))

    elif ut == "argo":
        aura_dur = float(u.get("aura_duration", ARGON_AURA_DURATION))
        proc_hits = float(u.get("proc_hits", ARGON_PROC_HITS))
        bonus_per_proc = float(u.get("bonus_per_proc", ARGON_BONUS_PER_PROC))

        ult_cd = float(ULT_COOLDOWN.get(cookie_name_kr, 30.0))
        uptime = 0.0
        if ult_cd > 0 and aura_dur > 0:
            uptime = clamp(aura_dur / ult_cd, 0.0, 1.0)

        hits_per_sec = float(COOKIE_HITS_PER_SEC.get(cookie_name_kr, 1.0))
        if proc_hits <= 0:
            proc_hits = 5.0

        procs_per_sec = (hits_per_sec / proc_hits) * uptime
        stats["unique_extra_coeff"] += bonus_per_proc * procs_per_sec

    elif ut == "ross_bacon_memory":
        interval = float(u.get("proc_interval", 3.0))
        coeff = float(u.get("projectile_coeff", 12.0))

        if interval > 0:
            stats["unique_extra_coeff"] += coeff / interval

        stats["_ross_enabled"] = 1.0
        stats["_ross_proc_interval"] = interval
        stats["_ross_projectile_coeff"] = coeff

# =====================================================
# 8) 공통: 파티 버프/디버프
# =====================================================

def apply_party_buffs(stats: dict, party: List[str], main_cookie_name: str):
    # [1] 이슬 파티 (또는 메인)
    if ("이슬맛 쿠키" in party) or (main_cookie_name == "이슬맛 쿠키"):
        u_cd = get_uptime("PARTY_ISLE_CRITDMG_0p56")
        stats["crit_dmg"] += 0.56 * u_cd
        stats["atc_pct"] += 0.224

        u_seaz = get_uptime("PARTY_ISLE_SEAZ_ATK25_ALL30")
        stats["final_atk_mult"] += 0.25 * u_seaz
        stats["all_elem_dmg"]   += 0.30 * u_seaz

    # [2] 윈파 파티 (또는 메인)
    if ("윈드파라거스 쿠키" in party) or (main_cookie_name == "윈드파라거스 쿠키"):
        u = get_uptime("PARTY_WIND_ARMOR224_FINAL3125_CRIT40")
        stats["crit_dmg"]  += 0.40   * u

        if GOLDEN_SET_TEAM_AURA:
            stats["debuff_amp"]         += 0.15
            stats["element_strike_dmg"] += 0.25

# =====================================================
# 9) 공통: 딜 공식
# =====================================================

def base_damage_only(stats: Dict[str, float]) -> float:
    cr = clamp(stats["crit_rate"], 0.0, 1.0)
    cd = max(1.0, stats["crit_dmg"])
    armor_pen = clamp(stats["armor_pen"], 0.0, 0.8)

    OA = stats["base_atk"]
    EA = stats["base_elem_atk"] + stats["elem_atk"]

    atk_pct = 1 + stats["base_atk_pct"] + stats["atk_pct"]
    final_atk = 1 + stats["final_atk_mult"]

    crit_mult = 1 + cr * (cd - 1)

    def_reduction = clamp(stats.get("def_reduction", 0.0), 0.0, 0.50)
    defense_mult = 1 / (1 + 2.5 * (1 - armor_pen) * (1 - def_reduction))

    return (
        (OA + EA)
        * atk_pct
        * final_atk
        * (1 + stats["all_elem_dmg"])
        * crit_mult
        * defense_mult
        * (1 + stats["final_dmg"])
    )

def skill_bonus_mult(stats: Dict[str, float], skill_type: str) -> float:
    if skill_type == "basic":
        return 1.0 + stats.get("basic_dmg", 0.0)
    if skill_type == "special":
        return 1.0 + stats.get("special_dmg", 0.0)
    if skill_type == "ult":
        return 1.0 + stats.get("ult_dmg", 0.0)
    if skill_type == "passive":
        return 1.0 + stats.get("passive_dmg", 0.0)
    return 1.0

STRIKE_RATIO_MATCH    = 1.0 / 8.0
STRIKE_RATIO_MISMATCH = 1.0 / 16.0

def strike_total_from_direct(
    direct_damage: float,
    cookie_name_kr: str,
    stats: Dict[str, float],
    party: List[str]
) -> float:
    has_wind_marker = ("윈드파라거스 쿠키" in party) or (cookie_name_kr == "윈드파라거스 쿠키")
    if not has_wind_marker:
        return 0.0

    attacker_elem = COOKIE_ELEMENT.get(cookie_name_kr, "unknown")
    ratio = STRIKE_RATIO_MATCH if attacker_elem == WIND_MARK_ELEMENT else STRIKE_RATIO_MISMATCH

    resist_mult = 1.0 - clamp(BOSS_MARK_ELEMENT_RESIST, 0.0, 0.95)
    es = float(stats.get("element_strike_dmg", 0.0))

    return direct_damage * ratio * resist_mult * (1.0 + es)

# =====================================================
# 10) 공통: 스탯 빌더 / 제약
# =====================================================

def build_stats_for_combo(
    cookie_name_kr: str,
    base: dict,
    shards: Dict[str, int],
    potentials: Dict[str, int],
    equip_name: str,
    seaz_name: Optional[str],
    unique_name: str,
    party: List[str],
    artifact_name: str,
) -> Dict[str, float]:

    stats: Dict[str, float] = {
        "base_atk": base["atk"],
        "base_elem_atk": base["elem_atk"],
        "base_atk_pct": base["atk_pct"],
        "crit_rate": base["crit_rate"],
        "crit_dmg": base["crit_dmg"],
        "armor_pen": base["armor_pen"],

        "atk_pct": 0.0,
        "elem_atk": 0.0,
        "all_elem_dmg": 0.0,
        "def_reduction": 0.0,
        "final_dmg": 0.0,
        "final_atk_mult": 0.0,

        "basic_dmg": 0.0,
        "special_dmg": 0.0,
        "ult_dmg": 0.0,
        "passive_dmg": 0.0,

        "element_strike_dmg": 0.0,

        "buff_amp": 0.0,
        "debuff_amp": 0.0,

        "unique_extra_coeff": 0.0,

        "sugar_set_enabled": 0.0,
        "sugar_set_proc_chance": 0.0,
        "sugar_set_proc_coeff": 0.0,
    }

    equip = EQUIP_SETS[equip_name]
    for part in ["head", "top", "bottom"]:
        add(stats, equip[part]["base"])
        add(stats, equip[part]["unique"])
    add(stats, equip["set_effect"]["base"])

    if equip_name == "달콤한 설탕 깃털복":
        stats["sugar_set_enabled"] = 1.0
        stats["sugar_set_proc_chance"] = SUGAR_SET_PROC_CHANCE
        stats["sugar_set_proc_coeff"] = SUGAR_SET_PROC_ATK_COEFF

    if seaz_name is not None:
        seaz = SEAZNITES[seaz_name]
        add(stats, seaz.get("sub", {}))
        passive = seaz.get("passive", {})

        if "ally_all_elem_dmg" in passive:
            stats["all_elem_dmg"] += passive["ally_all_elem_dmg"]
        if "element_strike_dmg" in passive:
            stats["element_strike_dmg"] += passive["element_strike_dmg"]
        if "final_dmg" in passive:
            stats["final_dmg"] += passive["final_dmg"]

        for k in ["basic_dmg", "special_dmg", "ult_dmg", "passive_dmg"]:
            if k in passive:
                add_stat(stats, k, passive[k])

        if "final_dmg_stack" in passive and "max_stacks" in passive:
            stats["final_dmg"] += passive["final_dmg_stack"] * passive["max_stacks"]

    for k, slots in shards.items():
        if k in SHARD_INC:
            add_stat(stats, k, slots * SHARD_INC[k])

    stats["atk_pct"]   += potentials.get("atk_pct", 0) * POTENTIAL_INC["atk_pct"]
    stats["crit_rate"] += potentials.get("crit_rate", 0) * POTENTIAL_INC["crit_rate"]
    stats["crit_dmg"]  += potentials.get("crit_dmg", 0) * POTENTIAL_INC["crit_dmg"]
    stats["armor_pen"] += potentials.get("armor_pen", 0) * POTENTIAL_INC["armor_pen"]
    stats["elem_atk"]  += potentials.get("elem_atk", 0) * POTENTIAL_INC["elem_atk"]

    stats["buff_amp"]   += potentials.get("buff_amp", 0) * POTENTIAL_INC["buff_amp"]
    stats["debuff_amp"] += potentials.get("debuff_amp", 0) * POTENTIAL_INC["debuff_amp"]

    apply_artifact(stats, artifact_name)
    apply_unique(stats, cookie_name_kr, unique_name)
    apply_party_buffs(stats, party, cookie_name_kr)

    return stats

def is_valid_by_caps(stats: Dict[str, float]) -> bool:
    if stats["crit_rate"] > 1.0 + 1e-12:
        return False
    if stats["armor_pen"] > 0.80 + 1e-12:
        return False
    return True

# =====================================================
# (A) 윈드파라거스
# =====================================================

BASE_STATS_WIND = {
    "윈드파라거스 쿠키": {
        "atk": 635.0,
        "elem_atk": 0.0,
        "atk_pct": 0.0,
        "crit_rate": 0.457,
        "crit_dmg": 1.5,
        "armor_pen": 0.0
    }
}

WIND_TIME = {"B": 2.4, "S": 0.5, "U": 4.5, "C": 4.0}
WIND_SPECIAL_COEFF = 21.016
WIND_BASIC_COEFF = (0.383 * 3) + (0.554 * 7) + 4.544
WIND_ULT_COEFF = 7.242 * 5

WIND_LOYALTY_1_COEFF = 5.069 * 3
WIND_LOYALTY_2_COEFF = 3.266 * 6
WIND_CHARGE_COEFF = WIND_LOYALTY_1_COEFF + WIND_LOYALTY_2_COEFF
WIND_FREE_WING_COEFF = 2.60 * 30

WIND_ALWAYS_EMPOWERED_CHARGE = True

WIND_CYCLE_TOKENS = [
    "S", "U", "C",
    "B", "B", "B",
    "S", "B", "C",
    "B", "B", "B",
]

WIND_EMERALDIN_DEFAULT_DURATION = 18.0
WIND_EMERALDIN_DEFAULT_CRITDMG_BONUS = 0.40

def wind_compute_emeraldin_uptime(
    cycle_tokens: List[str],
    total_time: float,
    empowered_charge_count: int,
    duration: float
) -> float:
    if empowered_charge_count <= 0 or total_time <= 0:
        return 0.0
    interval = total_time / empowered_charge_count
    if interval <= 0:
        return 1.0
    return clamp(duration / interval, 0.0, 1.0)

def wind_allowed_equips() -> List[str]:
    return ["황금 예복 세트"]

def wind_allowed_uniques() -> List[str]:
    return ["나비스의 기억"]

def wind_allowed_potentials() -> List[Dict[str, int]]:
    return [{
        "debuff_amp": 4,
        "crit_rate": 1,
        "atk_pct": 1,
        "elem_atk": 2,
        "crit_dmg": 0,
        "armor_pen": 0,
        "buff_amp": 0,
    }]

def wind_allowed_artifacts() -> List[str]:
    return ["이어지는 마음"]

def wind_allowed_seaz() -> List[str]:
    return ["페퍼루비:믿음직한 브리더", "리치코랄:믿음직한 브리더"]

def wind_generate_shard_candidates(step: int = 7) -> List[Dict[str, int]]:
    steps = list(range(0, NORMAL_SLOTS + 1, step))
    if steps[-1] != NORMAL_SLOTS:
        steps.append(NORMAL_SLOTS)

    candidates: List[Dict[str, int]] = []
    for a in steps:
        for b in steps:
            for c in steps:
                for d in steps:
                    for e in steps:
                        for f in steps:
                            used = a + b + c + d + e + f
                            if used > NORMAL_SLOTS:
                                continue
                            g = NORMAL_SLOTS - used
                            candidates.append({
                                "crit_rate": a,
                                "crit_dmg": b,
                                "all_elem_dmg": c,
                                "basic_dmg": d,
                                "special_dmg": e,
                                "atk_pct": f,
                                "elem_atk": g,
                                "ult_dmg": 0,
                                "passive_dmg": 0,
                            })
    return candidates

def wind_cycle_damage(stats: Dict[str, float], party: List[str], artifact_name: str) -> Dict[str, float]:
    total_time = 0.0
    empowered_charge_count = 0

    for tok in WIND_CYCLE_TOKENS:
        if tok == "B":
            total_time += WIND_TIME["B"]
        elif tok == "S":
            total_time += WIND_TIME["S"]
        elif tok == "U":
            total_time += WIND_TIME["U"]
        elif tok == "C":
            total_time += WIND_TIME["C"]
            if WIND_ALWAYS_EMPOWERED_CHARGE:
                empowered_charge_count += 1

    emeraldin_bonus = 0.0
    if artifact_name == "이어지는 마음":
        em = ARTIFACTS[artifact_name].get("emeraldin", {})
        dur = float(em.get("duration", WIND_EMERALDIN_DEFAULT_DURATION))
        cd_bonus = float(em.get("crit_dmg_bonus", WIND_EMERALDIN_DEFAULT_CRITDMG_BONUS))

        uptime = wind_compute_emeraldin_uptime(
            cycle_tokens=WIND_CYCLE_TOKENS,
            total_time=total_time,
            empowered_charge_count=empowered_charge_count,
            duration=dur
        )
        emeraldin_bonus = cd_bonus * uptime

    local_stats = dict(stats)
    local_stats["crit_dmg"] += emeraldin_bonus

    unit = base_damage_only(local_stats)

    direct = 0.0
    breakdown = {"basic": 0.0, "special": 0.0, "ult": 0.0, "charge": 0.0, "strike": 0.0, "unique": 0.0}

    def do_basic():
        nonlocal direct
        dmg = unit * WIND_BASIC_COEFF * skill_bonus_mult(local_stats, "basic")
        direct += dmg
        breakdown["basic"] += dmg

    def do_special():
        nonlocal direct
        dmg = unit * WIND_SPECIAL_COEFF * skill_bonus_mult(local_stats, "special")
        direct += dmg
        breakdown["special"] += dmg

    def do_ult():
        nonlocal direct
        dmg = unit * WIND_ULT_COEFF * skill_bonus_mult(local_stats, "ult")
        direct += dmg
        breakdown["ult"] += dmg

    def do_charge():
        nonlocal direct
        coeff = WIND_FREE_WING_COEFF if WIND_ALWAYS_EMPOWERED_CHARGE else WIND_CHARGE_COEFF
        dmg = unit * coeff * skill_bonus_mult(local_stats, "special")
        direct += dmg
        breakdown["charge"] += dmg

    for tok in WIND_CYCLE_TOKENS:
        if tok == "B":
            do_basic()
        elif tok == "S":
            do_special()
        elif tok == "U":
            do_ult()
        elif tok == "C":
            do_charge()

    strike = strike_total_from_direct(direct, "윈드파라거스 쿠키", local_stats, party)
    breakdown["strike"] = strike

    unique_total = unit * local_stats.get("unique_extra_coeff", 0.0) * total_time
    breakdown["unique"] = unique_total

    total_damage = direct + strike + unique_total
    dps = total_damage / total_time if total_time > 0 else 0.0

    return {
        "total_damage": total_damage,
        "total_time": total_time,
        "dps": dps,
        "breakdown_basic": breakdown["basic"],
        "breakdown_special": breakdown["special"],
        "breakdown_ult": breakdown["ult"],
        "breakdown_charge": breakdown["charge"],
        "breakdown_strike": breakdown["strike"],
        "breakdown_unique": breakdown["unique"],
        "_emeraldin_avg_critdmg_bonus": emeraldin_bonus,
        "_emeraldin_empowered_charge_count": empowered_charge_count,
    }

def optimize_wind_cycle(
    seaz_name: str,
    party: List[str],
    step: int = 7,
    progress_cb: Optional[Callable[[float], None]] = None,
    equip_override: Optional[str] = None,
) -> Optional[dict]:
    cookie = "윈드파라거스 쿠키"
    base = BASE_STATS_WIND[cookie].copy()

    equips = wind_allowed_equips()
    uniques = wind_allowed_uniques()
    potentials = wind_allowed_potentials()
    artifacts = wind_allowed_artifacts()
    shard_candidates = wind_generate_shard_candidates(step=step)

    total = max(1, len(equips) * len(artifacts) * len(uniques) * len(shard_candidates) * len(potentials))
    done = 0
    tick = max(1, total // 250)

    def _emit(p: float):
        if progress_cb is None:
            return
        try:
            progress_cb(p)
        except Exception:
            pass

    _emit(0.0)
    best = None

    for equip in equips:
        for artifact_name in artifacts:
            for unique_name in uniques:
                for shards in shard_candidates:
                    for pot in potentials:
                        done += 1
                        if (done % tick) == 0:
                            _emit(done / total)

                        stats = build_stats_for_combo(
                            cookie_name_kr=cookie,
                            base=base,
                            shards=shards,
                            potentials=pot,
                            equip_name=equip,
                            seaz_name=seaz_name,
                            unique_name=unique_name,
                            party=party,
                            artifact_name=artifact_name,
                        )
                        if not is_valid_by_caps(stats):
                            continue

                        cycle = wind_cycle_damage(stats, party, artifact_name)

                        cur = {
                            "cookie": cookie,
                            "dps": cycle["dps"],
                            "cycle_total_damage": cycle["total_damage"],
                            "cycle_total_time": cycle["total_time"],
                            "cycle_breakdown": cycle,
                            "equip": equip,
                            "seaz": seaz_name,
                            "unique": unique_name,
                            "artifact": artifact_name,
                            "shards": shards,
                            "potentials": pot,
                            "party": party,
                            "stats": stats,
                        }

                        if best is None or cur["dps"] > best["dps"]:
                            best = cur

    _emit(1.0)
    return best

# =====================================================
# (B) 멜랑크림
# =====================================================

BASE_STATS_MELAN = {
    "멜랑크림 쿠키": {
        "atk": 646.0,
        "elem_atk": 0.0,
        "atk_pct": 0.0,
        "crit_rate": 0.25,
        "crit_dmg": 1.875,
        "armor_pen": 0.0
    }
}

MELAN_BASIC_NORMAL = [1.704, 1.704, 3.067, 3.408 + 4.544]
MELAN_BASIC_PRIMA  = [2.726, 2.726, 4.899, 5.453 + 7.270]

MELAN_SPECIAL_NORMAL_COEFF = (4.26 * 5) + 10.65
MELAN_ULT_NORMAL_COEFF     = (7.81 * 6) + 35.50
MELAN_SPECIAL_PRIMA_AS_PASSIVE_COEFF = 73.6

PASSIVE_TIER_COEFF = {
    0.25: 6.816,
    0.50: 7.952,
    0.75: 11.36 * 2,
}

PRIMA_ENTRY_COEFF = 11.36
BREATH_GAIN_PER_BASIC_HIT = 0.05

MELAN_CYCLE_TOKENS = [
    "S", "U", "B4", "B4", "U",
    "S", "B4", "B4",
    "S", "B4", "B4", "B4", "B4",
    "S", "B4", "B4", "B4", "B4",
    "S"
]

MELAN_TIME = {"B4": 1.20, "S": 1.5, "U": 4.23}

def melan_allowed_equips() -> List[str]:
    return ["달콤한 설탕 깃털복", "미지의 방랑자", "수상한 사냥꾼", "시간관리국의 제복"]

def melan_allowed_uniques() -> List[str]:
    res = ["NONE"]
    for name in UNIQUE_SHARDS.keys():
        if name == "NONE":
            continue
        if is_unique_allowed("멜랑크림 쿠키", name):
            res.append(name)
    return res

def melan_allowed_artifacts() -> List[str]:
    return ["끝나지 않는 죽음의 밤"]

def melan_generate_potentials_common() -> List[Dict[str, int]]:
    TOTAL = 8
    FIXED_ELEM = 2
    FREE = TOTAL - FIXED_ELEM

    keys = ["atk_pct", "crit_rate", "crit_dmg", "armor_pen"]
    cap = {"armor_pen": min(4, FREE)}

    res: List[Dict[str, int]] = []

    def dfs(i: int, remain: int, cur: Dict[str, int]):
        if i == len(keys):
            if remain == 0:
                out = dict(cur)
                out["elem_atk"] = FIXED_ELEM
                out["buff_amp"] = 0
                out["debuff_amp"] = 0
                res.append(out)
            return

        k = keys[i]
        lim = remain
        if k in cap:
            lim = min(lim, cap[k])

        for x in range(lim + 1):
            cur[k] = x
            dfs(i + 1, remain - x, cur)
        cur.pop(k, None)

    dfs(0, FREE, {})
    return res

def melan_generate_shard_candidates(step: int = 7) -> List[Dict[str, int]]:
    steps = list(range(0, NORMAL_SLOTS + 1, step))
    if steps[-1] != NORMAL_SLOTS:
        steps.append(NORMAL_SLOTS)

    candidates: List[Dict[str, int]] = []
    for cr in steps:
        for cd in steps:
            for ae in steps:
                for ap in steps:
                    for bd in steps:
                        for ud in steps:
                            for pd in steps:
                                used = cr + cd + ae + ap + bd + ud + pd
                                if used > NORMAL_SLOTS:
                                    continue
                                ea = NORMAL_SLOTS - used
                                candidates.append({
                                    "crit_rate": cr,
                                    "crit_dmg": cd,
                                    "all_elem_dmg": ae,
                                    "atk_pct": ap,
                                    "basic_dmg": bd,
                                    "ult_dmg": ud,
                                    "passive_dmg": pd,
                                    "elem_atk": ea,
                                    "special_dmg": 0,
                                })
    return candidates

def melan_damage_for_token(
    stats: Dict[str, float],
    token: str,
    is_prima: bool,
    is_transform_ult: bool
) -> Tuple[float, float, bool, Dict[str, float]]:
    unit = base_damage_only(stats)
    b = {"basic": 0.0, "special": 0.0, "ult": 0.0, "passive": 0.0}

    if token == "B4":
        coeffs = MELAN_BASIC_PRIMA if is_prima else MELAN_BASIC_NORMAL

        # 프리마 상태 기본공격은 패시브 피해 취급
        mult_type = "passive" if is_prima else "basic"

        dmg = 0.0
        for c in coeffs:
            dmg += unit * c * skill_bonus_mult(stats, mult_type)

        if is_prima:
            b["passive"] = dmg
        else:
            b["basic"] = dmg

        return dmg, MELAN_TIME["B4"], is_prima, b

    if token == "S":
        if is_prima:
            # 프리마 상태 S는 패시브 피해 취급
            coeff = MELAN_SPECIAL_PRIMA_AS_PASSIVE_COEFF
            dmg = unit * coeff * skill_bonus_mult(stats, "passive")
            b["passive"] = dmg
            return dmg, MELAN_TIME["S"], is_prima, b
        else:
            coeff = MELAN_SPECIAL_NORMAL_COEFF
            dmg = unit * coeff * skill_bonus_mult(stats, "special")
            b["special"] = dmg
            return dmg, MELAN_TIME["S"], is_prima, b

    if token == "U":
        if is_transform_ult:
            # 프리마돈나 돌입 피해는 패시브 피해 취급
            entry = unit * PRIMA_ENTRY_COEFF * skill_bonus_mult(stats, "passive")
            b["passive"] = entry
            return entry, MELAN_TIME["U"], True, b
        else:
            coeff = MELAN_ULT_NORMAL_COEFF
            dmg = unit * coeff * skill_bonus_mult(stats, "ult")
            b["ult"] = dmg
            return dmg, MELAN_TIME["U"], is_prima, b

    return 0.0, 0.0, is_prima, b

def melan_cycle_damage(stats: Dict[str, float], party: List[str]) -> Dict[str, float]:
    total_direct = 0.0
    total_time = 0.0

    ult_count = 0
    is_prima = False

    breakdown = {
        "basic": 0.0,
        "special": 0.0,
        "ult": 0.0,
        "passive": 0.0,
        "proc": 0.0,
        "strike": 0.0,
        "unique": 0.0,
    }

    breath = 0.0
    eps = 1e-9

    def passive_proc_damage(prev: float, new: float) -> float:
        unit = base_damage_only(stats)
        pdmg = 0.0
        for tier in (0.25, 0.50, 0.75):
            if prev + eps < tier <= new + eps:
                coeff = PASSIVE_TIER_COEFF.get(tier, 0.0)
                # 언데드/멜랑노바/종말의 도래 = 패시브 피해
                pdmg += unit * coeff * skill_bonus_mult(stats, "passive")
        return pdmg

    def normalize_breath(x: float) -> float:
        return 0.0 if x >= 1.0 - eps else x

    for tok in MELAN_CYCLE_TOKENS:
        if tok == "U":
            ult_count += 1
            is_transform = (ult_count == 2)

            prev_prima = is_prima
            dmg, t, next_prima, b = melan_damage_for_token(stats, tok, is_prima, is_transform)

            total_direct += dmg
            total_time += t

            breakdown["ult"] += b["ult"]
            breakdown["passive"] += b["passive"]

            if (not prev_prima) and next_prima:
                breath = 0.0

            is_prima = next_prima
            continue

        if tok == "S":
            dmg, t, is_prima, b = melan_damage_for_token(stats, tok, is_prima, False)
            total_direct += dmg
            total_time += t

            breakdown["special"] += b["special"]
            breakdown["passive"] += b["passive"]
            continue

        if tok == "B4":
            unit = base_damage_only(stats)
            coeffs = MELAN_BASIC_PRIMA if is_prima else MELAN_BASIC_NORMAL
            total_time += MELAN_TIME["B4"]

            # 프리마 기본공격 = 패시브 배율
            mult_type = "passive" if is_prima else "basic"

            for c in coeffs:
                hdmg = unit * c * skill_bonus_mult(stats, mult_type)
                total_direct += hdmg

                if is_prima:
                    breakdown["passive"] += hdmg
                else:
                    breakdown["basic"] += hdmg

                # 프리마 상태면 숨결/티어패시브/설탕셋 proc 금지(기존 유지)
                if is_prima:
                    continue

                prev = breath
                new = prev + BREATH_GAIN_PER_BASIC_HIT

                pdmg = passive_proc_damage(prev, new)
                if pdmg > 0:
                    total_direct += pdmg
                    breakdown["passive"] += pdmg

                breath = normalize_breath(new)

                # 설탕셋 EV(기본공 적중마다 기대값 추가)
                if stats.get("sugar_set_enabled", 0.0) > 0.0:
                    proc = unit * stats.get("sugar_set_proc_coeff", 0.0) * stats.get("sugar_set_proc_chance", 0.0)
                    total_direct += proc
                    breakdown["proc"] += proc

            continue

    strike = strike_total_from_direct(total_direct, "멜랑크림 쿠키", stats, party)
    breakdown["strike"] = strike

    unit = base_damage_only(stats)
    unique_total = unit * stats.get("unique_extra_coeff", 0.0) * total_time
    breakdown["unique"] = unique_total

    total_damage = total_direct + strike + unique_total
    dps = total_damage / total_time if total_time > 0 else 0.0

    return {
        "total_damage": total_damage,
        "total_time": total_time,
        "dps": dps,
        "breakdown_basic": breakdown["basic"],
        "breakdown_special": breakdown["special"],
        "breakdown_ult": breakdown["ult"],
        "breakdown_passive": breakdown["passive"],
        "breakdown_proc": breakdown["proc"],
        "breakdown_strike": breakdown["strike"],
        "breakdown_unique": breakdown["unique"],
    }

def optimize_melan_cycle(
    seaz_name: str,
    party: List[str],
    step: int = 7,
    progress_cb: Optional[Callable[[float], None]] = None,
    equip_override: Optional[Union[str, List[str]]] = None,
) -> Optional[dict]:
    cookie = "멜랑크림 쿠키"
    base = BASE_STATS_MELAN[cookie].copy()

    equips = melan_allowed_equips()
    if equip_override and str(equip_override).strip():
        equips = [str(equip_override).strip()]

    uniques = melan_allowed_uniques()
    potentials = melan_generate_potentials_common()
    artifacts = melan_allowed_artifacts()
    shard_candidates = melan_generate_shard_candidates(step=step)

    total = max(
        1,
        len(equips) * len(artifacts) * len(uniques) * len(shard_candidates) * len(potentials)
    )
    done = 0
    tick = max(1, total // 250)

    def _emit(p: float):
        if progress_cb is None:
            return
        try:
            progress_cb(p)
        except Exception:
            pass

    _emit(0.0)
    best = None

    for equip in equips:
        for artifact_name in artifacts:
            for unique_name in uniques:
                for shards in shard_candidates:
                    for pot in potentials:
                        done += 1
                        if (done % tick) == 0:
                            _emit(done / total)

                        stats = build_stats_for_combo(
                            cookie_name_kr=cookie,
                            base=base,
                            shards=shards,
                            potentials=pot,
                            equip_name=equip,
                            seaz_name=seaz_name,
                            unique_name=unique_name,
                            party=party,
                            artifact_name=artifact_name,
                        )
                        if not is_valid_by_caps(stats):
                            continue

                        cycle = melan_cycle_damage(stats, party)

                        cur = {
                            "cookie": cookie,
                            "dps": cycle["dps"],
                            "cycle_total_damage": cycle["total_damage"],
                            "cycle_total_time": cycle["total_time"],
                            "cycle_breakdown": cycle,
                            "equip": equip,
                            "seaz": seaz_name,
                            "unique": unique_name,
                            "artifact": artifact_name,
                            "shards": shards,
                            "potentials": pot,
                            "party": party,
                            "stats": stats,
                        }

                        if best is None or cur["dps"] > best["dps"]:
                            best = cur

    _emit(1.0)
    return best

# =====================================================
# (C) 이슬(보호막)
# =====================================================

ISLE_BASE_ATK = 577
ISLE_ELEM_SUM = 160
ISLE_ATKPCT_SUM = 1.22
ISLE_SHIELD_BASE_MULT = 1.008

FIXED_SEAZ_ISLE = "허브그린드:백마법사의 의지"

ISLE_FIXED_POT = {
    "elem_atk": 2,
    "atk_pct": 2,
    "buff_amp": 4,
    "crit_rate": 0,
    "crit_dmg": 0,
    "armor_pen": 0,
    "debuff_amp": 0,
}

def calc_isle_shield(elem_slots: int, atk_pct_slots: int, shield_slots: int) -> Tuple[float, float]:
    u = get_uptime("PARTY_ISLE_SEAZ_ATK25_ALL30")
    seaz_atk_pct = 0.25 * u

    total_elem = ISLE_ELEM_SUM + SHARD_INC["elem_atk"] * elem_slots
    total_atk_pct = ISLE_ATKPCT_SUM + SHARD_INC["atk_pct"] * atk_pct_slots + seaz_atk_pct

    final_atk = (ISLE_BASE_ATK + total_elem) * (1 + total_atk_pct)
    total_shield_pct = SHARD_INC["shield_pct"] * shield_slots
    final_shield = final_atk * (1 + total_shield_pct) * ISLE_SHIELD_BASE_MULT
    return final_atk, final_shield

def optimize_isle_shards_only(party: List[str]) -> dict:
    best = None
    for elem_slots in range(NORMAL_SLOTS + 1):
        for atk_pct_slots in range(NORMAL_SLOTS - elem_slots + 1):
            shield_slots = NORMAL_SLOTS - elem_slots - atk_pct_slots
            final_atk, final_shield = calc_isle_shield(elem_slots, atk_pct_slots, shield_slots)
            if best is None or final_shield > best["max_shield"]:
                best = {
                    "cookie": "이슬맛 쿠키",
                    "party": party,
                    "equip_fixed": "전설의 유령해적 세트",
                    "seaz_fixed": FIXED_SEAZ_ISLE,
                    "potentials_fixed": ISLE_FIXED_POT,
                    "final_atk": final_atk,
                    "max_shield": final_shield,
                    "shards": {
                        "elem_atk": elem_slots,
                        "atk_pct": atk_pct_slots,
                        "shield_pct": shield_slots,
                    }
                }
    return best
