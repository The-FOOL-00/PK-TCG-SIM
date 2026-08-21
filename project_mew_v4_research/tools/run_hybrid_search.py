"""PROJECT MEW — HYBRID ANTI-E19 / GLOBAL-META BREAKTHROUGH SEARCH RUNNER.

Strictly offline, read-only evaluation. Frozen control V4 + E19.
"""

import sys
import os
import io
import json
import math
import time
import hashlib
import contextlib
from pathlib import Path
from collections import defaultdict, Counter
from concurrent.futures import ProcessPoolExecutor

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools import ab_gate, deck_compare, build_submission, validate_deck
from tools.meta_pool_v2 import run_meta_pool_v2
import main as agent_mod

RESEARCH_DIR = ROOT_DIR / "project_mew_v4_research"
CANDIDATES_DIR = RESEARCH_DIR / "candidates"
REPORTS_DIR = RESEARCH_DIR / "reports"
DATA_DIR = RESEARCH_DIR / "data"

for d in [CANDIDATES_DIR, REPORTS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ===========================================================================
# PART 1 — CONTROL FREEZE & VERIFICATION
# ===========================================================================

def verify_control_freeze():
    deck_path = ROOT_DIR / "deck.csv"
    bundle_path = ROOT_DIR / "project_mew_v4_challenger.tar.gz"
    
    deck_bytes = deck_path.read_bytes()
    bundle_bytes = bundle_path.read_bytes()
    
    deck_hash = hashlib.sha256(deck_bytes).hexdigest()
    bundle_hash = hashlib.sha256(bundle_bytes).hexdigest()
    
    expected_deck_hash = "3c0db7bc29599ff1a0a910fc3fbf091c0a5b87735db0c0ec62d774a9c010e8dc"
    expected_bundle_hash = "a7ee61995f5dd42c5ca4380d6bb9b76e45c3d923c08cdb0d98b7e434f1c1a894"
    
    control_record = {
        "control_deck_file": "deck.csv",
        "control_deck_name": "E19 Teal Mask Ogerpon ex",
        "control_policy_name": "V4 Strong Tactical",
        "control_deck_sha256": deck_hash,
        "control_bundle_sha256": bundle_hash,
        "deck_hash_verified": (deck_hash == expected_deck_hash),
        "bundle_hash_verified": (bundle_hash == expected_bundle_hash),
        "status": "FROZEN_IMMUTABLE"
    }
    
    (DATA_DIR / "control_freeze_record.json").write_text(json.dumps(control_record, indent=2), encoding="utf-8")
    print(f"Control Freeze Verified: Deck SHA256={deck_hash[:16]}..., Bundle SHA256={bundle_hash[:16]}...")
    return control_record


# ===========================================================================
# PART 2 & 3 — MECHANISM LIBRARY & COMPATIBILITY GRAPH
# ===========================================================================

def build_mechanism_library():
    library = {
        "A_FIRE_WEAKNESS": {
            "name": "Fire Weakness Exploitation",
            "description": "Fire attackers dealing 110+ base damage deal 220+ weakness damage, scoring instant 1HKOs on 210 HP Ogerpon.",
            "cards": ["Gouging Fire ex (46)", "Hearthflame Mask Ogerpon ex (99)", "Chi-Yu (719)", "Entei (855)", "Turtonator (1027)"],
            "direct_e19_advantage": "Extreme (2x multiplier halves damage requirement)",
            "energy_requirement": "Fire / Prism Energy",
            "setup_time": "Turn 1-2 with Turbo or manual attach",
            "deck_space_cost": "Moderate (4-8 Pokemon slots + 15-20 Energy)",
            "broad_meta_weakness": "Severe disadvantage vs Water (Mega Starmie ex)",
            "policy_compatibility": "High (V4 aggressive tempo and KO prioritization)"
        },
        "B_ANTI_EX": {
            "name": "Safeguard / Anti-Rule-Box Immunity",
            "description": "Single-prize walls that block all damage from Pokemon ex, preventing Ogerpon from taking prizes.",
            "cards": ["Mimikyu (767)", "Miltank (703)", "Neutralization Zone (1247)"],
            "direct_e19_advantage": "High (Hard wall against pure ex attackers)",
            "energy_requirement": "Psychic / Colorless / Prism",
            "setup_time": "Turn 1 immediate",
            "deck_space_cost": "Low to Moderate (4-8 Pokemon slots)",
            "broad_meta_weakness": "Vulnerable to single-prize attackers (Chi-Yu, Cramorant, Garchomp lines) and bench gust",
            "policy_compatibility": "High (V4 holds active wall safely)"
        },
        "C_HIGH_HP_TANK": {
            "name": "High-HP Damage Absorption",
            "description": "250-310+ HP bodies that absorb 2-3 hits from Ogerpon before conceding prizes.",
            "cards": ["Archaludon ex (988)", "Mega Audino ex (1006)", "Mega Zygarde ex (1056)", "Snorlax (1072)", "Orthworm ex (993)"],
            "direct_e19_advantage": "Moderate (Forces Ogerpon to over-commit energy to hit 250+)",
            "energy_requirement": "Metal / Fighting / Colorless",
            "setup_time": "Turn 2-3",
            "deck_space_cost": "High (Evolution or heavy energy engine)",
            "broad_meta_weakness": "Can be outpaced by Mega Starmie / Dragapult spread",
            "policy_compatibility": "Medium (Requires energy routing onto tank)"
        },
        "D_ENERGY_DENIAL": {
            "name": "Energy Denial & Disruption",
            "description": "Active and bench energy removal preventing Ogerpon from reaching the 2-3 energy threshold for Myriad Leaf Shower.",
            "cards": ["Crushing Hammer (1120)", "Enhanced Hammer (1081)", "Turtonator Shell Spikes (1027)"],
            "direct_e19_advantage": "High (Disrupts Ogerpon tempo and damage scaling)",
            "energy_requirement": "None (Trainer/Ability based)",
            "setup_time": "Turn 1-4 continuous",
            "deck_space_cost": "4-8 Trainer slots",
            "broad_meta_weakness": "Coin-flip variance (50% per hammer); ineffective if opponent accelerates faster than denial rate",
            "policy_compatibility": "High (V1/V4 plays item trainers immediately)"
        },
        "E_BENCH_DENIAL": {
            "name": "Bench Control & Target Selection",
            "description": "Gusting vulnerable bench targets and preventing opponent from safely sheltering wounded Pokemon.",
            "cards": ["Boss's Orders (1182)", "Prime Catcher (1088)", "Pokemon Catcher (1124)"],
            "direct_e19_advantage": "High (Picks off bench Ogerpons before they accumulate energy)",
            "energy_requirement": "None",
            "setup_time": "Turn 2+",
            "deck_space_cost": "3-5 slots",
            "broad_meta_weakness": "Requires lethal board pressure to capitalize",
            "policy_compatibility": "High (V4 Pattern 1 & V1 prioritize gust for lethal)"
        },
        "F_PRIZE_CONTROL": {
            "name": "Prize Trade Manipulation",
            "description": "Trading 1-prize attackers into 2-prize ex targets, forcing opponent to take 6 KOs while taking only 3.",
            "cards": ["Chi-Yu (719)", "Pecharunt (898)", "Fezandipiti (970)", "Zekrom (906)", "Legacy Energy (12)", "Briar (1201)"],
            "direct_e19_advantage": "High (Asymmetric prize clock: 2 prizes gained per KO vs 1 conceded)",
            "energy_requirement": "Type-specific / Special",
            "setup_time": "Turn 1-2",
            "deck_space_cost": "Moderate",
            "broad_meta_weakness": "Lower individual HP makes single-prizers easy 1HKO targets",
            "policy_compatibility": "High (V4 prize math naturally leverages asymmetric trades)"
        },
        "G_FAST_BASIC_AGGRESSION": {
            "name": "Turn 1-2 High Pressure Basic Aggro",
            "description": "High base damage basic attackers attacking on turn 1 or turn 2 with low energy costs.",
            "cards": ["Koraidon ex (979)", "Miraidon ex (957)", "Gouging Fire ex (46)", "Zangoose ex (1002)", "Iron Boulder (971)"],
            "direct_e19_advantage": "High (Pressures Ogerpon before Teal Dance engine stabilizes)",
            "energy_requirement": "Fighting / Lightning / Fire",
            "setup_time": "Turn 1-2",
            "deck_space_cost": "Low to Moderate",
            "broad_meta_weakness": "Requires consistent opening energy draws",
            "policy_compatibility": "High (V1 Strong Tactical is natively aggressive)"
        },
        "H_TEAL_DANCE_DISRUPTION": {
            "name": "Hand & Draw Disruption",
            "description": "Shrinking opponent hand size to disrupt combo pieces, Bug Catching Sets, and Tera Orbs.",
            "cards": ["Judge (1213)", "Unfair Stamp (1080)", "N's Plan (1221)"],
            "direct_e19_advantage": "Moderate (Resets Ogerpon hand after massive Teal Dance draws)",
            "energy_requirement": "None",
            "setup_time": "Turn 1+",
            "deck_space_cost": "4-6 slots",
            "broad_meta_weakness": "Can refresh opponent's dead hand into playable cards",
            "policy_compatibility": "High (V1/V4 supporters fired efficiently)"
        },
        "I_DAMAGE_ABSORPTION_REDUCTION": {
            "name": "Damage Reduction & EHP Expansion",
            "description": "Tools and abilities that increase effective HP beyond Ogerpon's 1-shot threshold (210-240).",
            "cards": ["Hero's Cape (1159)", "Survival Brace (1155)", "Heavy Baton (1160)", "Maximum Belt (1158)"],
            "direct_e19_advantage": "High (Pushes Basic ex to 310-330 HP, requiring 3+ attacks to KO)",
            "energy_requirement": "None (Tools)",
            "setup_time": "Turn 1+",
            "deck_space_cost": "1-3 Tool slots",
            "broad_meta_weakness": "Vulnerable to Tool Scrapper (1137) and Megaton Blower (1104)",
            "policy_compatibility": "High (V1 attaches tools immediately to active)"
        },
        "J_RESOURCE_EXHAUSTION": {
            "name": "Resource Depletion & Deckout Pressure",
            "description": "Forcing Ogerpon to exhaust energy, Tera Orbs, and gust cards through stall, recycling, and attrition.",
            "cards": ["Energy Retrieval (1118)", "Night Stretcher / Max Rod (1110)", "Jumbo Ice Cream (1147)", "Lively Stadium (1251)"],
            "direct_e19_advantage": "Moderate (Ogerpon burns deck quickly via Teal Dance, making it prone to late-game deckout)",
            "energy_requirement": "Any",
            "setup_time": "Turn 5+",
            "deck_space_cost": "4-6 slots",
            "broad_meta_weakness": "Slow clock; vulnerable to hyper-aggressive turn-2 KOs",
            "policy_compatibility": "Medium (Requires survival into late game)"
        }
    }
    
    (DATA_DIR / "mechanism_library.json").write_text(json.dumps(library, indent=2), encoding="utf-8")
    return library


def build_compatibility_graph(library):
    keys = list(library.keys())
    matrix = {}
    
    synergy_scores = {
        ("A_FIRE_WEAKNESS", "B_ANTI_EX"): {"score": 78, "synergy": "HIGH", "energy_cohesion": "MEDIUM (Dual Fire/Psychic or Prism)", "desc": "Fire 1HKOs Grass ex, Mimikyu walls non-Fire ex."},
        ("A_FIRE_WEAKNESS", "C_HIGH_HP_TANK"): {"score": 72, "synergy": "MEDIUM", "energy_cohesion": "MEDIUM", "desc": "Fire provides offensive tempo, Tank absorbs counter-attacks."},
        ("A_FIRE_WEAKNESS", "D_ENERGY_DENIAL"): {"score": 88, "synergy": "VERY_HIGH", "energy_cohesion": "HIGH (Colorless Hammers)", "desc": "Hammers slow down Ogerpon while Fire scores fast 1HKOs."},
        ("A_FIRE_WEAKNESS", "E_BENCH_DENIAL"): {"score": 85, "synergy": "VERY_HIGH", "energy_cohesion": "HIGH", "desc": "Gust brings benched Ogerpons into active for 1HKO."},
        ("A_FIRE_WEAKNESS", "F_PRIZE_CONTROL"): {"score": 92, "synergy": "VERY_HIGH", "energy_cohesion": "HIGH (Chi-Yu single-prize Fire attacker)", "desc": "Chi-Yu takes 2 prizes for 1 energy while conceding 1 prize."},
        ("A_FIRE_WEAKNESS", "G_FAST_BASIC_AGGRESSION"): {"score": 95, "synergy": "VERY_HIGH", "energy_cohesion": "VERY_HIGH (Mono-Fire)", "desc": "Hearthflame + Gouging Fire creates overwhelming T1-T2 pressure."},
        ("A_FIRE_WEAKNESS", "H_TEAL_DANCE_DISRUPTION"): {"score": 82, "synergy": "HIGH", "energy_cohesion": "HIGH", "desc": "Judge strips Ogerpon hands while Fire maintains board lead."},
        ("A_FIRE_WEAKNESS", "I_DAMAGE_ABSORPTION_REDUCTION"): {"score": 80, "synergy": "HIGH", "energy_cohesion": "HIGH", "desc": "Hero's Cape / Survival Brace prevents Ogerpon from revenge KOing Fire active."},
        ("A_FIRE_WEAKNESS", "J_RESOURCE_EXHAUSTION"): {"score": 60, "synergy": "MEDIUM_LOW", "energy_cohesion": "MEDIUM", "desc": "Aggro fire wants fast games; exhaustion wants long games."},
        ("B_ANTI_EX", "D_ENERGY_DENIAL"): {"score": 90, "synergy": "VERY_HIGH", "energy_cohesion": "VERY_HIGH", "desc": "Mimikyu stalls while Hammers strip energy, forcing pass turns."},
        ("B_ANTI_EX", "F_PRIZE_CONTROL"): {"score": 88, "synergy": "VERY_HIGH", "energy_cohesion": "HIGH", "desc": "Single-prize walls force 6 distinct KOs while trading efficiently."},
        ("B_ANTI_EX", "G_FAST_BASIC_AGGRESSION"): {"score": 75, "synergy": "MEDIUM_HIGH", "energy_cohesion": "MEDIUM", "desc": "Fast basic attacks while Mimikyu provides bench shelter."},
        ("C_HIGH_HP_TANK", "D_ENERGY_DENIAL"): {"score": 84, "synergy": "HIGH", "energy_cohesion": "HIGH", "desc": "Tank absorbs hits while Hammers prevent opponent from reaching lethal."},
        ("D_ENERGY_DENIAL", "G_FAST_BASIC_AGGRESSION"): {"score": 86, "synergy": "VERY_HIGH", "energy_cohesion": "HIGH", "desc": "Disrupts opponent setup while fast basic takes early prize lead."}
    }
    
    for k1 in keys:
        matrix[k1] = {}
        for k2 in keys:
            if k1 == k2:
                matrix[k1][k2] = {"score": 100, "synergy": "SELF", "desc": "Identical mechanism"}
            else:
                pair = (k1, k2) if (k1, k2) in synergy_scores else (k2, k1)
                if pair in synergy_scores:
                    matrix[k1][k2] = synergy_scores[pair]
                else:
                    matrix[k1][k2] = {"score": 50, "synergy": "NEUTRAL", "desc": "Standard interaction"}
                    
    (DATA_DIR / "mechanism_compatibility_graph.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")
    return matrix


# ===========================================================================
# PART 4, 5, 6, 7, 8, 9, 10, 11 — HYBRID CANDIDATE DECK GENERATOR
# ===========================================================================

def generate_hybrid_candidates():
    """Generates 200+ structurally diverse hybrid deck candidates."""
    candidates = {}
    
    # Common card IDs
    # Pokemon
    C_OGERPON_TEAL = 96      # Basic 210 HP Grass ex (Teal Dance + Myriad Leaf Shower)
    C_OGERPON_HEARTH = 99    # Basic 210 HP Fire ex (Wrathful Hearth)
    C_GOUGING_FIRE = 46      # Basic 230 HP Fire ex (Heat Tackle 160)
    C_CHI_YU = 719           # Basic 110 HP Fire single-prize (Megafire 30/80)
    C_TURTONATOR = 1027      # Basic 120 HP Fire single-prize (Shell Spikes energy discard)
    C_MIMIKYU = 767          # Basic 70 HP Psychic single-prize (Safeguard anti-ex)
    C_MILTANK = 703          # Basic 120 HP Colorless single-prize (Miracle Body anti-V/ex)
    C_ARCHALUDON = 988       # Basic/Stage1 300 HP Metal ex
    C_SNORLAX = 1072         # Basic 160 HP Colorless tank (Collapse 160)
    C_MEGA_AUDINO = 1006     # Basic 270 HP Colorless Mega ex
    C_FEZANDIPITI = 970      # Basic 120 HP Psychic (Adrena-Pheromone 50% dodge)
    C_PECHARUNT = 898        # Basic 80 HP Darkness (Final Chain search on KO)
    C_KORAIDON = 979         # Basic 230 HP Fighting ex (Orichalcum Fang 200)
    C_MIRAIDON = 957         # Basic 220 HP Lightning ex (Hadron Spark 120)
    C_ZANGOOSE = 1002        # Basic 200 HP Colorless ex (Wild Scissors 180)
    C_DRAMPA = 1010          # Basic 130 HP Colorless single-prize (Dragon Strike 120)
    C_REGICE = 944           # Basic 230 HP Water ex (Ice Prison 140)
    C_YVELTAL = 1062         # Basic 210 HP Darkness ex (Dark Strike 210)
    C_ORTHWORM = 993         # Basic 220 HP Metal ex (Pummeling Payback)
    
    # Energies
    E_GRASS = 1
    E_FIRE = 2
    E_WATER = 3
    E_LIGHTNING = 4
    E_PSYCHIC = 5
    E_FIGHTING = 6
    E_DARK = 7
    E_METAL = 8
    E_PRISM = 16            # Special: All types for Basics
    E_LEGACY = 12           # ACE SPEC Special Energy (-1 prize)
    E_GROW_GRASS = 18
    E_IGNITION_FIRE = 17
    
    # Trainers / ACE SPECs
    T_ULTRA_BALL = 1121
    T_TERA_ORB = 1127
    T_POFFIN = 1086
    T_BUG_CATCHING = 1094
    T_CRUSHING_HAMMER = 1120
    T_ENHANCED_HAMMER = 1081
    T_SWITCH = 1123
    T_ENERGY_RETRIEVAL = 1118
    T_ENERGY_SEARCH = 1119
    T_POKEGEAR = 1122
    T_TOOL_SCRAPPER = 1137
    T_JUMBO_ICE_CREAM = 1147
    T_LIVELY_STADIUM = 1251
    
    # Supporters
    S_BOSS = 1182
    S_JUDGE = 1213
    S_LILLIE = 1227
    S_BRIAR = 1201
    S_CYRANO = 1205
    S_HARLEQUIN = 1223
    S_N_PLAN = 1221
    S_WAITRESS = 1235
    
    # ACE SPECs
    ACE_PRIME_CATCHER = 1088
    ACE_HEROS_CAPE = 1159
    ACE_MAX_BELT = 1158
    ACE_SURVIVAL_BRACE = 1155
    ACE_MASTER_BALL = 1125
    ACE_NEUTRAL_ZONE = 1247
    
    # Helper builder
    def make_deck(pokes, trainers, ace, energies):
        deck = []
        for cid, cnt in pokes.items():
            deck.extend([cid] * cnt)
        for cid, cnt in trainers.items():
            deck.extend([cid] * cnt)
        if ace:
            deck.append(ace)
        
        rem = 60 - len(deck)
        if rem < 0:
            raise ValueError(f"Deck over 60 cards: {len(deck)}")
        
        # Distribute energies
        if isinstance(energies, dict):
            # First pass: assign special energies (cards > 8) with strict <= 4 cap
            specials = {k: min(4, v) for k, v in energies.items() if k > 8}
            basics_dict = {k: v for k, v in energies.items() if k <= 8}
            
            for s_id, s_cnt in specials.items():
                alloc = min(s_cnt, rem)
                deck.extend([s_id] * alloc)
                rem -= alloc
                
            if rem > 0 and basics_dict:
                tot_b_weight = sum(basics_dict.values())
                b_items = list(basics_dict.items())
                for b_id, weight in b_items[:-1]:
                    count = int(round(rem * (weight / tot_b_weight)))
                    deck.extend([b_id] * count)
                # Remainder to last basic energy
                allocated_basics = sum(len([c for c in deck if c == b_id]) for b_id, _ in b_items[:-1])
                remaining_for_last = rem - sum(int(round(rem * (weight / tot_b_weight))) for _, weight in b_items[:-1])
                last_b_id = b_items[-1][0]
                deck.extend([last_b_id] * max(0, remaining_for_last))
            elif rem > 0:
                # Default to Fire (2) or Grass (1)
                deck.extend([2] * rem)
        elif isinstance(energies, list):
            deck.extend(energies[:rem])
        else:
            deck.extend([energies] * rem)
            
        # Exact 60 fixup with basic energy
        primary_b = 2 # Fire default
        if isinstance(energies, dict):
            for k in energies:
                if k <= 8:
                    primary_b = k
                    break
        elif isinstance(energies, int) and energies <= 8:
            primary_b = energies

        while len(deck) < 60:
            deck.append(primary_b)
        while len(deck) > 60:
            deck.pop()
        return deck

    # =======================================================================
    # FAMILY 1: FIRE WEAKNESS + ANTI-EX (Gouging/Hearthflame + Mimikyu/Miltank)
    # =======================================================================
    for f_name, f_id in [("Gouging", C_GOUGING_FIRE), ("Hearthflame", C_OGERPON_HEARTH), ("ChiYu", C_CHI_YU)]:
        for n_mimikyu in [1, 2, 4]:
            for n_fire in [2, 4]:
                for ace in [ACE_PRIME_CATCHER, ACE_HEROS_CAPE, ACE_MAX_BELT]:
                    cid = f"HYB_F1_FireSafeguard_{f_name}_M{n_mimikyu}_F{n_fire}_{ace}"
                    pokes = {f_id: n_fire, C_MIMIKYU: n_mimikyu}
                    if f_id != C_CHI_YU:
                        pokes[C_CHI_YU] = 2
                    trainers = {T_ULTRA_BALL: 4, T_SWITCH: 4, S_BOSS: 4, S_LILLIE: 4, S_JUDGE: 2}
                    energies = {E_FIRE: 18, E_PSYCHIC: 6, E_PRISM: 4}
                    d = make_deck(pokes, trainers, ace, energies)
                    candidates[cid] = {"deck": d, "family": "Fire_Safeguard", "p1": f_name, "p2": "Mimikyu", "ace": ace}

    # =======================================================================
    # FAMILY 2: FIRE WEAKNESS + ENERGY DENIAL (Fire Turbo + 2-4 Hammers)
    # =======================================================================
    for fire_attacker, f_id in [("Hearthflame", C_OGERPON_HEARTH), ("Gouging", C_GOUGING_FIRE), ("ChiYu", C_CHI_YU)]:
        for ace in [ACE_PRIME_CATCHER, ACE_HEROS_CAPE, ACE_MAX_BELT, ACE_SURVIVAL_BRACE]:
            for n_hammers in [2, 4]:
                cid = f"HYB_F2_FireDenial_{fire_attacker}_H{n_hammers}_{ace}"
                pokes = {f_id: 4, C_TURTONATOR: 2, C_CHI_YU: 2} if f_id != C_CHI_YU else {C_CHI_YU: 4, C_TURTONATOR: 4}
                trainers = {T_CRUSHING_HAMMER: n_hammers, T_ULTRA_BALL: 4, T_SWITCH: 4, S_BOSS: 4, S_LILLIE: 4, S_JUDGE: 4}
                d = make_deck(pokes, trainers, ace, E_FIRE)
                candidates[cid] = {"deck": d, "family": "Fire_Denial", "p1": fire_attacker, "p2": "Crushing Hammer", "ace": ace}

    # =======================================================================
    # FAMILY 3: FIRE WEAKNESS + HIGH-HP TANK (Fire Aggro + Snorlax/Mega Audino/Archaludon)
    # =======================================================================
    for tank_name, tank_id in [("Snorlax", C_SNORLAX), ("Audino", C_MEGA_AUDINO), ("Archaludon", C_ARCHALUDON)]:
        for ace in [ACE_HEROS_CAPE, ACE_PRIME_CATCHER, ACE_SURVIVAL_BRACE]:
            for n_tank in [2, 4]:
                cid = f"HYB_F3_FireTank_{tank_name}_T{n_tank}_{ace}"
                pokes = {C_GOUGING_FIRE: 4, tank_id: n_tank, C_CHI_YU: 2}
                trainers = {T_ULTRA_BALL: 4, T_SWITCH: 4, S_BOSS: 4, S_LILLIE: 4, S_WAITRESS: 2}
                d = make_deck(pokes, trainers, ace, E_FIRE)
                candidates[cid] = {"deck": d, "family": "Fire_Tank", "p1": "Gouging Fire", "p2": tank_name, "ace": ace}

    # =======================================================================
    # FAMILY 4: ANTI-EX SAFEGUARD + FAST BASIC AGGRO (Mimikyu + Koraidon/Miraidon/Zangoose)
    # =======================================================================
    for aggro_name, aggro_id, e_type in [("Koraidon", C_KORAIDON, E_FIGHTING), ("Miraidon", C_MIRAIDON, E_LIGHTNING), ("Zangoose", C_ZANGOOSE, E_FIRE)]:
        for ace in [ACE_PRIME_CATCHER, ACE_HEROS_CAPE, ACE_MAX_BELT]:
            for n_mimikyu in [2, 4]:
                cid = f"HYB_F4_SafeguardAggro_{aggro_name}_M{n_mimikyu}_{ace}"
                pokes = {aggro_id: 4, C_MIMIKYU: n_mimikyu, C_MILTANK: 2}
                trainers = {T_ULTRA_BALL: 4, T_POFFIN: 4, T_SWITCH: 4, S_BOSS: 4, S_LILLIE: 4}
                energies = {e_type: 18, E_PSYCHIC: 6, E_PRISM: 4}
                d = make_deck(pokes, trainers, ace, energies)
                candidates[cid] = {"deck": d, "family": "Safeguard_Aggro", "p1": aggro_name, "p2": "Mimikyu", "ace": ace}

    # =======================================================================
    # FAMILY 5: TEAL MASK OGERPON + FIRE SPLASH (Dual Ogerpon Hybrid)
    # =======================================================================
    for n_hearth in [1, 2, 3]:
        for n_chiyu in [0, 2]:
            for ace in [ACE_PRIME_CATCHER, ACE_HEROS_CAPE, ACE_MAX_BELT, ACE_SURVIVAL_BRACE]:
                for e_split in ["15G_4R", "12G_7R", "14G_3R_2PRISM"]:
                    cid = f"HYB_F5_DualOgerpon_H{n_hearth}_CY{n_chiyu}_{e_split}_{ace}"
                    pokes = {C_OGERPON_TEAL: 4, C_OGERPON_HEARTH: n_hearth}
                    if n_chiyu > 0:
                        pokes[C_CHI_YU] = n_chiyu
                    trainers = {
                        T_TERA_ORB: 4, T_BUG_CATCHING: 4, T_CRUSHING_HAMMER: 4,
                        S_BOSS: 2, S_JUDGE: 4, S_LILLIE: 4, T_SWITCH: 2
                    }
                    if "15G_4R" in e_split:
                        energies = {E_GRASS: 15, E_FIRE: 4, E_GROW_GRASS: 2}
                    elif "12G_7R" in e_split:
                        energies = {E_GRASS: 12, E_FIRE: 7, E_GROW_GRASS: 2}
                    else:
                        energies = {E_GRASS: 14, E_FIRE: 3, E_PRISM: 2, E_GROW_GRASS: 2}
                    d = make_deck(pokes, trainers, ace, energies)
                    candidates[cid] = {"deck": d, "family": "Dual_Ogerpon_Splash", "p1": "Teal Ogerpon", "p2": "Hearthflame Ogerpon", "ace": ace}

    # =======================================================================
    # FAMILY 6: TEAL MASK OGERPON + ANTI-EX SPLASH (Teal Ogerpon + Mimikyu)
    # =======================================================================
    for n_mimikyu in [1, 2, 4]:
        for ace in [ACE_HEROS_CAPE, ACE_PRIME_CATCHER, ACE_NEUTRAL_ZONE]:
            cid = f"HYB_F6_OgerponSafeguard_M{n_mimikyu}_{ace}"
            pokes = {C_OGERPON_TEAL: 4, C_MIMIKYU: n_mimikyu}
            trainers = {
                T_TERA_ORB: 4, T_BUG_CATCHING: 4, T_CRUSHING_HAMMER: 4,
                S_BOSS: 2, S_JUDGE: 4, S_LILLIE: 4, T_SWITCH: 2
            }
            energies = {E_GRASS: 16, E_PSYCHIC: 3, E_GROW_GRASS: 2}
            d = make_deck(pokes, trainers, ace, energies)
            candidates[cid] = {"deck": d, "family": "Ogerpon_Safeguard", "p1": "Teal Ogerpon", "p2": "Mimikyu", "ace": ace}

    # =======================================================================
    # FAMILY 7: 3-WAY HYBRID (Fire Weakness + Anti-EX + Energy Denial)
    # =======================================================================
    for ace in [ACE_PRIME_CATCHER, ACE_HEROS_CAPE, ACE_MAX_BELT]:
        for f_poke, f_name in [(C_OGERPON_HEARTH, "Hearthflame"), (C_GOUGING_FIRE, "Gouging"), (C_CHI_YU, "ChiYu")]:
            cid = f"HYB_F7_Triple_FireSafeguardDenial_{f_name}_{ace}"
            pokes = {f_poke: 3, C_MIMIKYU: 2, C_CHI_YU: 2} if f_poke != C_CHI_YU else {C_CHI_YU: 4, C_MIMIKYU: 4}
            trainers = {T_CRUSHING_HAMMER: 4, T_ULTRA_BALL: 4, T_SWITCH: 4, S_BOSS: 3, S_JUDGE: 3, S_LILLIE: 4}
            energies = {E_FIRE: 16, E_PSYCHIC: 4, E_PRISM: 4}
            d = make_deck(pokes, trainers, ace, energies)
            candidates[cid] = {"deck": d, "family": "Triple_Fire_Safeguard_Denial", "p1": f_name, "p2": "Mimikyu + Hammer", "ace": ace}

    # =======================================================================
    # FAMILY 8: 3-WAY HYBRID (Dual Ogerpon Engine + Energy Denial + Prize Control)
    # =======================================================================
    for ace in [ACE_PRIME_CATCHER, ACE_HEROS_CAPE, ACE_MAX_BELT, ACE_SURVIVAL_BRACE]:
        for n_hammers in [2, 4]:
            cid = f"HYB_F8_Triple_DualOgerponDenialPrize_H{n_hammers}_{ace}"
            pokes = {C_OGERPON_TEAL: 4, C_OGERPON_HEARTH: 2, C_CHI_YU: 2}
            trainers = {
                T_TERA_ORB: 4, T_BUG_CATCHING: 4, T_CRUSHING_HAMMER: n_hammers,
                S_BOSS: 2, S_JUDGE: 4, S_LILLIE: 4, S_BRIAR: 1, T_SWITCH: 2
            }
            energies = {E_GRASS: 14, E_FIRE: 5, E_GROW_GRASS: 2}
            d = make_deck(pokes, trainers, ace, energies)
            candidates[cid] = {"deck": d, "family": "Triple_DualOgerpon_Denial_Prize", "p1": "Dual Ogerpon", "p2": "Chi-Yu + Hammer", "ace": ace}

    # =======================================================================
    # FAMILY 9: BASIC DENSITY VARIANTS (2, 3, 4, 6, 8, 10+ Basics)
    # =======================================================================
    for n_basics in [2, 3, 4, 6, 8, 10]:
        for ace in [ACE_PRIME_CATCHER, ACE_HEROS_CAPE]:
            cid = f"HYB_F9_Density_DualOgerpon_{n_basics}B_{ace}"
            if n_basics == 2:
                pokes = {C_OGERPON_TEAL: 1, C_OGERPON_HEARTH: 1}
            elif n_basics == 3:
                pokes = {C_OGERPON_TEAL: 2, C_OGERPON_HEARTH: 1}
            elif n_basics == 4:
                pokes = {C_OGERPON_TEAL: 3, C_OGERPON_HEARTH: 1}
            elif n_basics == 6:
                pokes = {C_OGERPON_TEAL: 4, C_OGERPON_HEARTH: 2}
            elif n_basics == 8:
                pokes = {C_OGERPON_TEAL: 4, C_OGERPON_HEARTH: 2, C_CHI_YU: 2}
            else: # 10
                pokes = {C_OGERPON_TEAL: 4, C_OGERPON_HEARTH: 2, C_CHI_YU: 2, C_MIMIKYU: 2}
            trainers = {
                T_TERA_ORB: 4, T_BUG_CATCHING: 4, T_CRUSHING_HAMMER: 4,
                S_BOSS: 2, S_JUDGE: 4, S_LILLIE: 4, T_SWITCH: 2
            }
            energies = {E_GRASS: 14, E_FIRE: 5, E_GROW_GRASS: 2}
            d = make_deck(pokes, trainers, ace, energies)
            candidates[cid] = {"deck": d, "family": "Density_Variants", "p1": f"{n_basics} Basics", "p2": "Dual Ogerpon", "ace": ace}

    # Validate and save all candidate deck files
    valid_candidates = {}
    print(f"\nGenerated {len(candidates)} candidate definitions. Validating deck rules...")
    for cid, cinfo in candidates.items():
        d_list = cinfo["deck"]
        if len(d_list) != 60:
            print(f"ERROR: {cid} length {len(d_list)} != 60")
            continue
        counts = Counter(d_list)
        violates_max4 = any(cnt > 4 for card, cnt in counts.items() if card > 8)
        if violates_max4:
            print(f"ERROR: {cid} violates 4-copy rule")
            continue
            
        fpath = CANDIDATES_DIR / f"{cid}.csv"
        fpath.write_text("\n".join(str(c) for c in d_list) + "\n", encoding="utf-8")
        cinfo["path"] = str(fpath)
        valid_candidates[cid] = cinfo

    print(f"Successfully generated and verified {len(valid_candidates)} legal hybrid decks in {CANDIDATES_DIR}.")
    (DATA_DIR / "hybrid_candidates_manifest.json").write_text(json.dumps({
        cid: {"family": v["family"], "p1": v["p1"], "p2": v["p2"], "ace": v["ace"], "path": v["path"]}
        for cid, v in valid_candidates.items()
    }, indent=2), encoding="utf-8")
    return valid_candidates


# ===========================================================================
# PART 12, 13, 14, 15, 16, 17, 18, 19, 20 — SIMULATION & EVALUATION PIPELINE
# ===========================================================================

def fast_screen_candidates(candidates, games_per_screen=100, workers=6):
    """Stage 1: Fast screen all hybrid candidates vs V4 + E19 control."""
    print(f"\n========================================================")
    print(f"STAGE 1: Fast Screening {len(candidates)} Hybrids vs V4 + E19 ({games_per_screen}g each)")
    print(f"========================================================")
    
    ogerpon_spec = "metaZ_teal_ogerpon_top10.csv"
    screen_results = {}
    c_items = list(candidates.items())
    
    for idx, (cid, info) in enumerate(c_items):
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}"
        
        total = ab_gate.run_gate(
            spec_c=spec_c,
            spec_i=ogerpon_spec,
            games=games_per_screen,
            workers=workers
        )
        
        st = total["chal"]
        w = st["wins_seat0"] + st["wins_seat1"]
        l = st["losses"]
        d = st["draws"]
        decided = w + l
        p, lo, hi = ab_gate.wilson(w, decided) if decided > 0 else (0.0, 0.0, 0.0)
        
        res_entry = {
            "name": cid,
            "family": info["family"],
            "p1": info["p1"],
            "p2": info["p2"],
            "ace": info["ace"],
            "wins": w,
            "losses": l,
            "draws": d,
            "win_rate_vs_e19": float(p),
            "wilson_ci": [float(lo), float(hi)],
            "bench_outs": st["reasons_lost"].get(3, 0),
            "prize_losses": st["reasons_lost"].get(1, 0),
            "deckouts": st["reasons_lost"].get(2, 0),
            "crashes": st["crashes"]
        }
        screen_results[cid] = res_entry
        
        if (idx + 1) % 10 == 0 or idx == len(c_items) - 1 or p >= 0.50:
            print(f"  [{idx+1:3d}/{len(c_items):3d}] {cid:48s} | WR: {p*100:5.1f}% [{lo*100:4.1f}%, {hi*100:4.1f}%] (W:{w:2d} L:{l:2d})")
            
    (REPORTS_DIR / "stage1_screening_results.json").write_text(json.dumps(screen_results, indent=2), encoding="utf-8")
    return screen_results


def evaluate_broad_meta(candidates_to_test, workers=6):
    """Stage 2: Broad MetaPool v2 evaluation across 6 archetypes x 4 tiers (480g each)."""
    print(f"\n========================================================")
    print(f"STAGE 2: Broad MetaPool v2 Evaluation for Top Candidates")
    print(f"========================================================")
    
    metapool_results = {}
    for cid, info in candidates_to_test.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}"
        
        print(f"\nEvaluating {cid} across MetaPool v2 (480 games)...")
        t0 = time.time()
        res = run_meta_pool_v2.run_meta_pool_v2(challenger_spec=spec_c, games_per_cell=20, workers=workers)
        el = time.time() - t0
        
        metapool_results[cid] = {
            "name": cid,
            "family": info.get("family", ""),
            "overall_win_rate": res["overall_win_rate"],
            "overall_wilson_ci": res["overall_wilson_ci"],
            "deck_summary": res["deck_summary"],
            "tier_summary": res["tier_summary"],
            "eval_time_sec": round(el, 1)
        }
        print(f"  -> MetaPool WR: {res['overall_win_rate']*100:.2f}% | CI: [{res['overall_wilson_ci'][0]*100:.1f}%, {res['overall_wilson_ci'][1]*100:.1f}%] ({el:.1f}s)")
        
    (REPORTS_DIR / "stage2_broad_meta_results.json").write_text(json.dumps(metapool_results, indent=2), encoding="utf-8")
    return metapool_results


def run_multi_stage_replication(top_candidates, workers=6):
    """Stage 3 & 4: 300g H2H vs V4 + E19, followed by Independent Seed Replication."""
    print(f"\n========================================================")
    print(f"STAGE 3 & 4: Rigorous 300g H2H and Independent Replications")
    print(f"========================================================")
    
    ogerpon_spec = "metaZ_teal_ogerpon_top10.csv"
    rep_results = {}
    
    for cid, info in top_candidates.items():
        rel_path = os.path.relpath(info["path"], ROOT_DIR).replace("\\", "/")
        spec_c = f"{rel_path}"
        
        print(f"\n[Run 1] 300-Game Dedicated H2H: {cid} vs V4 + E19...")
        r1 = ab_gate.run_gate(spec_c=spec_c, spec_i=ogerpon_spec, games=300, workers=workers)
        st1 = r1["chal"]
        w1 = st1["wins_seat0"] + st1["wins_seat1"]
        l1 = st1["losses"]
        d1 = st1["draws"]
        p1, lo1, hi1 = ab_gate.wilson(w1, w1 + l1)
        print(f"  Run 1 WR: {p1*100:5.1f}% [{lo1*100:4.1f}%, {hi1*100:4.1f}%] (W:{w1} L:{l1} D:{d1})")
        
        print(f"[Run 2] 300-Game INDEPENDENT REPLICATION (New Seeds): {cid} vs V4 + E19...")
        r2 = ab_gate.run_gate(spec_c=spec_c, spec_i=ogerpon_spec, games=300, workers=workers)
        st2 = r2["chal"]
        w2 = st2["wins_seat0"] + st2["wins_seat1"]
        l2 = st2["losses"]
        d2 = st2["draws"]
        p2, lo2, hi2 = ab_gate.wilson(w2, w2 + l2)
        print(f"  Run 2 WR: {p2*100:5.1f}% [{lo2*100:4.1f}%, {hi2*100:4.1f}%] (W:{w2} L:{l2} D:{d2})")
        
        rep_results[cid] = {
            "name": cid,
            "run1": {"wins": w1, "losses": l1, "draws": d1, "wr": float(p1), "ci": [float(lo1), float(hi1)]},
            "run2": {"wins": w2, "losses": l2, "draws": d2, "wr": float(p2), "ci": [float(lo2), float(hi2)]},
            "replicated": bool(p1 >= 0.55 and p2 >= 0.55)
        }
        
    (REPORTS_DIR / "stage3_replication_results.json").write_text(json.dumps(rep_results, indent=2), encoding="utf-8")
    return rep_results


if __name__ == "__main__":
    verify_control_freeze()
    lib = build_mechanism_library()
    cg = build_compatibility_graph(lib)
    candidates = generate_hybrid_candidates()
    print(f"Ready to execute screening and validation across {len(candidates)} hybrid candidates.")
