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

    "PARTY_ISLE_ATK_0p224": {"mode": MODE_ALWAYS},

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
# 0.3) 전투/공식 파라미터
# =====================================================
DEFENSE_K = 2.5
RECOMMENDED_ELEM_MULT = 1.30

# ---- 속성강타(표식) 모델(설명문 기반)
# (A) 축적 비율: 동일속성 66.666%, 타속성 33.333%
MARK_ACCUM_SAME = 2.0 / 3.0
MARK_ACCUM_DIFF = 1.0 / 3.0

# (B) "표식 데미지는 축적 총량의 특정 비율"을
# 기존 코드의 결과(동일 1/8, 타속성 1/16)를 유지하도록 역산한 방출 계수
#  - 동일: (2/3) * X = 1/8  => X = 3/16
#  - 타속: (1/3) * X = 1/16 => X = 3/16
MARK_RELEASE_MULT = 3.0 / 16.0

# (C) 표식 자체의 '속성저항'(기존 상수 유지하되, 디버프로 깎일 수 있게 처리)
BOSS_MARK_ELEMENT_RESIST_DEFAULT = 0.40


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
    stats[k] = stats.get(k, 0.0) + float(v)

def add(stats: Dict[str, float], bonus: Dict[str, float]):
    """dict 형태 bonus를 stats에 누적."""
    for k, v in bonus.items():
        add_stat(stats, k, float(v))

# =====================================================
# Focus breakdown (치피/공퍼/공증% 출처 기록)
# =====================================================

FOCUS_BD_KEYS = ["buff_crit_dmg_raw", "buff_atk_pct_raw", "atk_pct"]
FOCUS_BD_LABEL = {
    "buff_crit_dmg_raw": "치피(버프)",
    "buff_atk_pct_raw": "공퍼(버프)",
    "atk_pct": "공퍼/공증%(장비스탯)",
}

def _bd_init(stats: Dict[str, float]) -> Dict[str, List[Dict[str, object]]]:
    """
    stats["_focus_bd"] = {
      key: [ {source, value, note}, ... ]
    }
    """
    bd = stats.get("_focus_bd")
    if not isinstance(bd, dict):
        bd = {k: [] for k in FOCUS_BD_KEYS}
        stats["_focus_bd"] = bd
    else:
        for k in FOCUS_BD_KEYS:
            bd.setdefault(k, [])
    return bd  # type: ignore

def bd_add(stats: Dict[str, float], key: str, value: float, source: str, note: str = ""):
    if key not in FOCUS_BD_KEYS:
        return
    if abs(float(value)) < 1e-15:
        return
    bd = _bd_init(stats)
    bd[key].append({
        "항목": FOCUS_BD_LABEL.get(key, key),
        "source": source,
        "value": float(value),
        "note": note,
    })

def bd_add_delta(stats: Dict[str, float], key: str, before: float, source: str, note: str = ""):
    after = float(stats.get(key, 0.0))
    bd_add(stats, key, after - float(before), source=source, note=note)

def get_focus_breakdown(stats: Dict[str, float]) -> Dict[str, List[Dict[str, object]]]:
    # UI에서 바로 쓰기 좋게
    bd = stats.get("_focus_bd")
    return bd if isinstance(bd, dict) else {}

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
    "atk_flat": 0.0,
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
        "set_effect": {"base": {"all_elem_dmg": 0.30, "def_reduction_raw": 0.10}}
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
    "NONE": {
        "base_stats": {},        # 기본옵션(장비스탯)
        "unique_stats": {},      # 고유능력인데 '스탯'으로 처리(증폭 X)
        "unique_buffs": {},      # 고유능력 버프(증폭 O)
    },

    "끝나지 않는 죽음의 밤": {
        # 기본옵션: 공격력 +40%  => 장비스탯 atk_pct
        "base_stats": {"atk_pct": 0.40},

        # 고유능력: 치확/치피 => 버프(증폭 O)
        "unique_buffs": {
            "crit_rate": 0.30,
            "crit_dmg": 0.80,
        }
    },

    "이어지는 마음": {
        "base_stats": {"atk_pct": 0.40},

        # debuff_amp는 버프가 아니라 "증폭 스탯"이라 unique_stats로
        "unique_stats": {"debuff_amp": 0.25},

        # 치피 50%는 고유능력
        "unique_buffs": {"crit_dmg": 0.50},

        "emeraldin": {
            "crit_dmg_bonus": 0.40,
            "duration": 18.0,
        }
    },

    "비에 젖은 과거" : {
        "base_stats": {"buff_amp": 0.16},
        "unique_stats": {},
        "unique_buffs": {
            "crit_dmg": 0.60,
        },
        # 소나기 발생 시 심연(모속피 +30%, 10초) -> 이슬 사이클에서 uptime 모델링
        "abyss": {
            "all_elem_dmg": 0.30,
            "duration": 10.0,
        }
    }
}

def apply_artifact(stats: Dict[str, float], artifact_name: str):
    a = ARTIFACTS.get(artifact_name, ARTIFACTS["NONE"])

    # 1) 기본옵션(장비스탯) / 고유스탯(증폭 X)
    add(stats, a.get("base_stats", {}))
    add(stats, a.get("unique_stats", {}))

    # --- breakdown: 아티 기본옵/고유스탯 중 atk_pct(장비스탯 축) ---
    bs = a.get("base_stats", {}) or {}
    us = a.get("unique_stats", {}) or {}
    if "atk_pct" in bs:
        bd_add(stats, "atk_pct", float(bs["atk_pct"]), source=f"아티:{artifact_name}", note="기본옵 atk%")
    if "atk_pct" in us:
        bd_add(stats, "atk_pct", float(us["atk_pct"]), source=f"아티:{artifact_name}", note="고유스탯 atk%")

    # 2) 고유 버프(증폭 O)
    BA = float(stats.get("buff_amp", 0.0))
    buff_scale = 1.0 + BA

    ub = a.get("unique_buffs", {}) or {}

    # apply_artifact() 안
    if "atk_pct" in ub:
        x = float(ub["atk_pct"])
        stats["buff_atk_pct_raw"] += x * buff_scale
        bd_add(stats, "buff_atk_pct_raw", x * buff_scale, source=f"아티:{artifact_name}", note="고유버프 공퍼")

    # 치확/치피/속피 버프: 가산
    if "crit_rate" in ub:
        stats["buff_crit_rate_raw"] += float(ub["crit_rate"]) * buff_scale

    if "crit_dmg" in ub:
        add_cd = float(ub["crit_dmg"]) * buff_scale
        stats["buff_crit_dmg_raw"] += add_cd
        bd_add(stats, "buff_crit_dmg_raw", add_cd, source=f"아티:{artifact_name}", note="고유버프 치피")

    if "all_elem_dmg" in ub:
        stats["buff_all_elem_dmg_raw"] += float(ub["all_elem_dmg"]) * buff_scale
            
    # 최종공/피해증가
    if "final_atk_mult" in ub:
        stats["final_atk_mult"] += float(ub["final_atk_mult"]) * buff_scale
    if "dmg_bonus" in ub:
        stats["dmg_bonus"] += float(ub["dmg_bonus"]) * buff_scale
    if "final_dmg" in ub:
        stats["final_dmg"] += float(ub["final_dmg"]) * buff_scale

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
        bd_add(stats, "atk_pct", atk_bonus, source=f"유니크:{unique_name}", note="공퍼(스택합)")

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
from typing import List

def apply_party_buffs(stats: dict, party: List[str], main_cookie_name: str):
    # =========================
    # 0) 안전: 기본 키 세팅
    # =========================
    stats.setdefault("buff_amp", 0.0)
    stats.setdefault("debuff_amp", 0.0)

    stats.setdefault("buff_crit_dmg_raw", 0.0)
    stats.setdefault("buff_atk_pct_raw", 0.0)
    stats.setdefault("buff_all_elem_dmg_raw", 0.0)

    stats.setdefault("final_atk_mult", 0.0)
    stats.setdefault("element_strike_dmg", 0.0)

    # (선택) 윈파 쪽에 방관/최공/치피 등을 쓰면 여기 raw 키도 필요
    stats.setdefault("buff_armor_pen_raw", 0.0)

    # =========================
    # 1) 중복 적용 방지 (뻥튀기 핵심 방지)
    # =========================
    applied = stats.setdefault("_applied_party_buffs", set())

    def _apply_once(tag: str, fn):
        if tag in applied:
            return
        fn()
        applied.add(tag)

    has_isle = ("이슬맛 쿠키" in party) or (main_cookie_name == "이슬맛 쿠키")
    has_wind = ("윈드파라거스 쿠키" in party) or (main_cookie_name == "윈드파라거스 쿠키")

    # =========================
    # 2) 증폭(amp) 소스 확정 반영
    # =========================
    def _apply_amp_sources():
        # [이슬] 버프 증폭 (너 기존 로직 유지)
        if has_isle:
            stats["buff_amp"] += 0.40  # 잠재력
            stats["buff_amp"] += 0.24  # 전용무기
            stats["buff_amp"] += 0.20  # 시즈나이트(가정)

        # [윈파] 디버프 증폭 + 세트 속성강타피해 (사용자 확정값)
        if has_wind:
            stats["debuff_amp"] += 0.40  # 장비 잠재력 총 40%
            stats["debuff_amp"] += 0.15  # 세트효과 15%
            stats["element_strike_dmg"] += 0.25  # 세트효과: 속성강타피해 +25%

    _apply_once("AMP_SOURCES", _apply_amp_sources)

    # =========================
    # 3) 확정된 amp로 scale 계산
    # =========================
    BA = float(stats.get("buff_amp", 0.0))
    DA = float(stats.get("debuff_amp", 0.0))
    buff_scale   = 1.0 + BA
    debuff_scale = 1.0 + DA  # (디버프 계열 수치에 곱할 때 사용)

    # =========================
    # 4) 파티 버프 적용 (raw에 누적)
    # =========================
    def _apply_isle_buffs():
        u_cd = get_uptime("PARTY_ISLE_CRITDMG_0p56")
        add_cd = 0.56 * u_cd * buff_scale
        stats["buff_crit_dmg_raw"] += add_cd
        bd_add(stats, "buff_crit_dmg_raw", add_cd, source="파티:이슬", note="치피 56%")

        u_atk = get_uptime("PARTY_ISLE_ATK_0p224")
        add_atk = 0.224 * u_atk * buff_scale
        stats["buff_atk_pct_raw"] += add_atk
        bd_add(stats, "buff_atk_pct_raw", add_atk, source="파티:이슬", note="공퍼 22.4%")

        u_seaz = get_uptime("PARTY_ISLE_SEAZ_ATK25_ALL30")
        stats["final_atk_mult"] += 0.25 * u_seaz * buff_scale
        stats["buff_all_elem_dmg_raw"] += 0.30 * u_seaz * buff_scale

    def _apply_wind_party_effects():
        u = get_uptime("PARTY_WIND_ARMOR224_FINAL3125_CRIT40")
        add_cd = 0.40 * u * buff_scale
        stats["buff_crit_dmg_raw"] += add_cd
        bd_add(stats, "buff_crit_dmg_raw", add_cd, source="파티:윈파", note="치피 40%")

    if has_isle:
        _apply_once("PARTY_ISLE", _apply_isle_buffs)

    if has_wind:
        _apply_once("PARTY_WIND", _apply_wind_party_effects)

    return stats


# =====================================================
# 9) 공통: 딜 공식
# =====================================================
def base_damage_only(stats: Dict[str, float]) -> float:
    # 치확 = (장비스탯 치확) + (버프 치확)
    promo_cr_mult = float(stats.get("promo_crit_rate_mult", 1.0))
    promo_ap_mult = float(stats.get("promo_armor_pen_mult", 1.0))

    cr = clamp(
        (float(stats.get("crit_rate", 0.0)) * promo_cr_mult) + float(stats.get("buff_crit_rate_raw", 0.0)),
        0.0, 1.0
    )

    armor_pen = clamp(float(stats.get("armor_pen", 0.0)) * promo_ap_mult, 0.0, 0.8)

    # 치피 = base + 버프치피
    cd_base = float(stats.get("crit_dmg", 1.0))
    cd = max(1.0, cd_base + float(stats.get("buff_crit_dmg_raw", 0.0)))

    # [A] 장비 공격력(Flat): base_atk + equip_atk_flat
    OA = float(stats.get("base_atk", 0.0)) + float(stats.get("equip_atk_flat", 0.0))

    # [B] 속성 공격력(별도 축)
    EA = float(stats.get("base_elem_atk", 0.0)) + float(stats.get("elem_atk", 0.0))

    # [C] 장비 공퍼(= 돌파 공퍼 + 장비/스탯 공퍼 합)
    promo_atk_mult = float(stats.get("promo_atk_pct_mult", 1.0))

    equip_atk_pct = (1.0 + float(stats.get("base_atk_pct", 0.0)) + float(stats.get("atk_pct", 0.0)))
    equip_atk_pct *= promo_atk_mult

    # [D] 버프 공퍼(합) -> 배율
    buff_atk_pct_raw = float(stats.get("buff_atk_pct_raw", 0.0))
    buff_atk_mult_sum = 1.0 + buff_atk_pct_raw

    # 레거시(혹시 다른 코드에서 buff_atk_mult를 직접 곱 누적했을 수도 있으니)
    buff_atk_mult_legacy = float(stats.get("buff_atk_mult", 1.0))

    # 둘 다 있으면 곱해서 보존(대부분 legacy=1.0이라 영향 없음)
    buff_atk_mult = buff_atk_mult_sum * buff_atk_mult_legacy

    # [E] 최종공
    final_atk = 1.0 + float(stats.get("final_atk_mult", 0.0))

    # [F] 치명 배율
    cd_mult = max(1.0, cd_base + float(stats.get("buff_crit_dmg_raw", 0.0)))
    cd_add  = cd_mult - 1.0
    crit_mult = 1.0 + cr * cd_add

    # -----------------------------
    # 디버프증폭 적용: 방깎/내성깎만
    # -----------------------------
    DA = float(stats.get("debuff_amp", 0.0))
    debuff_scale = 1.0 + DA

    def_reduction = clamp(float(stats.get("def_reduction_raw", 0.0)) * debuff_scale, 0.0, 0.95)

    # 방어 배율: 1 / (1 + K*(1-방관)*(1-방깎))
    defense_mult = 1.0 / (1.0 + DEFENSE_K * (1.0 - armor_pen) * (1.0 - def_reduction))

    # 속성 내성 배율: (1 - 내성 + 내성감소)
    boss_resist = float(stats.get("boss_elem_resist", 0.0))
    res_red = float(stats.get("elem_res_reduction_raw", 0.0)) * debuff_scale
    eff_resist = clamp(boss_resist - res_red, -0.95, 0.95)
    elem_res_mult = 1.0 - eff_resist

    # 속피(장비/스탯 + 버프속피)
    all_elem_dmg_total = float(stats.get("all_elem_dmg", 0.0)) + float(stats.get("buff_all_elem_dmg_raw", 0.0))

    # 피해량 / 최종피해
    dmg_bonus = float(stats.get("dmg_bonus", 0.0))
    final_dmg = float(stats.get("final_dmg", 0.0))

    # 추천 속성 배율(추천 속성일 때 recommended_mult=1.3 세팅)
    recommended_mult = float(stats.get("recommended_mult", 1.0))

    promo_final_mult = float(stats.get("promo_final_dmg_mult", 1.0))

    dmg_taken_inc = float(stats.get("dmg_taken_inc", 0.0))
    taken_mult = 1.0 + dmg_taken_inc

    return (
        (OA + EA)
        * equip_atk_pct
        * buff_atk_mult
        * final_atk
        * defense_mult
        * elem_res_mult
        * (1.0 + all_elem_dmg_total)
        * crit_mult
        * (1.0 + dmg_bonus)
        * (1.0 + final_dmg) 
        * promo_final_mult
        * recommended_mult
        * taken_mult
    )

def summarize_effective_stats(stats: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    """
    UI 표시용 '유효 스탯' 요약.
    - *_sum   : '표시용 합(가산 환산)'
    - *_equiv : '실제 곱 환산(=딜식에 들어가는 총 배율-1)'
    """
    s = stats or {}

    promo_cr_mult    = float(s.get("promo_crit_rate_mult", 1.0))
    promo_ap_mult    = float(s.get("promo_armor_pen_mult", 1.0))
    promo_atk_mult   = float(s.get("promo_atk_pct_mult", 1.0))
    promo_final_mult = float(s.get("promo_final_dmg_mult", 1.0))

    # ---- 공격력% 축 ----
    equip_atk_add  = float(s.get("base_atk_pct", 0.0)) + float(s.get("atk_pct", 0.0))
    equip_atk_mult = (1.0 + equip_atk_add) * promo_atk_mult

    buff_atk_pct_raw     = float(s.get("buff_atk_pct_raw", 0.0))
    buff_atk_mult_sum    = 1.0 + buff_atk_pct_raw
    buff_atk_mult_legacy = float(s.get("buff_atk_mult", 1.0))
    buff_atk_mult        = buff_atk_mult_sum * buff_atk_mult_legacy

    # 표시용 합(가산 환산)
    atk_pct_sum   = (equip_atk_mult - 1.0) + (buff_atk_mult - 1.0)
    # 실제 곱 환산
    atk_pct_equiv = (equip_atk_mult * buff_atk_mult) - 1.0

    # ---- 최종공(가산) ----
    final_atk_mult_add = float(s.get("final_atk_mult", 0.0))

    # ---- 치명 ----
    eff_cr = clamp((float(s.get("crit_rate", 0.0)) * promo_cr_mult) + float(s.get("buff_crit_rate_raw", 0.0)), 0.0, 1.0)
    eff_cd = max(1.0, float(s.get("crit_dmg", 1.0)) + float(s.get("buff_crit_dmg_raw", 0.0)))

    # ---- 속피(장비스탯+버프) ----
    eff_all_elem = float(s.get("all_elem_dmg", 0.0)) + float(s.get("buff_all_elem_dmg_raw", 0.0))

    # ---- 방관 ----
    eff_armor_pen = clamp(float(s.get("armor_pen", 0.0)) * promo_ap_mult, 0.0, 0.8)

    # ---- 디버프 증폭(방깎/내성깎/표식저항감소에만) ----
    DA = float(s.get("debuff_amp", 0.0))
    debuff_scale = 1.0 + DA

    eff_def_red      = clamp(float(s.get("def_reduction_raw", 0.0)) * debuff_scale, 0.0, 0.95)
    eff_elem_res_red = float(s.get("elem_res_reduction_raw", 0.0)) * debuff_scale
    eff_mark_res_red = float(s.get("mark_res_reduction_raw", 0.0)) * debuff_scale

    # ---- 피해량 ----
    eff_dmg_bonus = float(s.get("dmg_bonus", 0.0)) + float(s.get("buff_dmg_bonus_raw", 0.0))

    # ---- 최종피해 ----
    final_dmg_add   = float(s.get("final_dmg", 0.0)) + float(s.get("buff_final_dmg_raw", 0.0))
    final_dmg_sum   = final_dmg_add + (promo_final_mult - 1.0)
    final_dmg_equiv = (1.0 + final_dmg_add) * promo_final_mult - 1.0

    return {
        "numeric": {
            "equip_atk_mult": equip_atk_mult,
            "buff_atk_mult": buff_atk_mult,

            "atk_pct_sum": atk_pct_sum,
            "atk_pct_equiv": atk_pct_equiv,

            "final_atk_mult_add": final_atk_mult_add,

            "eff_crit_rate": eff_cr,
            "eff_crit_dmg": eff_cd,

            "eff_all_elem_dmg": eff_all_elem,
            "eff_armor_pen": eff_armor_pen,

            "eff_def_reduction": eff_def_red,
            "eff_elem_res_reduction": eff_elem_res_red,
            "eff_mark_res_reduction": eff_mark_res_red,

            "dmg_bonus": eff_dmg_bonus,

            "final_dmg_add": final_dmg_add,
            "promo_final_dmg_mult": promo_final_mult,
            "final_dmg_sum": final_dmg_sum,
            "final_dmg_equiv": final_dmg_equiv,

            "buff_amp": float(s.get("buff_amp", 0.0)),
            "debuff_amp": DA,
            "element_strike_dmg": float(s.get("element_strike_dmg", 0.0)),
        }
    }

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
    """
    속성강타(표식) 모델(설명 반영 요약)
    - 추천 속성과 무관
    - 디버프 증폭은 '방깎/내성깎'에만 적용(표식 데미지 자체는 debuff_amp 영향 X)
    - 동일속성은 데미지의 66.666%가 축적, 타속성은 33.333%가 축적
    - 실제 발동 시 축적 총량의 특정 비율(MARK_RELEASE_MULT)이 방출된다고 가정
      (이 값은 기존 1/8, 1/16 결과를 보존하도록 역산됨)
    - 표식 속성저항(기본 0.40) 적용, 표식저항감소 디버프가 있으면 반영 가능
    """

    # 표식은 "스트라이커"가 있어야 생김(현재는 윈파만 표식 제공한다고 가정)
    has_marker = ("윈드파라거스 쿠키" in party) or (cookie_name_kr == "윈드파라거스 쿠키")
    if not has_marker:
        return 0.0

    attacker_elem = COOKIE_ELEMENT.get(cookie_name_kr, "unknown")
    same = (attacker_elem == WIND_MARK_ELEMENT)

    # (1) 축적량
    accum_ratio = MARK_ACCUM_SAME if same else MARK_ACCUM_DIFF
    stored = direct_damage * accum_ratio

    # (2) 방출량(= stored의 일부가 속성강타로 변환된다고 가정)
    strike_base = stored * MARK_RELEASE_MULT

    # (3) 표식 속성저항(별도 적용)
    # 디버프증폭이 표식저항감소에도 적용되게 raw를 사용
    DA = float(stats.get("debuff_amp", 0.0))
    debuff_scale = 1.0 + DA
    mark_res_red = float(stats.get("mark_res_reduction_raw", 0.0)) * debuff_scale

    mark_resist = float(stats.get("boss_mark_resist", BOSS_MARK_ELEMENT_RESIST_DEFAULT))
    eff_mark_resist = clamp(mark_resist - mark_res_red, -0.95, 0.95)
    mark_res_mult = 1.0 - eff_mark_resist

    # (4) 속성강타 피해 증가(시즈나이트/오라 등)
    es = float(stats.get("element_strike_dmg", 0.0))

    return strike_base * mark_res_mult * (1.0 + es)

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

        # -----------------------------
        # 장비/스탯(= "공격력 증가" 계열 포함)
        # -----------------------------
        "atk_pct": 0.0,          # 장비 공퍼(설유/장비옵/아티 '공격력 증가' 등)
        "equip_atk_flat": 0.0,   # 장비 공격력(Flat) (잠재 '공격력', 아티 기본옵 공격력 등)
        "elem_atk": 0.0,         # 속성 공격력(별도 축)
        "all_elem_dmg": 0.0,     # 속피(장비/스탯 축)

        # -----------------------------
        # 버프(= 고유능력/파티/락스타/다크초코 등)
        #  - buff_amp 적용 대상
        #  - 공격력 버프는 "개별 곱"이므로 raw가 아니라 mult로 관리
        # -----------------------------
        "buff_atk_mult": 1.0,           # 버프 공격력: (1+x)*(1+y)*...
        "buff_atk_pct_raw": 0.0,        # 버프 공격력% 합(가산)  ex) 0.224 + 0.40 ...
        "buff_crit_rate_raw": 0.0,      # 버프 치확(가산)
        "buff_crit_dmg_raw": 0.0,       # 버프 치피(가산)
        "buff_all_elem_dmg_raw": 0.0,   # 버프 속피(가산)

        # -----------------------------
        # 디버프(= 방깎/내성깎) raw
        # 디버프증폭(debuff_amp)이 적용되는 축
        # -----------------------------
        "def_reduction_raw": 0.0,      # 방어력 감소 raw
        "elem_res_reduction_raw": 0.0, # 속성 내성 감소 raw
        "mark_res_reduction_raw": 0.0, # 표식 속성저항 감소 raw

        # -----------------------------
        # 기타 배율/축
        # -----------------------------
        "final_atk_mult": 0.0,     # 최종공(별도 축)
        "dmg_bonus": 0.0,          # 피해량 총합(=일반 피해증가)
        "final_dmg": float(base.get("final_dmg", 0.0)),        # 최종 피해

        "basic_dmg": 0.0,
        "special_dmg": 0.0,
        "ult_dmg": 0.0,
        "passive_dmg": 0.0,

        "element_strike_dmg": 0.0,

        "buff_amp": float(base.get("buff_amp", 0.0)),
        "debuff_amp": float(base.get("debuff_amp", 0.0)),

        # 보스 속성 내성(기본값: 0.0) — 필요하면 외부에서 세팅
        "boss_elem_resist": 0.0,
        "dmg_taken_inc": 0.0,  # 적이 받는 피해 증가(받피증) - 디버프증폭 영향 X

        # 추천 속성 여부(기본 1.0, 추천이면 1.3로 세팅)
        "recommended_mult": 1.0,

        "unique_extra_coeff": 0.0,

        "sugar_set_enabled": 0.0,
        "sugar_set_proc_chance": 0.0,
        "sugar_set_proc_coeff": 0.0,

        # 승급 배율(곱연산 축)
        "promo_crit_rate_mult": 1.0,
        "promo_armor_pen_mult": 1.0,
        "promo_atk_pct_mult": 1.0,
        "promo_final_dmg_mult": 1.0,
        "promo_prima_dmg_mult": 1.0,
    }

    # =====================================================
    # 승급 효과 : 전부 곱연산 축으로 기록
    # =====================================================
    if cookie_name_kr == "멜랑크림 쿠키" and MELAN_PROMO_ENABLED:
        stats["promo_crit_rate_mult"] *= MELAN_PROMO_CRIT_RATE_MULT
        stats["promo_armor_pen_mult"] *= MELAN_PROMO_ARMOR_PEN_MULT
        stats["promo_atk_pct_mult"]   *= MELAN_PROMO_ATK_PCT_MULT
        stats["promo_final_dmg_mult"] *= MELAN_PROMO_FINAL_DMG_MULT
        stats["promo_prima_dmg_mult"] *= MELAN_PROMO_PRIMA_DMG_MULT
        stats["_melan_promo"] = 1.0

    if cookie_name_kr == "윈드파라거스 쿠키" and WIND_PROMO_ENABLED:
        stats["crit_rate"] += WIND_PROMO_CRIT_RATE_ADD

        before_ap = float(stats.get("atk_pct", 0.0))
        stats["atk_pct"]   += WIND_PROMO_ATK_PCT_ADD
        bd_add_delta(stats, "atk_pct", before_ap, source="승급:윈파", note="공퍼 +10%")

        # def/hp는 딜에 직접 안 쓰더라도 스탯으로 기록
        stats["def_pct"] = float(stats.get("def_pct", 0.0)) + WIND_PROMO_DEF_PCT_ADD
        stats["hp_pct"]  = float(stats.get("hp_pct", 0.0))  + WIND_PROMO_HP_PCT_ADD

        stats["final_dmg"] += WIND_PROMO_FINAL_DMG_ADD
        stats["_wind_promo"] = 1.0

    # --- 장비에서 들어오는 atk_pct(공퍼/공증%)만 출처 기록 ---
    before_ap = float(stats.get("atk_pct", 0.0))

    equip = EQUIP_SETS[equip_name]
    for part in ["head", "top", "bottom"]:
        add(stats, equip[part]["base"])
        add(stats, equip[part]["unique"])
    add(stats, equip["set_effect"]["base"])

    bd_add_delta(stats, "atk_pct", before_ap, source=f"장비:{equip_name}")

    if equip_name == "달콤한 설탕 깃털복":
        stats["sugar_set_enabled"] = 1.0
        stats["sugar_set_proc_chance"] = SUGAR_SET_PROC_CHANCE
        stats["sugar_set_proc_coeff"] = SUGAR_SET_PROC_ATK_COEFF

    if seaz_name:
        seaz = SEAZNITES.get(seaz_name)
        if seaz:
            add(stats, seaz.get("sub", {}))
            passive = seaz.get("passive", {}) or {}

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

    # --- 설유(atk_pct) 출처 기록용 before ---
    before_ap_shard = float(stats.get("atk_pct", 0.0))

    for k, slots in shards.items():
        if k in SHARD_INC:
            add_stat(stats, k, slots * SHARD_INC[k])

    # --- 설유 atk%만 breakdown 기록(중복가산 방지: delta로 기록) ---
    ap_slots = int(shards.get("atk_pct", 0) or 0)
    if ap_slots > 0:
        bd_add_delta(
            stats,
            "atk_pct",
            before_ap_shard,
            source="설탕유리조각",
            note=f"atk_pct 슬롯 {ap_slots}칸"
        )

    pot_ap = potentials.get("atk_pct", 0) * POTENTIAL_INC["atk_pct"]
    if pot_ap:
        bd_add(stats, "atk_pct", pot_ap, source="잠재력", note=f"atk_pct {potentials.get('atk_pct',0)}개")
    stats["atk_pct"] += pot_ap
    stats["crit_rate"] += potentials.get("crit_rate", 0) * POTENTIAL_INC["crit_rate"]
    stats["crit_dmg"]  += potentials.get("crit_dmg", 0) * POTENTIAL_INC["crit_dmg"]
    stats["armor_pen"] += potentials.get("armor_pen", 0) * POTENTIAL_INC["armor_pen"]
    stats["elem_atk"]  += potentials.get("elem_atk", 0) * POTENTIAL_INC["elem_atk"]
    stats["equip_atk_flat"] += potentials.get("atk_flat", 0) * POTENTIAL_INC["atk_flat"]

    stats["buff_amp"]   += potentials.get("buff_amp", 0) * POTENTIAL_INC["buff_amp"]
    stats["debuff_amp"] += potentials.get("debuff_amp", 0) * POTENTIAL_INC["debuff_amp"]

    apply_artifact(stats, artifact_name)
    apply_unique(stats, cookie_name_kr, unique_name)
    apply_party_buffs(stats, party, cookie_name_kr)

    return stats

def is_valid_by_caps(stats: Dict[str, float]) -> bool:
    promo_cr_mult = float(stats.get("promo_crit_rate_mult", 1.0))
    promo_ap_mult = float(stats.get("promo_armor_pen_mult", 1.0))

    eff_cr = stats["crit_rate"] * promo_cr_mult
    eff_ap = stats["armor_pen"] * promo_ap_mult

    if eff_cr > 1.0 + 1e-12:
        return False
    if eff_ap > 0.80 + 1e-12:
        return False
    return True

# =====================================================
# (A) 윈드파라거스
# =====================================================

# [윈드파라거스] 승급 효과
WIND_PROMO_ENABLED = True
WIND_PROMO_CRIT_RATE_ADD = 0.10
WIND_PROMO_ATK_PCT_ADD   = 0.10
WIND_PROMO_DEF_PCT_ADD   = 0.10
WIND_PROMO_HP_PCT_ADD    = 0.10
WIND_PROMO_FINAL_DMG_ADD = 0.05

BASE_STATS_WIND = {
    "윈드파라거스 쿠키": {
        "atk": 635.0,
        "elem_atk": 0.0,
        "atk_pct": 0.52, # 전용무기 포함
        "crit_rate": 0.475,
        "crit_dmg": 1.5,
        "armor_pen": 0.0,
        "final_dmg": 0.30 # 전용무기 포함
    }
}

WIND_TIME = {"B": 2.4, "S": 0.5, "U": 4.5, "C": 4.0}
WIND_SPECIAL_COEFF = 21.016
WIND_BASIC_COEFF = (0.383 * 3) + (0.554 * 7) + 4.544
WIND_ULT_COEFF = 7.242 * 5

WIND_LOYALTY_1_COEFF = 5.069 * 3
WIND_LOYALTY_2_COEFF = 3.266 * 6

# 승급: 충성의 기류 공격 추가
WIND_LOYALTY_3_COEFF = 5.10 * (1 + 4)   # 510% + 510%x4 = 25.5

WIND_CHARGE_COEFF = WIND_LOYALTY_1_COEFF + WIND_LOYALTY_2_COEFF + WIND_LOYALTY_3_COEFF
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
    equips = _resolve_equip_list_override(equip_override, equips)
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

MELAN_PROMO_ENABLED = True

MELAN_PROMO_CRIT_RATE_MULT = 1.10   # 치확 *1.10
MELAN_PROMO_ARMOR_PEN_MULT = 1.08   # 방관 *1.08
MELAN_PROMO_ATK_PCT_MULT   = 1.10   # 공격력% 축 *1.10
MELAN_PROMO_FINAL_DMG_MULT = 1.05   # 최종피해 축 *1.05

# 개수 증가(= 기존 계수에 "배수"로 곱)
MELAN_PROMO_UNDEAD_EXTRA = 1        # 25%: 언데드 +1개 => 계수*(1+1)=2배(기존 1개 가정)
MELAN_PROMO_NOVA_EXTRA   = 2        # 50%: 멜랑노바 +2개 => 계수*(1+2)=3배(기존 1개 가정)
MELAN_PROMO_APOCALYPSE_X2 = True    # 75%: 종말 100%증가 => 2배

MELAN_PRELUDE_COEFF = 5.0  # [최후의 전주곡] 500% = 5.0

# 프리마 강화도 "곱"으로
MELAN_PROMO_PRIMA_DMG_MULT = 1.25   # 프리마 피해 *1.25

BASE_STATS_MELAN = {
    "멜랑크림 쿠키": {
        "atk": 710.0,
        "elem_atk": 0.0,
        "atk_pct": 0.52, # 전용무기 포함
        "crit_rate": 0.25,
        "crit_dmg": 1.875,
        "armor_pen": 0.08,
        "final_dmg": 0.30 # 전용무기 포함
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
    "S", "B4", "U", "B4", "U",
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

    prima_mult = float(stats.get("promo_prima_dmg_mult", 1.0))

    if token == "B4":
        coeffs = MELAN_BASIC_PRIMA if is_prima else MELAN_BASIC_NORMAL
        mult_type = "passive" if is_prima else "basic"

        dmg = 0.0
        for c in coeffs:
            hdmg = unit * c * skill_bonus_mult(stats, mult_type)

            # 프리마 기본공은 프리마 강화 배율 적용(원하면 유지)
            if is_prima:
                hdmg *= prima_mult
                b["passive"] += hdmg
            else:
                b["basic"] += hdmg

            dmg += hdmg

        return dmg, MELAN_TIME["B4"], is_prima, b

    if token == "S":
        if is_prima:
            coeff = MELAN_SPECIAL_PRIMA_AS_PASSIVE_COEFF
            dmg = unit * coeff * skill_bonus_mult(stats, "passive")
            dmg *= prima_mult
            b["passive"] += dmg
            return dmg, MELAN_TIME["S"], is_prima, b
        else:
            coeff = MELAN_SPECIAL_NORMAL_COEFF
            dmg = unit * coeff * skill_bonus_mult(stats, "special")
            # 비(프리마) S에는 prima_mult 곱하지 않음
            b["special"] += dmg
            return dmg, MELAN_TIME["S"], is_prima, b

    if token == "U":
        # 프리마돈나 돌입 U에서는 최후의 전주곡 미적용
        prelude = 0.0
        if (not is_prima) and (not is_transform_ult):
            prelude = unit * MELAN_PRELUDE_COEFF * skill_bonus_mult(stats, "ult")

        if is_transform_ult:
            # 프리마 돌입 피해(패시브 취급)만
            entry = unit * PRIMA_ENTRY_COEFF * skill_bonus_mult(stats, "passive")
            entry *= prima_mult 
            dmg = entry
            b["passive"] += entry
            return dmg, MELAN_TIME["U"], True, b
        else:
            coeff = MELAN_ULT_NORMAL_COEFF
            ult = unit * coeff * skill_bonus_mult(stats, "ult")

            dmg = ult + prelude
            b["ult"] += ult + prelude
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

        promo_on = (stats.get("_melan_promo", 0.0) > 0.0)

        for tier in (0.25, 0.50, 0.75):
            if prev + eps < tier <= new + eps:
                coeff = PASSIVE_TIER_COEFF.get(tier, 0.0)

                # 승급 효과: 전부 곱연산
                tier_mult = 1.0
                if promo_on:
                    if tier == 0.25:
                        # 25%: 언데드 쿠키 +1개
                        tier_mult *= (1.0 + float(MELAN_PROMO_UNDEAD_EXTRA))
                    elif tier == 0.50:
                        # 50%: 멜랑노바 +2개
                        tier_mult *= (1.0 + float(MELAN_PROMO_NOVA_EXTRA))
                    elif tier == 0.75:
                        # 75%: 종말의 도래 피해 100% 증가 => 2배
                        if bool(MELAN_PROMO_APOCALYPSE_X2):
                            tier_mult *= 2.0

                # 언데드/멜랑노바/종말 = 패시브 피해 배율 적용
                pdmg += unit * coeff * tier_mult * skill_bonus_mult(stats, "passive")

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

            #  프리마 기본공격 = 패시브 배율
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
# (C) 이슬맛 쿠키 (DPS 사이클 / 보호막 최적화)
# =====================================================

from typing import Dict, List, Tuple, Optional, Callable, Union

ISLE_PROMO_ENABLED = True

# -----------------------------
# 고정 세팅
# -----------------------------
ISLE_FIXED_POT = {
    "elem_atk": 2,
    "buff_amp": 4,
    "atk_pct": 2,
    "crit_rate": 0,
    "crit_dmg": 0,
    "armor_pen": 0,
    "debuff_amp": 0,
}
ISLE_FIXED_UNIQUE   = "정화된 에메랄딘의 기억"
ISLE_FIXED_ARTIFACT = "비에 젖은 과거"

BASE_STATS_ISLE = {
    "이슬맛 쿠키": {
        "atk": 577.0,
        "elem_atk": 0.0,
        "atk_pct": 0.0,
        "crit_rate": 0.15,
        "crit_dmg": 1.50,
        "armor_pen": 0.0,
        "final_dmg": 0.0,
        "buff_amp": 0.15,   # 기본 버프증폭 15%
    }
}

# ---- 로테이션
ISLE_CAST_TIME = {"B": 2.50, "S": 0.25, "C": 0.25, "U": 1.50}

# ---- 계수(%) -> 배율
ISLE_BASIC_COEFF = 1.42 + 1.42 + 3.834              # = 6.674
ISLE_SPECIAL_COEFF = (3.834 * 3) + 5.964            # = 17.466

ISLE_ULT_HITS_PER_SEC = 1.0
ISLE_ULT_DURATION = 15.0
ISLE_ULT_HIT_COEFF = 3.124

ISLE_CHARGE_HITS = 1
ISLE_CHARGE_HIT_COEFF = 1.491

ISLE_SHADOW_HITS = 1
ISLE_SHADOW_HIT_COEFF = 4.26

# ---- 버프/패시브 파라미터
ISLE_STACK_MAX = 6
ISLE_STACK_FROM_S = 1
ISLE_STACK_FROM_U = 2

ISLE_STRIKE_STACK_CD_BASE = 8.0
ISLE_STRIKE_STACK_CD_PROMO_REDUCE = 4.0  # => 4초

ISLE_SHADOW_CD_BASE = 12.0
ISLE_SHADOW_CD_PROMO_REDUCE = 3.0        # => 9초

ISLE_END_BUFF_ATK_PCT = 0.224
ISLE_END_BUFF_DUR_BASE = 8.0
ISLE_END_BUFF_DUR_PROMO_ADD = 2.0

ISLE_CLEAR_DEAL_CRITDMG = 0.56
ISLE_CLEAR_DEAL_DUR = 30.0

ISLE_PROMO_BASIC_DMG_CLEAR = 0.05
ISLE_PROMO_BASIC_DMG_END   = 0.05

ISLE_PROMO_ATK_MULT = 1.08
ISLE_PROMO_FINAL_DMG_ADD = 0.04

ISLE_PROMO_CHARGE_SHADOW_MULT = 1.20

# 보호막 기본 배율(공격력의 100.8%)
ISLE_SHIELD_BASE_MULT = 1.008


def isle_generate_shard_candidates(target: str = "dps", step: int = 7) -> List[Dict[str, int]]:
    """
    - dps: 기존 step 기반 6축 탐색
    - shield: 보호막 최적은 3축(elem_atk, atk_pct, shield_pct) "1칸 단위" 전수조사 (정확도 우선)
    """
    candidates: List[Dict[str, int]] = []

    if target == "shield":
        # 보호막 최적화: elem_atk + atk_pct + shield_pct = NORMAL_SLOTS (1칸 단위)
        for ea in range(NORMAL_SLOTS + 1):
            for ap in range(NORMAL_SLOTS - ea + 1):
                sp = NORMAL_SLOTS - ea - ap
                candidates.append({
                    "elem_atk": ea,
                    "atk_pct": ap,
                    "shield_pct": sp,

                    # 스키마 맞추기(다 0)
                    "crit_rate": 0,
                    "crit_dmg": 0,
                    "all_elem_dmg": 0,
                    "special_dmg": 0,
                    "ult_dmg": 0,
                    "basic_dmg": 0,
                    "passive_dmg": 0,
                })
        return candidates

    # target == "dps"
    steps = list(range(0, NORMAL_SLOTS + 1, step))
    if steps[-1] != NORMAL_SLOTS:
        steps.append(NORMAL_SLOTS)

    for cr in steps:
        for cd in steps:
            for ae in steps:
                for ap in steps:
                    for sd in steps:
                        for ud in steps:
                            used = cr + cd + ae + ap + sd + ud
                            if used > NORMAL_SLOTS:
                                continue
                            ea = NORMAL_SLOTS - used
                            candidates.append({
                                "crit_rate": cr,
                                "crit_dmg": cd,
                                "all_elem_dmg": ae,
                                "atk_pct": ap,
                                "special_dmg": sd,
                                "ult_dmg": ud,
                                "elem_atk": ea,

                                "basic_dmg": 0,
                                "passive_dmg": 0,
                                "shield_pct": 0,   # DPS 최적화에서는 0 고정
                            })
    return candidates


def isle_calc_shield_from_stats(stats: Dict[str, float]) -> float:
    """
    최종공격력 = (base_atk + equip_atk_flat + base_elem_atk + elem_atk)
              * (1+base_atk_pct+atk_pct)
              * (1+buff_atk_pct_raw)
              * (1+final_atk_mult)
    보호막 = 최종공격력 * (1+shield_pct) * 1.008
    """
    OA = float(stats.get("base_atk", 0.0)) + float(stats.get("equip_atk_flat", 0.0))
    EA = float(stats.get("base_elem_atk", 0.0)) + float(stats.get("elem_atk", 0.0))

    equip_atk_pct = 1.0 + float(stats.get("base_atk_pct", 0.0)) + float(stats.get("atk_pct", 0.0))
    buff_atk_mult = 1.0 + float(stats.get("buff_atk_pct_raw", 0.0))
    final_atk_mult = 1.0 + float(stats.get("final_atk_mult", 0.0))

    final_atk = (OA + EA) * equip_atk_pct * buff_atk_mult * final_atk_mult

    shield_pct = float(stats.get("shield_pct", 0.0))
    shield = final_atk * (1.0 + shield_pct) * ISLE_SHIELD_BASE_MULT
    return shield


def _isle_apply_passive_start_effect(base_stats: Dict[str, float]) -> Dict[str, float]:
    """
    전투 시작: 버프증폭의 50%만큼 치확 증가, 증가값 최대 60% 제한.
    """
    st = dict(base_stats)
    BA = float(st.get("buff_amp", 0.0))
    add_cr = min(0.60, 0.50 * BA)
    st["buff_crit_rate_raw"] += add_cr
    return st


def isle_cycle_damage(stats: Dict[str, float], party: List[str], artifact_name: str) -> Dict[str, float]:
    horizon = 30.0

    promo_on = bool(ISLE_PROMO_ENABLED)
    base_for_sim = dict(stats)

    if promo_on:
        base_for_sim["base_atk"] *= ISLE_PROMO_ATK_MULT
        base_for_sim["final_dmg"] += ISLE_PROMO_FINAL_DMG_ADD

    base_for_sim = _isle_apply_passive_start_effect(base_for_sim)

    s_cd = 10.0
    u_cd = 30.0

    strike_cd = ISLE_STRIKE_STACK_CD_BASE - (ISLE_STRIKE_STACK_CD_PROMO_REDUCE if promo_on else 0.0)
    strike_cd = max(0.0, strike_cd)

    shadow_cd = ISLE_SHADOW_CD_BASE - (ISLE_SHADOW_CD_PROMO_REDUCE if promo_on else 0.0)
    shadow_cd = max(0.0, shadow_cd)

    end_dur = ISLE_END_BUFF_DUR_BASE + (ISLE_END_BUFF_DUR_PROMO_ADD if promo_on else 0.0)

    t = 0.0
    next_s = 0.0
    next_u = 0.0
    next_strike_stack = 0.0
    next_shadow_ready = 0.0

    stacks = 3 if promo_on else 0

    end_buff_until = -1.0
    clear_deal_until = -1.0
    abyss_until = -1.0

    abyss_amt = 0.0
    abyss_dur = 0.0
    if artifact_name == "비에 젖은 과거":
        meta = ARTIFACTS[artifact_name].get("abyss", {}) or {}
        abyss_amt = float(meta.get("all_elem_dmg", 0.0))
        abyss_dur = float(meta.get("duration", 0.0))

    total_direct = 0.0
    total_time = 0.0

    breakdown = {
        "basic": 0.0,
        "special": 0.0,
        "ult": 0.0,
        "proc": 0.0,
        "strike": 0.0,
        "unique": 0.0,
    }

    def cur_stats_at(time_now: float) -> Dict[str, float]:
        st = dict(base_for_sim)

        if time_now < clear_deal_until:
            BA = float(st.get("buff_amp", 0.0))
            buff_scale = 1.0 + BA
            st["buff_crit_dmg_raw"] += ISLE_CLEAR_DEAL_CRITDMG * buff_scale
            if promo_on:
                st["basic_dmg"] += ISLE_PROMO_BASIC_DMG_CLEAR

        if time_now < end_buff_until:
            BA = float(st.get("buff_amp", 0.0))
            buff_scale = 1.0 + BA
            st["buff_atk_pct_raw"] += ISLE_END_BUFF_ATK_PCT * buff_scale
            if promo_on:
                st["basic_dmg"] += ISLE_PROMO_BASIC_DMG_END

        if abyss_amt > 0 and time_now < abyss_until:
            BA = float(st.get("buff_amp", 0.0))
            buff_scale = 1.0 + BA
            st["buff_all_elem_dmg_raw"] += abyss_amt * buff_scale

        return st

    def apply_sonagi_trigger(time_now: float):
        nonlocal abyss_until
        if abyss_dur > 0:
            abyss_until = max(abyss_until, time_now + abyss_dur)

    while t < horizon - 1e-9:
        # 속성강타 스택 획득(파티 표식 가정)
        has_marker = ("윈드파라거스 쿠키" in party)
        if has_marker and strike_cd > 0 and t >= next_strike_stack - 1e-9:
            stacks = min(ISLE_STACK_MAX, stacks + 1)
            next_strike_stack = t + strike_cd

        # U > S > C > B
        if t >= next_u - 1e-9:
            st = cur_stats_at(t)
            unit = base_damage_only(st)

            hits = int(ISLE_ULT_DURATION * ISLE_ULT_HITS_PER_SEC + 1e-9)
            coeff = ISLE_ULT_HIT_COEFF * hits
            dmg = unit * coeff * skill_bonus_mult(st, "ult")

            total_direct += dmg
            breakdown["ult"] += dmg
            apply_sonagi_trigger(t)

            clear_deal_until = max(clear_deal_until, t + ISLE_CLEAR_DEAL_DUR)
            stacks = min(ISLE_STACK_MAX, stacks + ISLE_STACK_FROM_U)

            dt = ISLE_CAST_TIME["U"]
            t += dt
            total_time += dt
            next_u = t - dt + u_cd
            continue

        if t >= next_s - 1e-9:
            st = cur_stats_at(t)
            unit = base_damage_only(st)

            dmg = unit * ISLE_SPECIAL_COEFF * skill_bonus_mult(st, "special")
            total_direct += dmg
            breakdown["special"] += dmg
            apply_sonagi_trigger(t)

            stacks = min(ISLE_STACK_MAX, stacks + ISLE_STACK_FROM_S)

            dt = ISLE_CAST_TIME["S"]
            t += dt
            total_time += dt
            next_s = t - dt + s_cd
            continue

        if stacks >= 3 and t >= next_shadow_ready - 1e-9:
            st = cur_stats_at(t)
            unit = base_damage_only(st)

            ch_coeff = ISLE_CHARGE_HIT_COEFF * int(ISLE_CHARGE_HITS)
            ch_dmg = unit * ch_coeff * skill_bonus_mult(st, "special")

            sh_coeff = ISLE_SHADOW_HIT_COEFF * int(ISLE_SHADOW_HITS)
            sh_dmg = unit * sh_coeff * skill_bonus_mult(st, "special")

            if promo_on:
                ch_dmg *= ISLE_PROMO_CHARGE_SHADOW_MULT
                sh_dmg *= ISLE_PROMO_CHARGE_SHADOW_MULT

            total_direct += (ch_dmg + sh_dmg)
            breakdown["special"] += ch_dmg
            breakdown["proc"] += sh_dmg
            apply_sonagi_trigger(t)

            stacks -= 3
            end_buff_until = max(end_buff_until, t + end_dur)
            next_shadow_ready = t + shadow_cd

            dt = ISLE_CAST_TIME["C"]
            t += dt
            total_time += dt
            continue

        # B
        st = cur_stats_at(t)
        unit = base_damage_only(st)

        dmg = unit * ISLE_BASIC_COEFF * skill_bonus_mult(st, "basic")
        total_direct += dmg
        breakdown["basic"] += dmg

        dt = ISLE_CAST_TIME["B"]
        t += dt
        total_time += dt

    strike = strike_total_from_direct(total_direct, "이슬맛 쿠키", base_for_sim, party)
    breakdown["strike"] = strike

    unit0 = base_damage_only(cur_stats_at(0.0))
    unique_total = unit0 * float(base_for_sim.get("unique_extra_coeff", 0.0)) * total_time
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
        "breakdown_proc": breakdown["proc"],
        "breakdown_strike": breakdown["strike"],
        "breakdown_unique": breakdown["unique"],
    }


def optimize_isle_cycle(
    seaz_name: str,
    party: List[str],
    step: int = 7,  # (호환용) DPS탐색 step이었는데, 여기서는 "보호막 최적"이 목적이라 사실상 안 씀
    progress_cb: Optional[Callable[[float], None]] = None,
    equip_override: Optional[Union[str, List[str]]] = None,
) -> Optional[dict]:
    """
    항상 '보호막 최적' 샤드 배치를 찾는다.
    단, RESULT에 필요한 DPS/사이클도 같은 세팅으로 같이 계산해서 반환한다.
    - best 선택: max_shield 최우선, 동률이면 dps로 타이브레이크
    """
    cookie = "이슬맛 쿠키"
    base = BASE_STATS_ISLE[cookie].copy()

    # equip 후보만 구성
    equips = list(EQUIP_SETS.keys())
    if equip_override:
        if isinstance(equip_override, str) and equip_override.strip():
            equips = [equip_override.strip()]
        elif isinstance(equip_override, (list, tuple)):
            equips = _resolve_equip_list_override(equip_override, equips)

    artifact_name = ISLE_FIXED_ARTIFACT
    unique_name   = ISLE_FIXED_UNIQUE
    pot           = ISLE_FIXED_POT

    # 보호막 후보(정확 전수조사)
    shard_candidates = isle_generate_shard_candidates(target="shield", step=step)

    total = max(1, len(equips) * len(shard_candidates))
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

    zero_shards = {k: 0 for k in SHARD_INC.keys()}

    for equip in equips:
        stats_template = build_stats_for_combo(
            cookie_name_kr=cookie,
            base=base,
            shards=zero_shards,
            potentials=pot,
            equip_name=equip,
            seaz_name=seaz_name,
            unique_name=unique_name,
            party=party,
            artifact_name=artifact_name,
        )
        if not is_valid_by_caps(stats_template):
            continue

        for shards in shard_candidates:
            done += 1
            if (done % tick) == 0:
                _emit(done / total)

            stats = dict(stats_template)
            for k, slots in shards.items():
                inc = SHARD_INC.get(k, 0.0)
                if inc != 0.0 and slots:
                    stats[k] = stats.get(k, 0.0) + inc * slots

            if not is_valid_by_caps(stats):
                continue

            # 보호막 + DPS(RESULT용) 둘 다 계산
            shield = isle_calc_shield_from_stats(stats)
            cycle  = isle_cycle_damage(stats, party, artifact_name)

            cur = {
                "cookie": cookie,

                # RESULT용(항상 존재)
                "dps": cycle["dps"],
                "cycle_total_damage": cycle["total_damage"],
                "cycle_total_time": cycle["total_time"],
                "cycle_breakdown": cycle,

                # 보호막 최적화용(항상 존재)
                "max_shield": shield,

                # UI 고정키
                "equip_fixed": equip,
                "seaz_fixed": seaz_name,
                "unique_fixed": unique_name,
                "artifact_fixed": artifact_name,
                "potentials_fixed": pot,

                # 호환 키
                "equip": equip,
                "seaz": seaz_name,
                "unique": unique_name,
                "artifact": artifact_name,
                "potentials": pot,

                "shards": {
                    # UI에서는 이 3개만 보여주면 깔끔
                    "elem_atk": int(shards.get("elem_atk", 0)),
                    "atk_pct": int(shards.get("atk_pct", 0)),
                    "shield_pct": int(shards.get("shield_pct", 0)),
                },
                "party": party,
                "stats": stats,
            }

            # best 갱신: shield 우선, 동률이면 dps
            if best is None:
                best = cur
            else:
                if cur["max_shield"] > best["max_shield"] + 1e-9:
                    best = cur
                elif abs(cur["max_shield"] - best["max_shield"]) <= 1e-9 and cur["dps"] > best["dps"]:
                    best = cur

    _emit(1.0)
    return best
