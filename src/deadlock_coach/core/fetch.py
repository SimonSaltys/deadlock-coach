from deadlock_coach.core.api import get_match_metadata
from deadlock_coach.core.assets import name_of

MARKS_S = [300, 600, 900, 1200, 1500, 1800]  # 5..30 min

STAT_FIELDS = [
    "net_worth", "gold_lane_creep", "gold_neutral_creep", "gold_treasure",
    "gold_death_loss", "gold_denied", "creep_kills", "possible_creeps",
    "player_damage", "player_damage_taken", "kills", "deaths", "assists",
    "shots_hit", "shots_missed", "level",
]

# Integer counts: use the last known value instead of interpolating
STEP_FIELDS = {"kills", "deaths", "assists", "level"}

# Shop items have upgrade_id == 1; abilities use 0 (unlock) or a large id (upgrade)
SHOP_ITEM_UPGRADE_ID = 1


def _interp(times: list[int], values: list[float], t: int) -> float | None:
    """Linear interpolation of a cumulative stat at time t. None if t is past the data."""
    if not times or t > times[-1]:
        return None
    if t <= times[0]:
        return values[0] * t / times[0]  # cumulative stats start at 0 at t=0
    for i in range(1, len(times)):
        if t <= times[i]:
            t0, t1 = times[i - 1], times[i]
            v0, v1 = values[i - 1], values[i]
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return None


def _step(times: list[int], values: list[float], t: int) -> float | None:
    """Last known value at or before time t. None if t is past the data."""
    if not times or t > times[-1]:
        return None
    last = 0
    for ti, v in zip(times, values):
        if ti > t:
            break
        last = v
    return last


def _stats_at_marks(stats: list[dict]) -> dict[int, dict]:
    times = [s["time_stamp_s"] for s in stats]
    out = {}
    for mark in MARKS_S:
        row = {}
        for f in STAT_FIELDS:
            values = [s[f] for s in stats]
            fn = _step if f in STEP_FIELDS else _interp
            row[f] = fn(times, values, mark)
        if row["net_worth"] is not None:
            out[mark] = row
    return out


def _split_purchases(items: list[dict]) -> tuple[list[dict], list[dict]]:
    shop, abilities = [], []
    for i in items:
        entry = {
            "t": i["game_time_s"],
            "id": i["item_id"],
            "upgrade_id": i["upgrade_id"],
        }
        if i["upgrade_id"] == SHOP_ITEM_UPGRADE_ID:
            entry["name"] = name_of("items", i["item_id"])
            entry["sold_t"] = i["sold_time_s"] or None
            shop.append(entry)
        else:
            entry["name"] = name_of("items", i["item_id"])
            abilities.append(entry)
    return shop, abilities


def _decode_path(path: dict, resolution: int) -> list[dict]:
    xs = path["x_max"] - path["x_min"]
    ys = path["y_max"] - path["y_min"]
    return [
        {
            "t": i,
            "x": path["x_min"] + x / resolution * xs,
            "y": path["y_min"] + y / resolution * ys,
            "health": h,
        }
        for i, (x, y, h) in enumerate(zip(path["x_pos"], path["y_pos"], path["health"]))
    ]


def player_record(meta: dict, account_id: int) -> dict:
    info = meta["match_info"]
    me = next(p for p in info["players"] if p["account_id"] == account_id)
    mp = info["match_paths"]
    path = next(p for p in mp["paths"] if p["player_slot"] == me["player_slot"])
    shop_items, abilities = _split_purchases(me["items"])

    return {
        "match_id": info["match_id"],
        "account_id": account_id,
        "hero_id": me["hero_id"],
        "hero_name": name_of("heroes", me["hero_id"]),
        "team": me["team"],
        "won": me["team"] == info["winning_team"],
        "duration_s": info["duration_s"],
        "match_mode": info["match_mode"],
        "assigned_lane": me["assigned_lane"],
        "kills": me["kills"],
        "deaths": me["deaths"],
        "assists": me["assists"],
        "net_worth": me["net_worth"],
        "stats_at": _stats_at_marks(me["stats"]),
        "items": shop_items,
        "abilities": abilities,
        "deaths_detail": [
            {
                "t": d["game_time_s"],
                "x": d["death_pos"]["x"],
                "y": d["death_pos"]["y"],
                "ttk_s": d.get("time_to_kill_s"),
                "killer_slot": d["killer_player_slot"],
            }
            for d in me["death_details"]
        ],
        "path": _decode_path(path, mp["x_resolution"]),
    }


def fetch(match_id: int, account_id: int) -> dict:
    return player_record(get_match_metadata(match_id), account_id)


if __name__ == "__main__":
    import json
    import sys

    rec = fetch(int(sys.argv[1]), int(sys.argv[2]))
    rec["path"] = f"<{len(rec['path'])} points>"  # keep the print readable
    print(json.dumps(rec, indent=2))