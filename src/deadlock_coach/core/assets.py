import json
from functools import cache
from pathlib import Path

import requests

ASSETS_URL = "https://api.deadlock-api.com"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = PROJECT_ROOT / "data" / "assets"

ENDPOINTS = {
    "heroes": "/v1/assets/heroes",
    "items": "/v1/assets/items",  # shop items and abilities together
}


def _load(name: str, refresh: bool = False) -> list[dict]:
    """Load an asset list from the local cache, fetching it if missing."""
    path = CACHE_DIR / f"{name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    r = requests.get(ASSETS_URL + ENDPOINTS[name], timeout=30)
    r.raise_for_status()
    data = r.json()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


@cache
def lookup(name: str) -> dict[int, dict]:
    """id -> asset dict for heroes or items."""
    return {a["id"]: a for a in _load(name)}


def refresh_all() -> None:
    """Re-download all assets. Run after a patch."""
    for name in ENDPOINTS:
        _load(name, refresh=True)
    lookup.cache_clear()


def name_of(kind: str, asset_id: int) -> str:
    try:
        asset = lookup(kind).get(asset_id)
    except requests.RequestException:
        return f"unknown_{asset_id}"
    return asset["name"] if asset else f"unknown_{asset_id}"