# HANDOFF — 2026-07-11 (session switch at Stage 3B → Option A)

## 1. STATE

Ladder: **v2.0.0 (search + our 35-energy deck) = μ614 is the incumbent and
anchor — never displace it**; v2.1.0-alakazam (μ548) is the weak slot to
displace on next submit. Teammate Sanjay's PPO = μ616.8. Top-5 ≈ μ1100;
current #1 Yushin Ito 1277.8. Work stream: Stage 3B-Garchomp (behavior
cloning) is DONE and FAILED its gates (G6a 31.0%, G6b 42.7%, G6c 44.7%);
the diagnosed cause is fixable, and the chosen next step is **Option A:
BC-full — extend imitation to ST_CARD sub-decisions**, then gates. If A
fails its gates but shows signal beyond current BC, follow-up is Option B
(BC-full as rollout policy inside the search).

## 2. JOURNEY

1. v1 heuristic shipped, μ≈512 — below field average; 1-ply upgrades all failed gates.
2. Pivot: runtime belief-search agent (CardTracker + determinized MC on bundled cg/); probe proved cg+search green on-ladder (Linux-x86_64/Py3.11.13). Shipped v2.0.0 → μ614.
3. S1 distilled policy and value-truncation both failed to beat terminal-v1 rollouts; shipped numpy-free.
4. Alakazam deck-swap feasibility gate said 74.7% — **ladder said μ548**: the gate's opponent (ourselves on the old deck) hid a shared piloting weakness. Rank-1 (Majkel) plays a byte-identical list, so it was 100% piloting.
5. Garchomp (nasuo445's list) + tempo heuristics FAILED G1 at 39.3% vs v2.0.0 — attacker online turn 13.6 vs nasuo's ~6.
6. **Architectural finding: search+v1-rollout cannot plan multi-turn evolution/combo setup** — fails every complex meta deck, pilots only our simple aggro deck. Top-10 run fast policies (31–92ms), not search.
7. Pivoted to BC from top replays (99.7% clean (state,chosen-index) recovery via the step-i-obs ↔ step-i+1-action alignment; 812-episode harvest of current top-10 in data/top_replays_bulk/).
8. BC-Garchomp: val top-1 69.4% vs 20.8% v1-agreement floor (best learning signal in the project) — but G6a 31.0 / G6b 42.7 / G6c 44.7 ALL FAIL; diagnosed as **sub-decision blindness + compounding off-distribution error**. Next: Option A.

## 3. LOCKED DECISIONS

- v1 is dead as a gate reference. Gates: 300 games, seats alternated,
  Wilson CI, PASS = lower bound >50% vs the current strongest incumbent
  (v2.0.0 μ614 until something stronger ships).
- Safety machinery byte-identical in every variant: C1 validation asserts,
  resolve_selection, D-governor, fallback chain. Local gate PASS is
  necessary, never sufficient — the ladder is the true gate (24–48h watch
  before calling a new incumbent).
- Bundle target: Linux-x86_64, Python 3.11.13; <190MiB; exec-load in bare
  temp dir; fault-injection suite; 30-game zero-crash; deck validate;
  cg/ nested like the sample; on-ladder SearchBegin ≈3.3ms (~20x local).
- Kaggle CLI: `py -3.12 -m kaggle ...`; CLI 2.2.3 auth is buggy client-side
  — tools use the OAuth bearer from ~/.kaggle/credentials.json via direct
  HTTP; token expires (~hours), user re-runs `py -3.12 -m kaggle auth login`.
- No competition episode data in the repo (data/ is gitignored).
- Kaggle slot rule: automatic latest-2-by-time. To ship X while keeping
  v2.0.0: re-submit v2.0.0 FIRST, then X (displaces the weak slot, never
  the anchor). User does all submissions (team 2-slot coordination).
- Python: use `C:/Users/Sundareswaran/AppData/Local/Python/pythoncore-3.12-64/python.exe`
  (plain `python`/`py` alias flaky for repo tools).
- Commits: per phase/gate, NO Claude co-author line.

## 4. KEY FILES

- `main.py` — agent: v1 heuristic + belief search (PTCG_SEARCH,
  SEARCH_BELIEF=comp|mirror|uniform|oracle) + governor + PILOT heuristics +
  BC hook (PTCG_BC, `_bc_model`/`_bc_decide`, weights bc_weights_<tag>.npz,
  policy-contract forward `_pol_choose`).
- `tools/ab_gate.py` — the only gate harness (spec: `deck.csv+NAME=VALUE`
  sets main.py module attrs per side; sets DECK per side; ORACLE=<deck>).
- `training/train_policy.py` (S1 pipeline + npz inference contract),
  `training/train_bc.py` (BC: dropout/L2/early-stop, same contract).
- `tools/extract_bc_data.py` (replay → BC targets, serve-path encoding),
  `tools/bc_feasibility.py`, `tools/harvest_episodes.py` (top-10 episode
  harvester), `tools/analyze_top_replays.py`, `tools/analyze_garchomp_losses.py`
  (--mode search|bc), `tools/diagnose_belief.py`, `tools/stress_governor.py`,
  `tools/build_search_submission.py` (--deck --rollout --cap --version),
  `tools/searcher.py` (2a teacher), `tools/test_tracker.py`,
  `tools/test_search_robustness.py` (fault suite — must stay green).
- Decks: `deck.csv` (ours), `metaB_alakazam.csv` (= Majkel's, rank-2),
  `metaC_garchomp_nasuo.csv` (rank-7), `metaD_mewtwo_kashiwashira.csv`.
- Reports: `report/LADDER_INTEL.md`, `report/LADDER_INTEL_REFRESHED.md`
  (2026-07-10 top-10 + per-deck BC pools), `report/WRITEUP_DRAFT.md`
  (rubric writeup — every gate goes here + EXPERIMENT_LOG.md).
- Data (gitignored): `data/top_replays_bulk/` (812 top-10 episodes +
  _manifest.csv), `data/bc_garchomp/decisions.npz` (4,610 targets),
  `data/leaderboard_snapshot_2026-07-10.csv`, `runs/` (gate JSONs, some
  force-committed).

## 5. WHY OPTION A

BC-Garchomp's val top-1 69.4% vs a 20.8% agree-with-v1 floor is the
strongest learning signal the project has produced, but ship gates came in
at 31–44.7%. Diagnosis (EXPERIMENT_LOG 2026-07-11): (1) **sub-decision
blindness** — the net answers only MAIN single-selects (60% of decisions);
the setup actually flows through ST_CARD sub-decisions (which Pokémon
Buddy-Buddy Poffin / Fighting Gong fetch), still answered by v1, so the
imitated line's pieces never reach the hand. **14,960 winning-side ST_CARD
targets sit unused** (more than the 29,429 MAIN targets across the top-10
pool; Garchomp-specific counts in data/bc_garchomp + re-extract). (2)
compounding off-distribution error (0.69⁵ ≈ 16% chance of a 5-step line).
Option A removes cause 1: new option encoder for ST_CARD contexts (Option
fields: cardId/area/index/context — see `_score_card` for the semantics v1
uses), joint or two-headed training, integrate behind the same PTCG_BC flag
covering ~90% of decisions. Current G6 numbers are a 60%-BC/40%-v1 hybrid's
failure, not BC's ceiling — A must land before an honest BC verdict.
Then gates: BC-full vs v2.0.0 (ship-critical), vs search+Garchomp, and the
piloting-signature check (first-attack turn vs nasuo's 4.1 —
`tools/analyze_garchomp_losses.py --mode bc`).

## 6. WHAT THE NEXT SESSION DOES

1. Read this file, then: EXPERIMENT_LOG.md (last ~20 entries), `git log
   --oneline -20`, WRITEUP_DRAFT.md §2b onward.
2. Report state concisely to the user before doing anything.
3. Execute Option A (build → gates → stop-report per the locked gate
   discipline). Do not start Option B without a gate verdict on A.

## 7. OPEN QUESTIONS

- **Kaggle slots:** rule is automatic latest-2-by-time (user confirmed).
  Verify at next ship that the submit sequence displaces v2.1.0 (548) and
  never v2.0.0 (614): re-submit v2.0.0 first, then the new bundle. Ask the
  user whether manual deactivation exists on the comp page (checkbox
  situation unconfirmed).
- **Sanjay's PPO trajectory:** unknown — per the Stage-4 decision gate, ask
  the user for his training-reward trend before any RL work.
- G6c detail worth remembering: 64 of BC's 134 wins were by DECKOUT — the
  net absorbed the meta's grind texture; it loses on prize-race tempo.
- OAuth token may be expired at session start — ask user to re-auth before
  any harvest/download work.
