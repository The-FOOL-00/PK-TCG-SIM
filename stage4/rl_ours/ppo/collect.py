"""Play real cabt games and capture decision points for tests/audits.

Returns a list of records, one per MAIN/ST_CARD decision the learner seat
faced, carrying the frozen observation plus the encoded (state, rows). This
is the exact surface the PPO rollout worker will train on, so bit-match and
leakage audit both run on the true training path.
"""

import contextlib
import io
import json

from . import common


class _Recorder:
    def __init__(self, deck, attrs, defaults, seat, sink, cap):
        self.deck, self.attrs, self.defaults = deck, attrs, defaults
        self.seat, self.sink, self.cap = seat, sink, cap

    def __call__(self, obs, _config=None):
        if obs.get("select") is None:
            return list(self.deck)
        common.apply_attrs(self.deck, self.attrs, self.defaults)
        sel = obs.get("select") or {}
        cur = obs.get("current") or {}
        if (cur.get("yourIndex") == self.seat and len(self.sink) < self.cap):
            kind = common.decision_kind(sel)
            if kind is not None:
                # deep-copy the observation so later engine mutation can't
                # alias our captured state
                frozen = json.loads(json.dumps(obs))
                self.sink.append((kind, frozen["select"], frozen["current"]))
        return common.agent_mod.agent(obs)


def collect_decisions(n_games=40, cap=4000, learner_spec=None,
                      opp_spec=None, seed=0):
    """List of (kind, sel, cur) for the learner seat across n_games.

    Both sides default to the learner spec (BC-v2 self-play) so captured
    states reflect the on-policy distribution training will see.
    """
    learner_spec = learner_spec or common.LEARNER_SPEC
    opp_spec = opp_spec or common.LEARNER_SPEC
    ld, la = common.parse_spec(learner_spec)
    od, oa = common.parse_spec(opp_spec)
    defaults = common.collect_defaults(la, oa)
    sink = []
    for g in range(n_games):
        seat = g % 2
        rec = _Recorder(ld, la, defaults, seat, sink, cap)
        opp = common.make_league_wrapper(opp_spec, defaults)
        wrappers = [None, None]
        wrappers[seat] = rec
        wrappers[1 - seat] = opp
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            env = common.make_env()
            env.run(wrappers)
        if len(sink) >= cap:
            break
    return sink
