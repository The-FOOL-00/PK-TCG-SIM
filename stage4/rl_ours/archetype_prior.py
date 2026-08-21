"""Gate 2: build a SEARCH_PRIOR card-weight table from the 07-22 top-10 harvest.

Contract (main.py `sample_opponent_deck`):
    w = 1.0 if prior is None else max(0.0, prior.get(cid, 1.0))
NOTE the default: a card ABSENT from the dict gets weight 1.0. So the table
must cover the whole pool explicitly — archetype cards get high weight,
everything else a small epsilon — otherwise the ~1,200 off-archetype cards
would each outweigh an archetype card.

Weight model: w(card) = BASE * sum_a [ share(a) * copies(card, list_a) ]
for cards appearing in any harvested archetype list, else EPS.
`share(a)` is the archetype's observed frequency among harvested top-10 sides.

Also note (documented in GATE2_FACTORIAL.md): passing a non-None prior makes
main.py skip both `_comp_prior()` and the `dom_type` energy-coherence
mechanism, since both live under `if prior is None`. The factorial variable is
therefore "belief model", not "weights only".
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HARVEST = REPO / "analysis" / "phase2_meta_shift" / "profile_top10_jul22.json"

BASE = 400.0     # archetype-card weight scale
EPS = 0.002      # off-archetype weight (not 0: sampler must not underflow)


def archetype_lists(min_sides=8):
    """{label: (share, representative 60-card list, n_sides)} from the harvest."""
    import sys
    sys.path.insert(0, str(REPO / "tools"))
    from meta_miner import archetype

    data = json.loads(HARVEST.read_text(encoding="utf-8"))
    by_arch = defaultdict(list)
    for s in data["sides"]:
        deck = s.get("deck")
        if not deck:
            continue
        a = archetype(deck)
        if a:
            by_arch[a["label"]].append(tuple(sorted(deck)))
    total = sum(len(v) for v in by_arch.values())
    out = {}
    for label, lists in by_arch.items():
        if len(lists) < min_sides:
            continue
        rep = Counter(lists).most_common(1)[0][0]   # modal exact list
        out[label] = (len(lists) / total, list(rep), len(lists))
    # renormalise shares over the kept archetypes
    tot_share = sum(v[0] for v in out.values()) or 1.0
    return {k: (v[0] / tot_share, v[1], v[2]) for k, v in out.items()}


def build_prior(pool_ids, arch=None):
    """card_id -> weight, covering every id in `pool_ids`."""
    arch = arch or archetype_lists()
    acc = defaultdict(float)
    for _label, (share, lst, _n) in arch.items():
        for cid, copies in Counter(lst).items():
            acc[cid] += share * copies
    prior = {int(cid): EPS for cid in pool_ids}
    for cid, w in acc.items():
        prior[int(cid)] = BASE * w
    return prior, arch


def main():
    import sys
    sys.path.insert(0, str(REPO))
    import main as agent_mod
    agent_mod._pool()
    pool = agent_mod._pool()
    prior, arch = build_prior(pool.keys())
    print(f"archetypes kept: {len(arch)}   pool size: {len(pool)}")
    print(f"{'archetype':<48s} {'share':>7s} {'sides':>6s} {'uniq cards':>11s}")
    for label, (share, lst, n) in sorted(arch.items(), key=lambda kv: -kv[1][0]):
        print(f"{label[:48]:<48s} {share*100:>6.1f}% {n:>6d} {len(set(lst)):>11d}")
    covered = sum(1 for w in prior.values() if w > EPS)
    print(f"\ncards with archetype weight: {covered} / {len(prior)} "
          f"({covered/len(prior)*100:.1f}% of pool)")
    ws = sorted((w for w in prior.values() if w > EPS), reverse=True)
    print(f"archetype weight range: {ws[-1]:.2f} .. {ws[0]:.2f}   (off-archetype {EPS})")
    print(f"mass ratio archetype:off = "
          f"{sum(ws):.0f} : {EPS*(len(prior)-covered):.2f}")
    out = REPO / "stage4" / "rl_ours" / "archetype_prior.json"
    out.write_text(json.dumps({"prior": {str(k): v for k, v in prior.items()},
                               "archetypes": {k: {"share": v[0], "n_sides": v[2]}
                                              for k, v in arch.items()}}),
                   encoding="utf-8")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
