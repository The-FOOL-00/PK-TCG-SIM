"""nproc fork-gate configs + kill criteria (binding sign-off amendments).

The core count on lab arrival is a FORK GATE, not a tunable: it selects one of
three pre-registered configs. Do not hand-edit these at the lab — the whole
point is that the config was fixed before we saw the hardware.
"""

from . import train

# ---- kill criteria (driver-enforced; see algorithm_survey.md §9 + amendments)
KILL = {
    "validation_regress": (
        "training winrate-vs-anchor at 10k games < starting value "
        "=> STOP, rediagnose (the Sanjay 34->5% pattern check)"),
    "K1_collapse": (
        "two consecutive 200-game gates < 29% vs v2.2.0 "
        "=> halt, revert to prior checkpoint, diagnose (~2 lab-days)"),
    "K2_plateau": (
        "no gate >= 44% by 150k games or >= 48% by 300k "
        "=> capacity growth 27.8k->128k->256k FIRST; Gumbel-AZ only after "
        "both widths plateau"),
    "K2_diagnostic": (
        "train reward ~p90 of small-net-achievable but gates < 44% "
        "=> capacity-limited (grow net), NOT plateau (algorithm pivot)"),
    "K3_retry": "one KL-halving retry only, if K2 fires with KL pinned",
    "leakage": "any leakage-audit fail => immediate STOP, no training",
    "nproc_nogo": (
        "combined sustained throughput < 1500 games/h (~36k/day) "
        "=> NO-GO on RL; ride v2.2.0 (BC-v2 @ 39% is not shippable)"),
}


def _cfg(**over):
    c = dict(train.DEFAULT_CFG)
    c.update(over)
    return c


# ≥16 cores: central config — full K2 headroom, target ≥300k games.
CENTRAL = _cfg(
    games_per_iter=480, workers=16, kl_coef=0.5, ent_coef=0.003,
    incumbent_final=0.35, incumbent_ramp_iters=60,
    shaping_prize=0.0, shaping_deck=0.0)

# 8–16 cores: reduced — games-per-iter halved to keep update cadence, no
# re-run slack (one restart consumes the margin).
REDUCED = _cfg(
    games_per_iter=240, workers=10, kl_coef=0.5, ent_coef=0.003,
    incumbent_final=0.35, incumbent_ramp_iters=60,
    shaping_prize=0.0, shaping_deck=0.0)

# <8 cores: Colab-scale — supplement the home box, explicit go/no-go. The
# driver must confirm combined throughput ≥ 1500 games/h before committing.
COLAB = _cfg(
    games_per_iter=96, workers=4, kl_coef=0.5, ent_coef=0.003,
    incumbent_final=0.30, incumbent_ramp_iters=50,
    shaping_prize=0.0, shaping_deck=0.0)


def select(n_cores):
    """(name, cfg, go_no_go) for the fork gate. go_no_go True means launch
    is pre-authorized; False (Colab tier) means STOP and escalate to user."""
    if n_cores >= 16:
        return "central", dict(CENTRAL), True
    if n_cores >= 8:
        return "reduced", dict(REDUCED), True
    return "colab", dict(COLAB), False
