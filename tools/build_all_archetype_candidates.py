"""Constructs and validates all legal candidate decks for the Archetype Search."""

import json
import os
import sys
from pathlib import Path
from collections import Counter
from kaggle_environments import make

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import main as agent_mod
from tools import deck_compare


def build_bellibolt_deck():
    """Constructs legal 60-card Iono's Bellibolt ex Lightning Tempo deck."""
    # 4 Tadbulb, 3 Bellibolt ex, 3 Wattrel, 2 Kilowattrel, 2 Voltorb, 2 Electrode
    # 4 Poffin, 4 Ultra Ball, 2 Switch, 2 Boss's Orders, 4 Lillie, 4 Waitress, 2 Cyrano, 1 Prime Catcher, 21 Lightning Energy
    deck = (
        [268] * 4 +  # Iono's Tadbulb (Basic)
        [269] * 3 +  # Iono's Bellibolt ex (Stage 1)
        [270] * 3 +  # Iono's Wattrel (Basic)
        [271] * 2 +  # Iono's Kilowattrel (Stage 1)
        [265] * 2 +  # Iono's Voltorb (Basic)
        [266] * 2 +  # Iono's Electrode (Stage 1)
        [1086] * 4 + # Buddy-Buddy Poffin
        [1121] * 4 + # Ultra Ball
        [1123] * 2 + # Switch
        [1182] * 2 + # Boss's Orders
        [1227] * 4 + # Lillie's Determination
        [1235] * 4 + # Waitress
        [1205] * 2 + # Cyrano
        [1088] * 1 + # Prime Catcher (ACE SPEC)
        [4] * 21     # Basic Lightning Energy
    )
    assert len(deck) == 60, f"Deck has {len(deck)} cards, expected 60"
    return deck


def prepare_and_validate_all_archetypes():
    out_dir = Path("deck_search/candidates")
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = {
        "Starmie_S0": ("meta_starmie.csv", "Mega Starmie ex Fast Aggro (Baseline Control)"),
        "Alakazam_Psychic": ("metaB_alakazam.csv", "Alakazam ex / Dudunsparce Psychic Control"),
        "Grimmsnarl_Dark": ("metaG_grimmsnarl_top10.csv", "Grimmsnarl / Dark / Non-EX Disruption"),
        "Mewtwo_Stall": ("meta_mewtwo_stall.csv", "Mewtwo ex / Energy Denial / Stall"),
        "Dragapult_Spread": ("metaZ_dragapult_top10.csv", "Dragapult ex Phantom Dive Bench Spread"),
        "Archaludon_Metal": ("metaX_archaludon_sanjay.csv", "Archaludon ex Metal Bridge High-HP Tank"),
        "Ogerpon_Grass": ("metaZ_teal_ogerpon_top10.csv", "Teal Mask Ogerpon ex Teal Dance Acceleration"),
        "Bellibolt_Lightning": (build_bellibolt_deck(), "Iono's Bellibolt ex Lightning Tempo")
    }

    validated_paths = {}
    sanity_results = {}

    for name, (source, desc) in candidates.items():
        if isinstance(source, str):
            deck_list = [int(line.strip()) for line in open(source) if line.strip()]
        else:
            deck_list = source

        assert len(deck_list) == 60, f"Deck {name} has {len(deck_list)} cards"
        counts = Counter(deck_list)
        for cid, c in counts.items():
            if cid not in (1, 2, 3, 4, 5, 6, 7, 8):  # Energy IDs
                assert c <= 4, f"Deck {name} has {c}x card {cid} > 4 limit"

        csv_path = out_dir / f"{name}.csv"
        csv_path.write_text("\n".join(str(c) for c in deck_list) + "\n", encoding="utf-8")
        validated_paths[name] = str(csv_path)

        # 10-Game Sanity Evaluation
        wins, crashes = 0, 0
        for g in range(10):
            def p0(obs, _config):
                if obs.get("select") is None: return list(deck_list)
                agent_mod.DECK = list(deck_list)
                agent_mod.BS_CEI = True
                agent_mod.BS_CEI_2PLY = True
                agent_mod.BS_CEI_DETS = 2
                agent_mod.DYN_DECK_TABLES = True
                return agent_mod.agent(obs)

            def p1(obs, _config):
                if obs.get("select") is None: return list(deck_list)
                agent_mod.DECK = list(deck_list)
                agent_mod.BS_CEI = False
                return agent_mod.agent(obs)

            env = make("cabt", debug=False)
            env.run([p0, p1])
            st0 = env.state[0]
            if st0.status in ("INVALID", "ERROR", "TIMEOUT"):
                crashes += 1
            if (st0.reward or 0) == 1:
                wins += 1

        sanity_results[name] = {
            "name": name,
            "description": desc,
            "path": str(csv_path),
            "cards": len(deck_list),
            "unique": len(counts),
            "sanity_wins": wins,
            "sanity_crashes": crashes,
            "status": "PASS" if crashes == 0 else "FAIL"
        }
        print(f"Sanity Check for {name:22s}: {wins}/10 wins, {crashes} crashes -> {sanity_results[name]['status']}")

    (Path("deck_search") / "candidate_decks.json").write_text(json.dumps(sanity_results, indent=2), encoding="utf-8")
    print(f"Wrote deck_search/candidate_decks.json")
    return validated_paths


if __name__ == "__main__":
    prepare_and_validate_all_archetypes()
