# Contradictions Register & Discrepancy Reconciliation

**Repository:** `https://github.com/The-FOOL-00/PK-TCG-SIM.git`  
**Current Head:** `main` (commit `86abcef`)  
**Scope:** Formal record of historical contradictions, measurement artifacts, documentation errors, and methodological discrepancies discovered and reconciled during the competition research cycle.

---

## 1. Contradictions Register Overview

| ID | Issue Title | Source A (Claim) | Source B (Contradicting Evidence) | Resolution Status | Final Authoritative Finding |
|---|---|---|---|---|---|
| **C1** | **V1 Peak Rating Narrative vs Empirical Truth** | Early informal notes & memos: *"Aggressive agent reached ~995 peak"* | `aggressive_peak_reconstruction.json`, `data/live_complete_history/` | **Resolved** | V1 TrueSkill peak was $\mu = 857.1$ ($\sigma = 35.0$) at Game 109. Max opponent faced was 1118.8. True project peak was $\mu = 939.5$ (V3, Game 39). |
| **C2** | **Final Archive Packaged Deck Description** | Early draft in `docs/FINAL_ARTIFACTS.md`: *"Byte-for-byte match with canonical E19 list"* | Card decoding of `deck.csv` inside `project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz` | **Resolved** | Deck `0f8fb632...` is the 60-card **Alakazam Master V5** decklist, selected to eliminate the 0% Cornerstone auto-loss and pierce Crustle walls. |
| **C3** | **Diagnostic Tool Shadow-Bug Importing Random Agent** | Early diagnostic reports: *"first-attack turn 10.8 (search) / 14.6 (BC)"* | `EXPERIMENT_LOG.md` L735–757, tool source code audit | **Resolved** | Tools prepended `sample_submission/` to `sys.path`. Re-measurement showed V1 attacks at turn 4.6 and BC at 6.4; setup quality was the true discriminator. |
| **C4** | **Local Feasibility Gate vs Live Ladder Falsification** | Local A/B gate: *"v2.1.0 Alakazam beats old deck 74.7% [69.5%, 79.3%]"* | Live Kaggle ladder: `v2.1.0` scored $\mu = 548$ (-66 pt vs `v2.0.0` $\mu = 614$) | **Resolved** | Measurement artifact: both sides mis-piloted Alakazam combo sub-decisions symmetrically in local self-play, concealing the shared defect. |
| **C5** | **Sequencing Rules in Self-Play vs Live Ladder** | Self-play screen: *E1/E2 dropped as noise (delta $\le 0.025$)* | Live ladder telemetry: `v1_grimm_seq_e1e2` achieved +0.0853 velocity over `v1_grimmsnarl` | **Resolved** | Structural self-play property: taking a free action before a terminal action cancels in mirror matches; benefits only appear cross-deck. |
| **C6** | **V4 Expected Win Rate vs Live Rating Collapse** | Paired benchmark: *V4 achieved 86.67% WR ($p = 0.0034$)* | Live ladder score dropped to $\approx 689$ Elo | **Resolved** | P0 packaging bug: `project_mew_v4_challenger.tar.gz` had an unpatched root `main.py` that failed to call `v4_policy`, executing legacy V1 heuristics. |
| **C7** | **Global Optimality Claim for E19 Deck** | Memo statements: *"E19 proved globally optimal"* | `PROJECT_MEW_EVIDENCE_LEDGER.md` Claim 8, combinatorial card math | **Resolved** | E19 statistically dominated all 243 evaluated hybrid variations ($p < 0.001$), but "global optimality" over the full $10^{15}$ space is unprovable. |

---

## 2. Detailed Discrepancy Audits

### Contradiction 1: V1 Peak Rating Narrative vs Empirical Truth
- **Investigation**: Reconstructed the complete match-by-match trajectory of all 120 live ladder games played by V1 (`aggressive_peak_reconstruction.json`).
  - Games 1–25: 22W / 3L (88.0% WR), climbing from $\mu = 504.5$ to $775.1$.
  - Games 26–50: 17W / 8L (68.0% WR), reaching $\mu = 827.6$.
  - Games 51–109: Peak rating reached $\mu = 857.1$ ($\sigma = 35.0$) at Game 109 after defeating `Bot_Competitive_785` ($\mu = 667.2$).
  - Games 110–120: Faced elite opponents ($\mu > 1000$), finishing with settled $\mu = 844.6$.
  - Opponents Faced: Average opponent rating was 782.6; maximum opponent faced was 1118.8.
- **Root Cause**: Early team memos conflated the maximum opponent rating faced ($1118.8$) or the 3-sigma upper confidence bound ($\mu + 3\sigma = 962.1$) with the agent's posterior mean $\mu$.
- **Resolution**: Canonical documentation records $\mu = 857.1$ as V1's true peak and $\mu = 939.5$ (V3) as the project's authenticated peak.

### Contradiction 2: Final Archive Packaged Deck Description
- **Investigation**: Inspected the physical contents of `candidates/final/project_mew_aggressive_surgical_kaggle_fixed_candidate.tar.gz`. Extracted `deck.csv` (`0f8fb632ade2833645af8c6ffe2b282fe24e7446ee8b23f3e468b8410d8ea36c`) and resolved card IDs against `EN_Card_Data.csv`.
- **Finding**: The deck contains:
  - 4x Abra (741), 4x Kadabra (742), 4x Alakazam (743)
  - 4x Dunsparce (305), 3x Dudunsparce (66)
  - 4x Rare Candy (1079), 4x Enhanced Hammer (1081), 4x Buddy-Buddy Poffin (1086), 3x Night Stretcher (1097), 1x Sacred Ash (1129)
  - 4x Poké Pad (1152), 3x Boss's Orders (1182), 1x Lana's Aid (1184), 4x Hilda (1225), 4x Dawn (1231), 1x Battle Cage (1264)
  - 4x Telepath Psychic Energy (19), 3x Basic {P} Energy (5), 1x Enriching Energy (13)
- **Root Cause**: Earlier drafts of `docs/FINAL_ARTIFACTS.md` conflated V4's active Ogerpon E19 deck with the final candidate's actual packaged deck. As detailed in `PROJECT_MEW_AGGRESSIVE_SURGICAL_CANDIDATE_RESEARCH_REPORT.md` §15–17, the team paired Aggressive-Surgical with Alakazam Master V5 to neutralize Cornerstone Mask ex and Crustle walls.
- **Resolution**: Updated `docs/FINAL_ARTIFACTS.md`, `docs/ARCHITECTURE.md`, and `docs/RESEARCH_HISTORY.md` to accurately document the 60-card Alakazam Master V5 list and the strategic reasoning behind its selection.

### Contradiction 3: Diagnostic Tool Shadow-Bug Importing Random Agent
- **Investigation**: Audited imports in `tools/analyze_garchomp_losses.py` and `tools/diagnose_alakazam_piloting.py`. Both scripts contained `sys.path.insert(0, "sample_submission/sample_submission")` prior to `import main`. Because `sample_submission/` contained a 38-line random sample agent, all diagnostic runs invoked random play.
- **Impact Analysis**: Only diagnostic behavioral telemetry was affected; formal gates (`ab_gate.py`), extraction pipelines, and ladder submissions imported the root `main.py` directly and were completely unaffected.
- **Resolution**: Both tools were patched with assertion guards (`assert hasattr(main, "STATS")`), and all behavioral signatures were re-measured and documented in `EXPERIMENT_LOG.md` (2026-07-11).

### Contradiction 4: Local Feasibility Gate vs Live Ladder Falsification (v2.1.0)
- **Investigation**: Evaluated why `v2.1.0-alakazam` scored 74.7% in local testing but collapsed to $\mu = 548$ on ladder.
- **Root Cause**: The local gate evaluated our search agent on Alakazam against our search agent on the 35-Energy deck. Because both sides were piloted by the same search engine—which only handled MAIN-phase single-selects and skipped combo trainer sub-decisions—both sides mis-piloted Alakazam symmetrically. On the live ladder, human pilots and top-tier bots exploited combo sequencing that our search could not execute.
- **Resolution**: Formulated the permanent methodological rule: *A gate whose opponent is oneself cannot detect a shared piloting weakness; all future gates must evaluate cross-deck against strong external baselines.*

### Contradiction 5: Sequencing Rules in Self-Play vs Live Ladder
- **Investigation**: Investigated why sequencing rules E1 and E2 (take free actions before attacking) appeared neutral in mirror self-play but delivered +0.0853 prize velocity on the live ladder.
- **Root Cause**: Taking a costless board-advancing action before ending a turn with an attack is strictly dominated. In a mirror match, both agents receive the identical benefit, canceling out in pairwise win rates. Against diverse ladder opponents who play sub-optimally, the tempo advantage manifests clearly.
- **Resolution**: Replaced mirror self-play screens with cross-deck screening protocols (`KE` family).

### Contradiction 6: V4 Expected Win Rate vs Live Rating Collapse
- **Investigation**: Analyzed why the live V4 deployment dropped to $\approx 689$ Elo despite an 86.67% paired offline benchmark.
- **Root Cause**: A clean-process audit of `project_mew_v4_challenger.tar.gz` revealed that root `main.py` failed to import `project_mew_v4.bot.v4_policy` or call `select_v4_action`. The archive ran the unpatched legacy V1 heuristic in production.
- **Resolution**: Built `project_mew_v4_corrected_candidate.tar.gz` (`44456613...`) with static verification assertions, confirming execution of Patterns 1, 2, and 3.

### Contradiction 7: Global Optimality Claim for E19 Deck
- **Investigation**: Evaluated the claim that E19 is "globally optimal".
- **Root Cause**: While E19 statistically outperformed all 243 evaluated hybrid variations ($p < 0.001$), the search space was restricted to pre-selected counter-mechanisms. The full space of legal 60-card decks exceeds $10^{15}$ permutations.
- **Resolution**: Refined claims to specify that E19 is optimal within the explored hybrid search space.
