"""Mine the daily episode datasets Kaggle publishes -> META.md snapshot.

Pipeline:
  1. Download the episodes-index manifest, pick the latest day (or --date).
  2. List that day's episode files, sample N of them (deterministic seed),
     download each (~3 MB apiece) into runs/kaggle_meta/episodes/.
  3. Parse each replay: team names, decks (the 60-card answers in
     steps[1][*].action), game length, first-attack turn, end reason.
  4. Join teams against the current leaderboard; "top" = leaderboard top 20.
  5. Cluster deck archetypes by their distinct Pokemon card-ID set and write
     META.md (weekly snapshot — commit it; episode JSONs stay gitignored).

Run:  python tools/meta_miner.py --sample 40
      python tools/meta_miner.py --date 2026-06-22 --sample 60 --keep-json
"""

import argparse
import collections
import csv
import io
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

COMP = "pokemon-tcg-ai-battle"
INDEX_DS = "kaggle/pokemon-tcg-ai-battle-episodes-index"
META_DIR = REPO / "runs" / "kaggle_meta"


def load_card_db():
    """Full card database from EN_Card_Data.csv (all ~1.3k ids, several rows
    per card — one per move). main.CARDS only holds OUR deck's 9 cards, so it
    cannot label opponent decks."""
    db = {}
    with open(REPO / "EN_Card_Data.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    stage_key = next(k for k in rows[0] if k.startswith("Stage"))
    for r in rows:
        cid = int(r["Card ID"])
        if cid in db:
            continue
        stage, rule = r[stage_key], r["Rule"]
        try:
            hp = int(r["HP"])
        except (ValueError, TypeError):
            hp = 0
        db[cid] = {
            "name": r["Card Name"],
            "is_pokemon": "Pok" in stage and "Tool" not in stage,
            "is_basic_energy": stage == "Basic Energy",
            "hp": hp,
            "ex": "ex" in rule,
            "mega": rule.startswith("Mega"),
        }
    return db


CARD_DB = load_card_db()


def kaggle_cmd(*args, timeout=600):
    out = subprocess.run([sys.executable, "-m", "kaggle", *args],
                         capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)} failed: {out.stderr[-400:]}")
    return out.stdout


def latest_day(date=None):
    META_DIR.mkdir(parents=True, exist_ok=True)
    kaggle_cmd("datasets", "download", INDEX_DS, "-p", str(META_DIR), "--unzip", "--force")
    rows = list(csv.DictReader(open(META_DIR / "manifest.csv", encoding="utf-8")))
    if date:
        rows = [r for r in rows if r["date"] == date]
        if not rows:
            raise SystemExit(f"date {date} not in manifest")
    row = sorted(rows, key=lambda r: r["date"])[-1]
    return row


def list_episode_files(slug, want):
    """First `want`*2 file names from the daily dataset (one API page is 200+)."""
    out = kaggle_cmd("datasets", "files", f"kaggle/{slug}",
                     "--page-size", str(max(100, want * 2)))
    names = re.findall(r"^(\d+\.json)\s", out, re.M)
    return names[: want * 2]


def download_episodes(slug, names, dest):
    dest.mkdir(parents=True, exist_ok=True)
    got = []
    for i, name in enumerate(names):
        fp = dest / name
        if not fp.exists():
            try:
                kaggle_cmd("datasets", "download", f"kaggle/{slug}",
                           "-f", name, "-p", str(dest), timeout=300)
                zp = dest / (name + ".zip")
                if zp.exists():  # single-file downloads are sometimes zipped
                    with zipfile.ZipFile(zp) as z:
                        z.extractall(dest)
                    zp.unlink()
            except Exception as e:
                print(f"  skip {name}: {e}", file=sys.stderr)
                continue
        if fp.exists():
            got.append(fp)
        if (i + 1) % 10 == 0:
            print(f"  downloaded {len(got)}/{i+1}", flush=True)
    return got


def parse_episode(fp):
    d = json.loads(fp.read_text(encoding="utf-8"))
    teams = (d.get("info") or {}).get("TeamNames") or ["?", "?"]
    steps = d.get("steps") or []
    decks = [None, None]
    if len(steps) > 1:
        for a in (0, 1):
            act = steps[1][a].get("action")
            if isinstance(act, list) and len(act) == 60:
                decks[a] = act
    vis = (steps[0][0].get("visualize")
           or (steps[0][0].get("observation") or {}).get("visualize")) or []
    reason, last_turn = None, 0
    first_attack = [None, None]
    for entry in vis:
        cur = entry.get("current") or {}
        last_turn = max(last_turn, cur.get("turn") or 0)
        for l in entry.get("logs") or []:
            t, pi = l.get("type"), l.get("playerIndex")
            if t == "Result":
                reason = l.get("reason")
            elif t == "Attack" and pi in (0, 1) and first_attack[pi] is None:
                first_attack[pi] = cur.get("turn")
    return {"episode": d.get("id") or fp.stem, "teams": teams,
            "rewards": d.get("rewards") or [None, None],
            "statuses": d.get("statuses") or ["?", "?"],
            "decks": decks, "turns": last_turn, "reason": reason,
            "first_attack": first_attack}


def leaderboard_scores():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        kaggle_cmd("competitions", "leaderboard", "-c", COMP, "--download", "-p", td)
        zips = list(Path(td).glob("*.zip"))
        if zips:
            with zipfile.ZipFile(zips[0]) as z:
                text = z.read(z.namelist()[0]).decode("utf-8", "replace").splitlines()
        else:
            text = list(Path(td).glob("*.csv"))[0].read_text(
                encoding="utf-8", errors="replace").splitlines()
    scores = {}
    for rec in csv.DictReader(text):
        team = rec.get("TeamName") or rec.get("teamName") or ""
        try:
            scores[team] = float(rec.get("Score") or rec.get("score") or 0)
        except ValueError:
            pass
    return scores


def archetype(deck):
    """Deck -> (label, pokemon-id signature, energy count)."""
    if not deck:
        return None
    counts = collections.Counter(deck)
    pokemon = sorted({cid for cid in deck
                      if CARD_DB.get(cid, {}).get("is_pokemon")})
    energy = sum(n for cid, n in counts.items()
                 if CARD_DB.get(cid, {}).get("is_basic_energy"))
    # label by the headline attackers (mega/ex first, else highest HP)
    def key(cid):
        c = CARD_DB.get(cid, {})
        return (c.get("mega", False), c.get("ex", False), c.get("hp") or 0)
    head = sorted(pokemon, key=key, reverse=True)[:2]
    label = " / ".join(CARD_DB.get(cid, {}).get("name") or str(cid)
                       for cid in head) or "unknown"
    return {"label": label, "signature": tuple(pokemon), "energy": energy}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: latest)")
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--top-n", type=int, default=20, help="leaderboard 'top' cutoff")
    ap.add_argument("--out", default="META.md")
    args = ap.parse_args()

    day = latest_day(args.date)
    slug = day["daily_dataset_slug"]
    print(f"day {day['date']}: {day['episode_count']} episodes, "
          f"top_avg {float(day['top_avg_score']):.0f}, "
          f"median {float(day['median_avg_score']):.0f}", flush=True)

    names = list_episode_files(slug, args.sample)[: args.sample]
    print(f"downloading {len(names)} episode files...", flush=True)
    files = download_episodes(slug, names, META_DIR / "episodes" / day["date"])
    episodes = []
    for fp in files:
        try:
            episodes.append(parse_episode(fp))
        except Exception as e:
            print(f"  parse fail {fp.name}: {e}", file=sys.stderr)
    print(f"parsed {len(episodes)} episodes", flush=True)

    lb = leaderboard_scores()
    ranked = sorted(lb.values(), reverse=True)
    top_cut = ranked[args.top_n - 1] if len(ranked) >= args.top_n else ranked[-1]

    # per-side records: (team, score, deck stats, won, ...)
    sides, arch_stats = [], collections.defaultdict(lambda: {
        "n": 0, "wins": 0, "scores": [], "energy": [], "sig": None})
    reasons = collections.Counter()
    turns_all, first_atk = [], []
    for ep in episodes:
        reasons[ep["reason"]] += 1
        turns_all.append(ep["turns"])
        for a in (0, 1):
            team = ep["teams"][a]
            score = lb.get(team)
            arch = archetype(ep["decks"][a])
            if ep["first_attack"][a] is not None:
                first_atk.append(ep["first_attack"][a])
            sides.append({"team": team, "score": score, "arch": arch,
                          "won": ep["rewards"][a] == 1,
                          "status": ep["statuses"][a]})
            if arch:
                st = arch_stats[arch["label"]]
                st["n"] += 1
                st["wins"] += 1 if ep["rewards"][a] == 1 else 0
                st["sig"] = arch["signature"]
                st["energy"].append(arch["energy"])
                if score is not None:
                    st["scores"].append(score)

    top_sides = [s for s in sides if s["score"] is not None and s["score"] >= top_cut]
    top_archs = collections.Counter(s["arch"]["label"] for s in top_sides if s["arch"])

    lines = [
        f"# Ladder meta snapshot — episodes of {day['date']} "
        f"(generated {time.strftime('%Y-%m-%d')})",
        "",
        f"Sample: {len(episodes)} episodes ({len(sides)} deck-sides) of "
        f"{day['episode_count']} that day. Leaderboard: {len(lb)} teams, "
        f"top {ranked[0]:.0f}, top-{args.top_n} cutoff {top_cut:.0f}, "
        f"median {sorted(ranked)[len(ranked)//2]:.0f}.",
        "",
        "## Field stats (whole sample)",
        "",
        f"- avg game length: {sum(turns_all)/max(1,len(turns_all)):.1f} turns"
        f" (min {min(turns_all or [0])}, max {max(turns_all or [0])})",
        f"- avg first-attack turn: "
        f"{sum(first_atk)/max(1,len(first_atk)):.1f}",
        f"- end reasons: "
        + ", ".join(f"{k}={v}" for k, v in reasons.most_common())
        + "  (1=prizes 2=deckout 3=no-active 4=effect)",
        f"- sides with bad status (INVALID/ERROR/TIMEOUT): "
        f"{sum(1 for s in sides if s['status'] in ('INVALID','ERROR','TIMEOUT'))}",
        "",
        "## Deck archetypes in the sample",
        "",
        "| archetype | sides | win rate | avg lb score | avg basic energy |",
        "|---|---|---|---|---|",
    ]
    for label, st in sorted(arch_stats.items(), key=lambda kv: -kv[1]["n"]):
        avg_score = (sum(st["scores"]) / len(st["scores"])) if st["scores"] else None
        lines.append(
            f"| {label} | {st['n']} | {st['wins']/st['n']*100:.0f}% | "
            f"{avg_score:.0f}" if avg_score is not None else
            f"| {label} | {st['n']} | {st['wins']/st['n']*100:.0f}% | ?"
        )
        lines[-1] += f" | {sum(st['energy'])/len(st['energy']):.0f} |"
    lines += [
        "",
        f"## Top-{args.top_n} team sides in the sample ({len(top_sides)})",
        "",
    ]
    if top_archs:
        for label, n in top_archs.most_common():
            lines.append(f"- {label}: {n} side(s)")
    else:
        lines.append("- none in this sample; increase --sample")
    lines += ["", "_Raw episode JSONs under runs/kaggle_meta/episodes/ "
              "(gitignored). Regenerate weekly._", ""]
    Path(REPO / args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
