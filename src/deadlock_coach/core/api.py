import requests

BASE_URL = "https://api.deadlock-api.com"
session = requests.Session()
session.headers["User-Agent"] = "deadlock-coach (github.com/SimonSaltys/deadlock-coach)"


def get_match_history(account_id: int) -> list[dict]:
    r = session.get(f"{BASE_URL}/v1/players/{account_id}/match-history", timeout=30)
    r.raise_for_status()
    return r.json()


def get_match_metadata(match_id: int) -> dict:
    r = session.get(f"{BASE_URL}/v1/matches/{match_id}/metadata", timeout=30)
    r.raise_for_status()
    return r.json()