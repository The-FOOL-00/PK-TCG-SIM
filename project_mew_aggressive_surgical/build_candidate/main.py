"""Pokemon TCG AI Battle Challenge agent.
Production-Safe Aggressive-Surgical High-Elo Candidate.
"""
import os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from bot.aggressive_surgical_policy import select_aggressive_surgical_action
except Exception:
    def select_aggressive_surgical_action(obs, legal_actions):
        return legal_actions[0].get("index", 0) if legal_actions else 0

def agent(obs):
    """Main agent entry point."""
    try:
        legal_actions = obs.get("legal_actions", [])
        if not legal_actions:
            return 0
        return select_aggressive_surgical_action(obs, legal_actions)
    except Exception as err:
        sys.stderr.write(f"[AGENT_FALLBACK_ERROR]: {err}\n")
        legal = obs.get("legal_actions", [])
        return legal[0].get("index", 0) if legal else 0

if __name__ == "__main__":
    dummy = {"legal_actions": [{"type": "ATTACK", "index": 0}], "active_hp": 210}
    print("Production Smoke Test: returned action", agent(dummy))
