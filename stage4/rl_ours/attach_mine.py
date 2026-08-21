"""Mine OT_ATTACH target-selects for Kangaskhan/Raging Bolt deck.
For every MAIN decision where the pilot chose OT_ATTACH, record which
Pokemon received the energy. Compare top-10 vs our v1-alone piloting."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from meta_miner import archetype  # noqa: E402

CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in CD["cards"].items()}

KANG_LABEL = "Mega Kangaskhan ex / Raging Bolt ex"
OT_ATTACH = 8
AREA_ACTIVE, AREA_BENCH = 4, 5

# Deck Pokemon IDs (from metaX_kangaskhan_top10.csv verified against card_data)
RAGING_BOLT = 63
MEGA_KANG = 756
TEAL_OGERPON = 96
WELLSPRING = 108
FEZANDIPITI = 140
LATIAS = 184
CLEFAIRY = 272
PASSIMIAN = 978
MEOWTH = 1071
POKE_NAMES = {
    RAGING_BOLT: "RagingBolt", MEGA_KANG: "MegaKang", TEAL_OGERPON: "TealOgerpon",
    WELLSPRING: "Wellspring", FEZANDIPITI: "Fezandipiti", LATIAS: "Latias",
    CLEFAIRY: "Clefairy", PASSIMIAN: "Passimian", MEOWTH: "Meowth",
}


def target_id(opt, cur, me):
    """Return the card id of the Pokemon this OT_ATTACH targets, or None."""
    area, index = opt.get("inPlayArea"), opt.get("inPlayIndex")
    if area is None:
        area, index = opt.get("area"), opt.get("index")
    pl = (cur.get("players") or [])
    if me is None or me >= len(pl):
        return None
    mine = pl[me]
    if area == AREA_ACTIVE:
        a = (mine.get("active") or [None])[0]
        return (a or {}).get("id")
    if area == AREA_BENCH:
        try:
            b = (mine.get("bench") or [])[int(index or 0)]
            return (b or {}).get("id")
        except (IndexError, ValueError):
            return None
    return None


def basics_on(pk):
    """Count basic-energy attachments (cardType=5) on a Pokemon slot."""
    if not pk:
        return 0
    n = 0
    for e in pk.get("energies") or []:
        cid = (e or {}).get("id") if isinstance(e, dict) else e
        if CARDS.get(cid, {}).get("cardType") == 5:
            n += 1
    return n


def rb_state(cur, me):
    """Where is Raging Bolt right now (active/bench/absent), and how many
    basics attached?"""
    pl = (cur.get("players") or [])
    if me is None or me >= len(pl):
        return "absent", 0
    mine = pl[me]
    a = (mine.get("active") or [None])[0]
    if a and a.get("id") == RAGING_BOLT:
        return "active", basics_on(a)
    for b in mine.get("bench") or []:
        if b and b.get("id") == RAGING_BOLT:
            return "bench", basics_on(b)
    return "absent", 0


def walk_top10(dirs):
    """Yield (chosen_target_id, rb_location, rb_basics, offered_rb_attach) for
    every OT_ATTACH pick by a top-10 Kangaskhan side."""
    for d in dirs:
        for fp in sorted(Path(d).glob("*.json")):
            try:
                js = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            steps = js.get("steps") or []
            if len(steps) < 2:
                continue
            for seat in (0, 1):
                act0 = steps[1][seat].get("action")
                if not (isinstance(act0, list) and len(act0) == 60):
                    continue
                a = archetype(act0)
                if not a or a["label"] != KANG_LABEL:
                    continue
                for i in range(len(steps) - 1):
                    e = steps[i][seat]
                    if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                        continue
                    obs = e.get("observation") or {}
                    sel = obs.get("select") or {}
                    if sel.get("type") != 0:
                        continue
                    opts = sel.get("option") or []
                    act2 = steps[i + 1][seat].get("action")
                    if not (isinstance(act2, list) and len(act2) == 1):
                        continue
                    ci = act2[0]
                    if not (isinstance(ci, int) and ci < len(opts)):
                        continue
                    o = opts[ci] or {}
                    if o.get("type") != OT_ATTACH:
                        continue
                    cur = obs.get("current") or {}
                    me = cur.get("yourIndex") or 0
                    tid = target_id(o, cur, me)
                    loc, basics = rb_state(cur, me)
                    # was RB attach offered?
                    offered_rb = False
                    for oo in opts:
                        if (oo or {}).get("type") == OT_ATTACH and target_id(oo, cur, me) == RAGING_BOLT:
                            offered_rb = True
                            break
                    yield tid, loc, basics, offered_rb


def walk_ours(dirs):
    """Same but for our v1-alone piloting of Kangaskhan in crossdeck_kang.py
    output (KANG is on _our_seat)."""
    for d in dirs:
        for fp in sorted(Path(d).glob("g*.json")):
            try:
                js = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            steps = js.get("steps") or []
            if len(steps) < 2:
                continue
            our_seat = js.get("_our_seat", 0)
            for i in range(len(steps) - 1):
                e = steps[i][our_seat]
                if not isinstance(e, dict) or e.get("status") != "ACTIVE":
                    continue
                obs = e.get("observation") or {}
                sel = obs.get("select") or {}
                if sel.get("type") != 0:
                    continue
                opts = sel.get("option") or []
                act2 = steps[i + 1][our_seat].get("action")
                if not (isinstance(act2, list) and len(act2) == 1):
                    continue
                ci = act2[0]
                if not (isinstance(ci, int) and ci < len(opts)):
                    continue
                o = opts[ci] or {}
                if o.get("type") != OT_ATTACH:
                    continue
                cur = obs.get("current") or {}
                me = cur.get("yourIndex") or 0
                tid = target_id(o, cur, me)
                loc, basics = rb_state(cur, me)
                offered_rb = False
                for oo in opts:
                    if (oo or {}).get("type") == OT_ATTACH and target_id(oo, cur, me) == RAGING_BOLT:
                        offered_rb = True
                        break
                yield tid, loc, basics, offered_rb


def summarize(label, rows):
    n = 0
    target_hist = Counter()
    rb_offered = rb_offered_not_picked = 0
    rb_basics_hist_when_picked = defaultdict(int)
    for tid, loc, basics, offered in rows:
        n += 1
        target_hist[tid] += 1
        if offered:
            rb_offered += 1
            if tid != RAGING_BOLT:
                rb_offered_not_picked += 1
        if tid == RAGING_BOLT:
            rb_basics_hist_when_picked[basics] += 1
    print(f"\n== {label} — total OT_ATTACH picks: {n}")
    for cid, cnt in target_hist.most_common():
        name = POKE_NAMES.get(cid, f"?({cid})")
        print(f"  {name:15s}  {cnt:4d}  ({cnt/max(1,n)*100:.1f}%)")
    print(f"  RB attach OFFERED: {rb_offered}  ({rb_offered/max(1,n)*100:.1f}% of attach picks)")
    print(f"  RB attach OFFERED but SKIPPED: {rb_offered_not_picked}  "
          f"({rb_offered_not_picked/max(1,rb_offered)*100:.1f}% of offers)")
    print(f"  RB basics-at-time-of-attach histogram (when RB was the pick): {dict(rb_basics_hist_when_picked)}")
    return n, target_hist, rb_offered, rb_offered_not_picked


if __name__ == "__main__":
    A = REPO / "analysis/phase2_meta_shift"
    top_dirs = [A / "replays_top10_jul26", A / "replays_top10_jul31"]
    our_dirs = [REPO / "scratchpad/s3/cdk_grimmsnarl_none",
                REPO / "scratchpad/s3/cdk_grimmsnarl_ke1"]
    print("Mining top-10 Kang attach targets from:", [str(d.name) for d in top_dirs])
    summarize("top-10 pilots", walk_top10(top_dirs))
    print("\nMining our v1 attach targets from:", [str(d.name) for d in our_dirs])
    summarize("our v1", walk_ours(our_dirs))
