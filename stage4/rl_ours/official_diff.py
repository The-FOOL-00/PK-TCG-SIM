"""Diff the official EN_Card_Data.csv against card_data.json skills[]/attacks[]
for every card referenced by R1/R2/R3 and the SEQ ordering gates."""
import csv
import io
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CD = json.loads((REPO / "card_data.json").read_text(encoding="utf-8"))
CARDS = {int(k): v for k, v in CD["cards"].items()}
ATT = {int(k): v for k, v in CD["attacks"].items()}

# card id -> (label, which rule references it)
TARGETS = {
    380: ("Cynthia's Gabite / Champion's Call", "R1 (_is_search_ability)"),
    342: ("Cynthia's Roserade / Cheer On to Glory", "R5 proposed / Phase 2 note"),
    387: ("Cynthia's Spiritomb / Raging Curse", "R3 (_attack_damage_est)"),
    1173: ("Cynthia's Power Weight", "STEP 0 §5"),
    381: ("Cynthia's Garchomp ex", "R2 (_can_evolve_further), STEP 0"),
    379: ("Cynthia's Gible", "R2"),
    341: ("Cynthia's Roselia", "R2"),
    # SEQ gates are card-agnostic, but these are the Grimmsnarl bodies whose
    # printed damage drives can_ko / ko_able in E1c and E3.
    648: ("Marnie's Grimmsnarl ex / Shadow Bullet", "E1c/E3 threat proxy"),
    647: ("Marnie's Morgrem", "E1c/E3 threat proxy"),
    646: ("Marnie's Impidimp", "E1c/E3 threat proxy"),
    112: ("Munkidori", "E2 rationale (damage-shift ability)"),
    104: ("Froslass", "E1c/E3 threat proxy"),
    860: ("Snorunt", "E1c/E3 threat proxy"),
}


def norm(s):
    """Normalise for comparison: unify quotes/dashes, collapse whitespace."""
    if not s:
        return ""
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace("�", "?")          # mojibake placeholder in the CSV
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def load_csv():
    rows = {}
    with io.open(REPO / "EN_Card_Data.csv", encoding="utf-8-sig",
                 errors="replace", newline="") as f:
        for r in csv.DictReader(f):
            cid = (r.get("Card ID") or "").strip()
            if not cid.isdigit():
                continue
            rows.setdefault(int(cid), []).append(r)
    return rows


if __name__ == "__main__":
    csv_rows = load_csv()
    print("official CSV rows: %d cards with an id" % len(csv_rows))
    print("card_data.json cards: %d" % len(CARDS))
    print()
    diffs = 0
    for cid, (label, rule) in TARGETS.items():
        print("=" * 74)
        print("[%d] %s          <- %s" % (cid, label, rule))
        rows = csv_rows.get(cid)
        c = CARDS.get(cid)
        if not rows:
            print("   !! NOT IN OFFICIAL CSV")
            diffs += 1
            continue
        if not c:
            print("   !! NOT IN card_data.json")
            diffs += 1
            continue
        print("   name  CSV=%r  json=%r  %s"
              % (rows[0].get("Card Name"), c.get("name"),
                 "MATCH" if norm(rows[0].get("Card Name")) == norm(c.get("name"))
                 else "*** DIFFER ***"))
        # every move/ability row for this card in the CSV
        print("   --- official CSV rows (Move Name | Cost | Damage | Effect) ---")
        for r in rows:
            mn = (r.get("Move Name") or "").strip()
            if not mn or mn == "n/a":
                continue
            print("     %-24s | %-10s | %-6s | %s"
                  % (mn[:24], (r.get("Cost") or "")[:10],
                     (r.get("Damage") or "")[:6],
                     (r.get("Effect Explanation") or "").strip()[:150]))
        print("   --- card_data.json ---")
        for s in c.get("skills") or []:
            print("     SKILL  %-22s | %s"
                  % ((s.get("name") or "").strip()[:22],
                     (s.get("text") or "").strip()[:150]))
        for aid in c.get("attacks") or []:
            a = ATT.get(aid) or {}
            print("     ATTACK %-22s | dmg=%-5s | %s"
                  % ((a.get("name") or "")[:22], a.get("damage"),
                     (a.get("text") or "")[:150]))
        # ---- targeted text comparison ----
        csv_texts = [norm(r.get("Effect Explanation")) for r in rows
                     if (r.get("Effect Explanation") or "").strip()
                     and (r.get("Effect Explanation") or "").strip() != "n/a"]
        json_texts = [norm(s.get("text")) for s in (c.get("skills") or [])]
        json_texts += [norm((ATT.get(a) or {}).get("text"))
                       for a in (c.get("attacks") or [])]
        json_texts = [t for t in json_texts if t]
        missing = [t for t in json_texts
                   if t and not any(t in ct or ct in t for ct in csv_texts)]
        extra = [t for t in csv_texts
                 if t and not any(t in jt or jt in t for jt in json_texts)]
        if missing or extra:
            diffs += 1
            print("   *** TEXT DIFFERENCE ***")
            for t in missing:
                print("       in json, not matched in CSV: %s" % t[:130])
            for t in extra:
                print("       in CSV, not matched in json: %s" % t[:130])
        else:
            print("   TEXT: consistent")
        # damage cross-check
        for aid in c.get("attacks") or []:
            a = ATT.get(aid) or {}
            nm = norm(a.get("name"))
            for r in rows:
                if norm(r.get("Move Name")) == nm:
                    d = (r.get("Damage") or "").strip()
                    dj = a.get("damage")
                    dn = re.sub(r"[^0-9]", "", d)
                    if dn and int(dn) != int(dj or 0):
                        diffs += 1
                        print("   *** DAMAGE DIFFERS: %s CSV=%r json=%s"
                              % (a.get("name"), d, dj))
                    elif not dn and (dj or 0) != 0:
                        diffs += 1
                        print("   *** DAMAGE: CSV blank/non-numeric %r vs json %s"
                              % (d, dj))
    print()
    print("=" * 74)
    print("cards with a discrepancy: %d / %d" % (diffs, len(TARGETS)))
