"""Generate the media-gallery figures for the Strategy-track writeup.

Every number here is transcribed from report/WRITEUP_SUBMIT.md / WRITEUP_FULL.md;
the source section is named in the comment above each block. Nothing is computed
or re-derived -- if a figure and the report disagree, the report is authoritative
and this file has drifted.

Usage:  python tools/make_writeup_figures.py [outdir]
Output: report/figures/fig{1..4}_*.png  (1600px wide, light surface)
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# --- palette (dataviz skill reference instance, light mode) ------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
S1 = "#2a78d6"  # slot 1 blue
S2 = "#eb6834"  # slot 2 orange
S3 = "#1baf7a"  # slot 3 aqua

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "sans-serif"],
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 1.0,
        "figure.dpi": 200,
    }
)


def _frame(ax, xgrid=False):
    """Recessive chrome: hairline grid on the value axis only, two spines gone."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="x" if xgrid else "y", color=GRID, linewidth=1.0)
    ax.tick_params(length=0, labelsize=10)


def _titles(fig, title, subtitle):
    fig.text(0.012, 0.975, title, ha="left", va="top", fontsize=16, weight="bold", color=INK)
    fig.text(0.012, 0.916, subtitle, ha="left", va="top", fontsize=10.5, color=INK_2)


def _footer(fig, text):
    fig.text(0.012, 0.022, text, ha="left", va="bottom", fontsize=8.5, color=MUTED)


# =============================================================================
# Fig 1 -- envelope closure, seven archetypes.  Source: WRITEUP_SUBMIT.md sec 3
# closure = our mirror prize velocity / that archetype's top-10 velocity.
# `alt_harness` marks the two decks measured on the second harness (footnote a):
# ranking transfers, absolute values are not directly comparable to the rest.
# =============================================================================
CLOSURE = [
    # (deck, attacker online via, velocity, envelope, closure %, one_step, alt_harness)
    ("Teal Mask Ogerpon ex", "Basic, no evolution", 0.4726, 0.5845, 80.9, True, True),
    ("Marnie's Grimmsnarl ex", "Stage-2 + Rare Candy", 0.4574, 0.5725, 79.9, True, False),
    ("Cynthia's Garchomp", "Stage-2, no Rare Candy", 0.2628, 0.4950, 53.1, False, False),
    ("TR Mewtwo / Spidops", "Basic, stall plan", 0.3303, 0.6754, 48.9, False, False),
    ("Dragapult ex / Munkidori", "Stage-2, no Rare Candy", 0.2324, 0.5021, 46.3, False, True),
    ("Mega Kangaskhan / Raging Bolt", "Basic + Mega evolution", 0.3025, 0.6729, 45.0, False, False),
    ("Fezandipiti / Dudunsparce", "Stage-1 engine", 0.2061, 0.5084, 40.5, False, False),
]


def fig1(outdir):
    rows = sorted(CLOSURE, key=lambda r: r[4])  # ascending -> best at top
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    fig.subplots_adjust(left=0.30, right=0.975, top=0.80, bottom=0.14)

    ypos = range(len(rows))
    for y, (deck, via, _vel, _env, closure, one_step, alt) in zip(ypos, rows):
        color = S1 if one_step else S2
        ax.barh(
            y,
            closure,
            height=0.62,
            color=color,
            hatch="///" if alt else None,
            edgecolor=SURFACE,
            linewidth=1.0,
        )
        ax.text(closure + 1.2, y, f"{closure:.1f}%", va="center", ha="left", fontsize=10.5,
                color=INK, weight="bold")

    ax.set_yticks(list(ypos))
    ax.set_yticklabels(
        [f"{r[0]}\n{r[1]}" for r in rows],
        fontsize=9.5,
        color=INK,
        linespacing=1.45,
    )
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 20, 40, 60, 80])
    ax.set_xlabel("closure  =  our prize velocity  /  that archetype's top-10 velocity", fontsize=10)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    _frame(ax, xgrid=True)

    # the empty 53–80 gap is the finding: two bands, nothing between them
    ax.axhspan(4.5, 6.5, color=S1, alpha=0.05, zorder=0)
    ax.text(96, 5.5, "79–81%", fontsize=10, color=S1, ha="left", va="center", weight="bold")
    ax.text(96, 2.0, "40–53%", fontsize=10, color=S2, ha="left", va="center", weight="bold")
    ax.annotate("", xy=(93, 4.5), xytext=(93, 6.5),
                arrowprops=dict(arrowstyle="-", color=S1, linewidth=1.6))
    ax.annotate("", xy=(93, -0.4), xytext=(93, 4.4),
                arrowprops=dict(arrowstyle="-", color=S2, linewidth=1.6))

    ax.legend(
        handles=[
            Patch(facecolor=S1, label="one-step attacker (Basic, or Stage-2 collapsed by Rare Candy)"),
            Patch(facecolor=S2, label="attacker needs a genuine multi-turn climb"),
            Patch(facecolor="white", edgecolor=MUTED, hatch="///", label="second harness (ranking transfers, absolutes not comparable)"),
        ],
        loc="upper left",
        bbox_to_anchor=(-0.42, -0.14),
        frameon=False,
        fontsize=8.8,
        handlelength=1.4,
        handleheight=0.9,
        labelcolor=INK_2,
    )

    _titles(
        fig,
        "Closure tracks how many turns the attacker needs — not deck strength",
        "Same agent, same flags, only deck.csv differs. 100 games / 200 sides per deck.",
    )
    fig.savefig(outdir / "fig1_envelope_closure.png", bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)


# =============================================================================
# Fig 2 -- every offline proxy we trusted.  Source: WRITEUP_SUBMIT.md sec 1
# The proxies are in different units (AUC, top-1 acc, context acc, tuned win
# rate); they share only the property of being the number we read BEFORE the
# head-to-head. That is the point of the figure, and the unit is named per row.
# =============================================================================
PROXIES = [
    # (intervention, proxy name, proxy value, h2h, ci_lo, ci_hi, verdict)
    ("BC + anti-deckout brake", "context accuracy", 96.8, 39.0, 33.7, 44.6, "KILL"),
    ("Behaviour cloning, MAIN-only", "top-1 accuracy (floor 20.8)", 69.4, 31.0, 26.0, 36.4, "KILL"),
    ("Learned value net, 1.52M rows", "validation AUC", 84.5, 48.7, 43.1, 54.3, "KILL"),
    ("Behaviour cloning, two-headed", "sub-decision accuracy", 76.1, 60.7, 55.0, 66.0, "SHIP"),
    ("Analytic 1-ply evaluator", "hill-climbed win rate", 53.0, 54.0, 48.3, 59.6, "KILL"),
]


def fig2(outdir):
    rows = sorted(PROXIES, key=lambda r: r[2] - r[3])  # smallest gap at bottom
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    fig.subplots_adjust(left=0.34, right=0.90, top=0.80, bottom=0.16)

    for y, (name, unit, proxy, h2h, lo, hi, verdict) in enumerate(rows):
        ax.plot([h2h, proxy], [y, y], color=AXIS, linewidth=2.0, zorder=1,
                solid_capstyle="round")
        ax.plot([lo, hi], [y, y], color=S2, linewidth=5.0, alpha=0.22, zorder=2,
                solid_capstyle="round")
        ax.scatter([proxy], [y], s=90, color=S1, zorder=3, edgecolor=SURFACE, linewidth=1.5)
        ax.scatter([h2h], [y], s=90, color=S2, zorder=4, edgecolor=SURFACE, linewidth=1.5)
        if abs(proxy - h2h) < 8:
            # near-coincident dots: stack the labels instead of colliding them
            ax.text(proxy, y - 0.30, f"{proxy:.1f}", va="top", ha="center",
                    fontsize=9.5, color=S1, weight="bold")
            ax.text(h2h, y + 0.28, f"{h2h:.1f}%", va="bottom", ha="center",
                    fontsize=9.5, color=S2, weight="bold")
        else:
            ax.text(proxy + 1.8, y + 0.02, f"{proxy:.1f}", va="center", ha="left",
                    fontsize=9.5, color=S1, weight="bold")
            ax.text(h2h - 2.0, y + 0.02, f"{h2h:.1f}%", va="center", ha="right",
                    fontsize=9.5, color=S2, weight="bold")
        ax.text(109, y, verdict, va="center", ha="left", fontsize=9,
                color=(S3 if verdict == "SHIP" else INK_2),
                weight="bold" if verdict == "SHIP" else "normal")

    ax.axvline(50, color=INK_2, linewidth=1.2, linestyle=(0, (4, 3)), zorder=0)
    ax.text(50, len(rows) - 0.32, " 50% — parity with the incumbent", fontsize=9,
            color=INK_2, ha="left", va="bottom")

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{n}\n{u}" for n, u, *_ in rows], fontsize=9.5,
                       color=INK, linespacing=1.45)
    ax.set_xlim(20, 118)
    ax.set_xticks([20, 30, 40, 50, 60, 70, 80, 90, 100])
    ax.set_ylim(-0.7, len(rows) - 0.10)
    ax.set_xlabel("score  (offline proxies are in the unit named under each row)", fontsize=10)
    _frame(ax, xgrid=True)

    ax.legend(
        handles=[
            Line2D([], [], marker="o", linestyle="none", markersize=9, color=S1,
                   label="offline proxy — read before the match"),
            Line2D([], [], marker="o", linestyle="none", markersize=9, color=S2,
                   label="head-to-head win rate, n≥300, seats alternated"),
            Line2D([], [], linewidth=5, color=S2, alpha=0.22, label="95% Wilson CI"),
        ],
        loc="upper left",
        bbox_to_anchor=(-0.46, -0.15),
        frameon=False,
        fontsize=8.8,
        labelcolor=INK_2,
        handlelength=1.6,
    )

    _titles(
        fig,
        "Every offline proxy we trusted read excellent. Head-to-head read 31–61%.",
        "PASS requires the CI lower bound to clear 50%. One of five cleared it.",
    )
    fig.savefig(outdir / "fig2_offline_proxies_lie.png", bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)


# =============================================================================
# Fig 3 -- E1/E2 sequencing rules.  Source: WRITEUP_SUBMIT.md sec 6
# Before/after are the E1+E2 ablation pair; the field column is top-10 Grimmsnarl
# (504 sides, 19,323 decisions) on the identical 60 cards.
# =============================================================================
SEQ = [
    # (metric, top-10 field, ours before, ours after)
    ("Own turns where an\navailable Ability fired", 80.2, 59.5, 89.5),
    ("Own turns where ATTACK was\nthe first action taken", 2.0, 42.4, 0.1),
]


def fig3(outdir):
    fig, ax = plt.subplots(figsize=(7.6, 4.5))
    fig.subplots_adjust(left=0.20, right=0.97, top=0.78, bottom=0.26)

    width = 0.24
    for i, (metric, field, before, after) in enumerate(SEQ):
        for j, (val, color) in enumerate(((before, S2), (after, S3), (field, S1))):
            x = i + (j - 1) * (width + 0.02)
            ax.bar(x, val, width=width, color=color, edgecolor=SURFACE, linewidth=1.0)
            ax.text(x, val + 1.6, f"{val:.1f}%", ha="center", va="bottom",
                    fontsize=10, color=INK, weight="bold")

    ax.set_xticks(range(len(SEQ)))
    ax.set_xticklabels([m for m, *_ in SEQ], fontsize=10, color=INK, linespacing=1.5)
    ax.set_ylim(0, 100)
    ax.set_ylabel("share of own turns", fontsize=10)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    _frame(ax)

    ax.legend(
        handles=[
            Patch(facecolor=S2, label="ours, before E1/E2"),
            Patch(facecolor=S3, label="ours, after E1/E2"),
            Patch(facecolor=S1, label="top-10 field, identical 60 cards"),
        ],
        loc="upper left",
        bbox_to_anchor=(0.0, -0.17),
        ncol=3,
        frameon=False,
        fontsize=9,
        handlelength=1.4,
        handleheight=0.9,
        labelcolor=INK_2,
    )

    _titles(
        fig,
        "Attacking ends the turn. Every other action is free.",
        "WEIGHT_LETHAL = 100 000 ended the turn the instant a KO appeared, cards unplayed.\n"
        "E1 (develop before a terminal action) + E2 (fire an available Ability first) close both gaps.",
    )
    _footer(fig, "Mirror self-play scored these rules as null — a mirror is blind to a strictly-dominated fix. "
                 "On ladder they moved prize velocity +0.0853, against a 0.019–0.025 noise band.")
    fig.savefig(outdir / "fig3_sequencing_parity.png", bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)


# =============================================================================
# Fig 4 -- the trap: high envelope, low closure.  Source: WRITEUP_SUBMIT.md sec 3
# =============================================================================
def fig4(outdir):
    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    fig.subplots_adjust(left=0.11, right=0.97, top=0.79, bottom=0.13)

    # label offsets tuned by eye against the rendered PNG (step 7 of the procedure)
    offsets = {
        "Teal Mask Ogerpon ex": (12, 6, "left"),
        "Marnie's Grimmsnarl ex": (-12, -4, "right"),
        "Cynthia's Garchomp": (0, 14, "center"),
        "TR Mewtwo / Spidops": (-13, 3, "right"),
        "Dragapult ex / Munkidori": (13, 0, "left"),
        "Mega Kangaskhan / Raging Bolt": (0, -20, "center"),
        "Fezandipiti / Dudunsparce": (13, 0, "left"),
    }
    for deck, _via, _vel, envelope, closure, one_step, alt in CLOSURE:
        color = S1 if one_step else S2
        ax.scatter([envelope], [closure], s=150, color=color, zorder=3,
                   edgecolor=SURFACE, linewidth=1.8)
        dx, dy, ha = offsets[deck]
        ax.annotate(deck, (envelope, closure), textcoords="offset points",
                    xytext=(dx, dy), ha=ha, va="center", fontsize=9, color=INK)

    ax.set_xlim(0.46, 0.73)
    ax.set_ylim(28, 92)
    ax.set_yticks([30, 40, 50, 60, 70, 80, 90])
    ax.set_xlabel("envelope — what top-10 pilots extract from this deck (prize velocity)", fontsize=10)
    ax.set_ylabel("closure — the share of that we convert", fontsize=10)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    _frame(ax)
    ax.grid(axis="x", color=GRID, linewidth=1.0)

    # caption sits directly under the trap corner; proximity beats an arrow that
    # would have to cross the two labels to get there
    ax.text(0.672, 33.8, "↑  picking a deck by field strength\nselects exactly this corner",
            fontsize=9.5, color=INK_2, ha="center", va="center", linespacing=1.5)

    ax.legend(
        handles=[
            Patch(facecolor=S1, label="one-step attacker"),
            Patch(facecolor=S2, label="multi-turn climb"),
        ],
        loc="upper left", frameon=False, fontsize=9,
        handlelength=1.4, handleheight=0.9, labelcolor=INK_2,
    )

    _titles(
        fig,
        "The trap: the two highest envelopes we measured are the two we convert worst",
        "Dragapult ex is the current meta's best archetype (76.5% pooled, 10–2 vs Grimmsnarl).\n"
        "We close 46.3% of it — adopting it would lower our rating.",
    )
    fig.savefig(outdir / "fig4_envelope_trap.png", bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)


def main():
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "report" / "figures"
    outdir.mkdir(parents=True, exist_ok=True)
    fig1(outdir)
    fig2(outdir)
    fig3(outdir)
    fig4(outdir)
    for p in sorted(outdir.glob("fig*.png")):
        print(f"{p.name}  {p.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
