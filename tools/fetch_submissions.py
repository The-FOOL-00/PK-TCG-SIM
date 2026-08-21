"""Kaggle Submissions and Leaderboard Fetcher for Project Mew.

Fetches live Kaggle competition submissions and leaderboard statistics
using Kaggle API authentication.
"""

import sys
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path

COMPETITION = "pokemon-tcg-ai-battle"
KAGGLE_DIR = Path.home() / ".kaggle"


def get_auth_header():
    """Gets Authorization header from credentials.json (OAuth) or kaggle.json (Basic)."""
    # 1. Try credentials.json OAuth access token
    cred_path = KAGGLE_DIR / "credentials.json"
    if cred_path.exists():
        try:
            data = json.loads(cred_path.read_text(encoding="utf-8"))
            token = data.get("access_token")
            if token:
                return {"Authorization": f"Bearer {token}"}
        except Exception:
            pass

    # 2. Try kaggle.json Basic auth
    kj_path = KAGGLE_DIR / "kaggle.json"
    if kj_path.exists():
        try:
            data = json.loads(kj_path.read_text(encoding="utf-8"))
            user = data.get("username")
            key = data.get("key")
            if user and key:
                user_key = f"{user}:{key}".encode("utf-8")
                b64 = base64.b64encode(user_key).decode("ascii")
                return {"Authorization": f"Basic {b64}"}
        except Exception:
            pass

    return {}


def fetch_submissions():
    headers = get_auth_header()
    if not headers:
        print("Error: No Kaggle API credentials found in ~/.kaggle/")
        return []

    url = f"https://www.kaggle.com/api/v1/competitions/submissions/list/{COMPETITION}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        if e.code == 401:
            print("OAuth token may be expired. Refresh by running: py -3.12 -m kaggle auth login")
        return []
    except Exception as e:
        print(f"Failed to fetch submissions: {e}")
        return []


def fetch_leaderboard():
    headers = get_auth_header()
    if not headers:
        return []

    url = f"https://www.kaggle.com/api/v1/competitions/leaderboard/view/{COMPETITION}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except Exception as e:
        print(f"Failed to fetch leaderboard: {e}")
        return []


def main():
    print(f"=== Project Mew - Kaggle Ladder Monitor ({COMPETITION}) ===")
    subs = fetch_submissions()
    if subs:
        print(f"\nSubmissions ({len(subs)} total):")
        for s in subs[:10]:
            ref = s.get("ref", s.get("id", "?"))
            fname = s.get("fileName", s.get("description", "?"))
            status = s.get("status", s.get("submissionStatus", "?"))
            score = s.get("publicScore", s.get("score", "N/A"))
            date = s.get("date", s.get("submittedDate", "?"))
            print(f"  ID: {ref:<10} Date: {date[:19]}  Status: {status:<15} Score/Elo: {score}")

    lb = fetch_leaderboard()
    if lb and isinstance(lb, dict) and "teams" in lb:
        teams = lb.get("teams", [])
        print(f"\nLeaderboard Overview ({len(teams)} teams):")
        for t in teams[:5]:
            rank = t.get("rank")
            team_name = t.get("teamName")
            score = t.get("score")
            print(f"  Rank #{rank:<4} {team_name:<30} Score: {score}")


if __name__ == "__main__":
    main()
