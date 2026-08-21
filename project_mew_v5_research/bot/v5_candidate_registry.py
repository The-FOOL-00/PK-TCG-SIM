"""V5 Candidate Decks and Configurations Registry for Project Mew.

Provides standardized deck specifications, policy mappings, and hypotheses
for the 5 primary candidates evaluated in the V5 Breakthrough Search.
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DECKS_DIR = ROOT_DIR / "project_mew_v5_research" / "decks"
DECKS_DIR.mkdir(parents=True, exist_ok=True)

# Candidate 1: Fixed V4 Control (E19 + True V4 Policy)
# Addresses P0 Packaging Flaw
CANDIDATE_A_SPEC = {
    "name": "Candidate_A_Fixed_V4_Control",
    "deck_path": str(ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv"),
    "policy_version": "V4_TRUE",
    "patterns_enabled": ["P1_ANTI_TANK", "P2_ENERGY_SPILLOVER", "P3_BENCH_RESTRAINT"],
    "hypothesis": "Restores intended V4 behavior in production runtime. If live drop was solely packaging-related, fixes collapse."
}

# Candidate 2: V5-Ogerpon-Tech (E18 + Okidogi Non-ex Tech + V5 Policy)
# Addresses P0 Packaging Flaw + Cornerstone Mask Immunity Wall
CANDIDATE_B_SPEC = {
    "name": "Candidate_B_V5_Ogerpon_Tech",
    "deck_path": str(DECKS_DIR / "E18_Okidogi_Tech.csv"),
    "policy_version": "V5_ADAPTIVE",
    "patterns_enabled": ["P1_ANTI_TANK", "P2_ENERGY_SPILLOVER", "P3_BENCH_RESTRAINT", "P4_IMMUNITY_BYPASS"],
    "hypothesis": "Adds Okidogi (non-ex Basic) to break Cornerstone Stance / Crustle damage denial while preserving Ogerpon's 95% velocity."
}

# Candidate 3: V5-Alakazam-Master (Top Meta Dominator)
# Addresses Meta Shift toward Alakazam (40.1% of Ladder)
CANDIDATE_C_SPEC = {
    "name": "Candidate_C_V5_Alakazam_Master",
    "deck_path": str(ROOT_DIR / "metaB_alakazam.csv"),
    "policy_version": "V5_ALAKAZAM_TACTICAL",
    "patterns_enabled": ["P1_ANTI_TANK", "P2_ENERGY_SPILLOVER", "P3_BENCH_RESTRAINT"],
    "hypothesis": "Aligns with the dominant 40.1% high-ladder meta with 73% top-tier replay win rate."
}

# Candidate 4: V5-Garchomp-Power (Cynthia's Garchomp ex nasuo445 Build)
# Addresses Robust Stage-2 Setup without Mulligan Sensitivity
CANDIDATE_D_SPEC = {
    "name": "Candidate_D_V5_Garchomp_Power",
    "deck_path": str(ROOT_DIR / "metaC_garchomp_nasuo.csv"),
    "policy_version": "V5_GARCHOMP_TEMPO",
    "patterns_enabled": ["P1_ANTI_TANK", "P2_ENERGY_SPILLOVER"],
    "hypothesis": "320 HP stage 2 power + fighting typing counters high-HP tanks and dark meta."
}

# Candidate 5: V5-Crustle-Wall (Anti-Meta Damage Mitigation)
# Addresses High-Burst Meta with Damage Reduction
CANDIDATE_E_SPEC = {
    "name": "Candidate_E_V5_Crustle_Wall",
    "deck_path": str(DECKS_DIR / "Crustle_Wall.csv"),
    "policy_version": "V5_WALL_STALL",
    "patterns_enabled": ["P1_ANTI_TANK", "P3_BENCH_RESTRAINT"],
    "hypothesis": "Counters aggressive ex attackers with damage-reduction walls."
}

def create_candidate_decks():
    # Build E18_Okidogi_Tech.csv (3 Teal Mask Ogerpon ex + 1 Okidogi ID 1091 + 18 Grass Energy + 38 Trainers)
    e19_src = (ROOT_DIR / "deck_search_ogerpon_counter" / "energy_neighborhood" / "E19.csv").read_text().splitlines()
    e19_ids = [int(line.strip()) for line in e19_src if line.strip()]
    
    # Replace 1 Ogerpon ex (ID 96) with 1 Okidogi (ID 1091) and 1 Energy (ID 1) with 1 Fighting Energy / Super Rod (ID 1140)
    e18_tech = []
    og_replaced = False
    en_replaced = False
    for cid in e19_ids:
        if cid == 96 and not og_replaced:
            e18_tech.append(1091) # Okidogi (Basic 130 HP Non-ex)
            og_replaced = True
        elif cid == 1 and not en_replaced:
            e18_tech.append(1140) # Super Rod
            en_replaced = True
        else:
            e18_tech.append(cid)
            
    (DECKS_DIR / "E18_Okidogi_Tech.csv").write_text("\n".join(str(c) for c in e18_tech) + "\n", encoding="utf-8")

    # Build Crustle_Wall.csv (4 Dwebble 1078, 4 Crustle 1079, 4 Battle Cage 1176, 4 Community Center 1250, 44 Trainers/Energy)
    crustle_deck = [
        1078, 1078, 1078, 1078, # Dwebble
        1079, 1079, 1079, 1079, # Crustle
        1176, 1176, 1176, 1176, # Battle Cage
        1250, 1250, 1250, 1250, # Community Center
        1094, 1094, 1094, 1094, # Bug Catching Set
        1180, 1180, 1180, 1180, # Nest Ball
        1181, 1181, 1181, 1181, # Ultra Ball
        1182, 1182, 1182, 1182, # Boss's Orders
        1213, 1213, 1213, 1213, # Judge
        1227, 1227, 1227, 1227, # Lillie's Determination
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 # 20 Grass Energy
    ]
    (DECKS_DIR / "Crustle_Wall.csv").write_text("\n".join(str(c) for c in crustle_deck) + "\n", encoding="utf-8")
    print(f"Created candidate decks in {DECKS_DIR}")

if __name__ == "__main__":
    create_candidate_decks()
