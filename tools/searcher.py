"""Determinized-search teacher on cg.api search_begin/search_step (Phase 2a).

What the engine gives us: search_begin(obs, <predicted hidden zones>) is NOT a
search algorithm — it is a determinized forward SIMULATOR. We supply a full
prediction of every hidden zone (both decks, both prizes, opponent hand,
face-down active); it returns a root SearchState. search_step(id, [i]) applies
option i and returns a new state (old ids stay alive -> tree branching;
search_release frees one node, search_end wipes the arena). State.result is
the winner index (-1 while running); State.yourIndex says whose selection each
node is, so we simulate BOTH players.

The teacher built here: flat determinized Monte Carlo ("PIMC-1"):
  for each of --det determinizations (uniform shuffles of the unseen pools,
  exact in mirror self-play where both 60-card lists are known):
      root = search_begin(...)
      for each of the top --topk options by v1 score:
          child = search_step(root, [i])
          value += --roll rollouts: BOTH sides play main.py's v1 heuristic
                   (main._decide) to State.result, or the rung-a value net
                   at --cap steps (calibrated P(win), flipped to the acting
                   player's perspective)
  choose argmax mean value. Search only fires on single-select decisions with
  >1 option; everything else (multi-select, yes/no counts) stays pure v1.

Local-only tool: cg.dll never ships. Used by the 2a strength gate
(tools/ab_gate.py --challenger "deck.csv+TEACHER=det2,roll1,topk4") and by
tools/gen_distill.py (2b).
"""

import ctypes
import json
import random
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE_CG_DIR = REPO / "sample_submission" / "sample_submission"
sys.path.insert(0, str(REPO))

import main as agent_mod  # noqa: E402  (v1 rollout policy + value net + card db)

# AFTER main: the sample dir has its own main.py which must not shadow ours
if str(SAMPLE_CG_DIR) not in sys.path:
    sys.path.append(str(SAMPLE_CG_DIR))

AREA_ACTIVE, AREA_BENCH = 4, 5
ST_MAIN = 0


# ------------------------------------------------------------ engine glue ----

class Search:
    """Direct cg.dll search driver. Parses the raw JSON into plain dicts, so
    node observations have exactly the field names main.py's scorers expect
    (they match the kaggle_environments observation dicts)."""

    def __init__(self):
        import cg.sim as sim  # loads cg.dll + GameInitialize()
        self.lib = sim.lib
        self.ptr = self.lib.AgentStart()

    def begin(self, sbi, your_deck, your_prize, opp_deck, opp_prize,
              opp_hand, opp_active, manual_coin=False):
        arr = lambda v: (ctypes.c_int * len(v))(*v)  # noqa: E731
        bs = self.lib.SearchBegin(
            self.ptr, sbi.encode("ascii"), len(sbi),
            arr(your_deck), arr(your_prize), arr(opp_deck), arr(opp_prize),
            arr(opp_hand), arr(opp_active), int(manual_coin))
        r = json.loads(bs)
        if r.get("error"):
            raise RuntimeError("SearchBegin error %s" % r["error"])
        return r["state"]

    def step(self, search_id, select):
        bs = self.lib.SearchStep(
            self.ptr, search_id, (ctypes.c_int * len(select))(*select), len(select))
        r = json.loads(bs)
        if r.get("error"):
            raise RuntimeError("SearchStep error %s" % r["error"])
        return r["state"]

    def release(self, search_id):
        self.lib.SearchRelease(self.ptr, search_id)

    def end(self):
        self.lib.SearchEnd(self.ptr)


# --------------------------------------------------------- determinization ----

def _visible_ids(player, include_hand):
    ids = []
    if include_hand:
        ids += [c["id"] for c in player.get("hand") or [] if c]
    for pk in (player.get("active") or []) + (player.get("bench") or []):
        if pk:  # face-down active shows as None
            ids.append(pk["id"])
            for zone in ("energyCards", "tools", "preEvolution"):
                ids += [c["id"] for c in pk.get(zone) or [] if c]
    ids += [c["id"] for c in player.get("discard") or [] if c]
    ids += [c["id"] for c in player.get("prize") or [] if c]  # revealed prizes
    return ids


def _fill_prize(prize, sampled):
    """Keep revealed prize cards in position, fill hidden slots from sampled."""
    out, k = [], 0
    for c in prize or []:
        if c:
            out.append(c["id"])
        else:
            out.append(sampled[k])
            k += 1
    return out


def determinize(cur, me, my_deck60, opp_deck60, rng):
    """Uniform sample of all hidden zones consistent with the observation.
    Returns kwargs for Search.begin (minus sbi/manual_coin)."""
    mine, theirs = cur["players"][me], cur["players"][1 - me]

    my_pool = list((Counter(my_deck60) - Counter(_visible_ids(mine, True))).elements())
    rng.shuffle(my_pool)
    n_hidden_prize = sum(1 for c in mine.get("prize") or [] if not c)
    my_prize = _fill_prize(mine.get("prize"), my_pool[:n_hidden_prize])
    my_deck = my_pool[n_hidden_prize:]

    opp_pool = list((Counter(opp_deck60) - Counter(_visible_ids(theirs, False))).elements())
    rng.shuffle(opp_pool)
    opp_active = []
    active = theirs.get("active") or []
    if active and active[0] is None:  # face-down: predict a Basic Pokemon
        basics = [i for i in opp_pool
                  if agent_mod.CARDS.get(i, {}).get("basic")]
        pick = rng.choice(basics) if basics else opp_pool[0]
        opp_pool.remove(pick)
        opp_active = [pick]
    n_hand = theirs.get("handCount") or 0
    opp_hand = opp_pool[:n_hand]
    rest = opp_pool[n_hand:]
    n_opp_hidden_prize = sum(1 for c in theirs.get("prize") or [] if not c)
    opp_prize = _fill_prize(theirs.get("prize"), rest[:n_opp_hidden_prize])
    opp_deck = rest[n_opp_hidden_prize:]

    return {"your_deck": my_deck, "your_prize": my_prize,
            "opp_deck": opp_deck, "opp_prize": opp_prize,
            "opp_hand": opp_hand, "opp_active": opp_active}


# ----------------------------------------------------------------- rollout ----

def node_result(node):
    return node["observation"]["current"]["result"]


def rollout(search, node, me, cap=400, release=True):
    """Both sides play main's v1 policy to terminal. Returns value in [0,1]
    for player `me`; at the step cap, the rung-a value net (if loadable)
    scores the position, else 0.5."""
    steps = 0
    prev_id = None
    while True:
        cur = node["observation"]["current"]
        if cur["result"] != -1:
            if release and prev_id is not None:
                search.release(prev_id)
            return 1.0 if cur["result"] == me else 0.0
        if steps >= cap:
            v = 0.5
            model = agent_mod._lv_model()
            if model is not None:
                p = agent_mod._lv_predict(
                    model, [agent_mod.encode_state(cur)])[0]
                v = p if cur["yourIndex"] == me else 1.0 - p
            if release and prev_id is not None:
                search.release(prev_id)
            return v
        sel = agent_mod.agent(node["observation"])  # C1-validated, never raises
        nxt = search.step(node["searchId"], sel)
        if release and prev_id is not None:
            search.release(prev_id)
        prev_id = node["searchId"]
        node = nxt
        steps += 1


# ----------------------------------------------------------------- teacher ----

def v1_ranked_options(obs):
    """Option indices best-first under the v1 scorer (flags all off here)."""
    sel = obs["select"]
    cur = obs["current"]
    me = cur["yourIndex"]
    scores = [agent_mod._score_option(o or {}, sel, cur, me)
              for o in sel["option"]]
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))


def searchable(obs):
    sel = obs.get("select")
    return (sel is not None and obs.get("current") is not None
            and obs["current"].get("result", -1) == -1
            and obs.get("search_begin_input")
            and sel.get("type") == ST_MAIN
            and sel.get("minCount", 1) == 1 and sel.get("maxCount", 1) == 1
            and len(sel.get("option") or []) > 1)


class Teacher:
    """Search-guided policy: v1 everywhere, determinized MC on MAIN choices."""

    def __init__(self, deck, det=2, roll=1, topk=4, cap=400, seed=0):
        self.search = Search()
        self.deck = list(deck)
        self.det, self.roll, self.topk, self.cap = det, roll, topk, cap
        self.rng = random.Random(seed)
        self.stats = {"decisions": 0, "searched": 0, "changed": 0}

    def choose(self, obs):
        """Returns (selection list, searched flag, candidate order or None)."""
        self.stats["decisions"] += 1
        v1_answer = agent_mod._decide(obs)[0]
        if not searchable(obs):
            return v1_answer, False, None
        cur = obs["current"]
        me = cur["yourIndex"]
        cands = v1_ranked_options(obs)[:self.topk]
        if len(cands) < 2:
            return v1_answer, False, None
        self.stats["searched"] += 1
        totals = {i: 0.0 for i in cands}
        n = 0
        for _d in range(self.det):
            det = determinize(cur, me, self.deck, self.deck, self.rng)
            try:
                root = self.search.begin(obs["search_begin_input"], **det)
                for i in cands:
                    for _r in range(self.roll):
                        node = self.search.step(root["searchId"], [i])
                        totals[i] += rollout(self.search, node, me, self.cap)
                n += self.roll
            except Exception as e:
                print("[teacher] search failed (%s); v1 fallback" % e,
                      file=sys.stderr, flush=True)
            finally:
                self.search.end()
        if n == 0:
            return v1_answer, False, None
        best = max(cands, key=lambda i: (totals[i] / n, -cands.index(i)))
        if [best] != v1_answer:
            self.stats["changed"] += 1
        return [best], True, cands


def make_agent(deck, **kw):
    """kaggle_environments-style wrapper (obs, config) -> answer."""
    teacher = Teacher(deck, **kw)

    def wrapper(obs, _config=None):
        if obs.get("select") is None:
            return list(deck)
        ans, _searched, _cands = teacher.choose(obs)
        return ans
    wrapper.teacher = teacher
    return wrapper
