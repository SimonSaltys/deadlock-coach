import json
from pathlib import Path

from deadlock_coach.core.fetch import player_record

FIXTURE = Path(__file__).parent / "fixtures" / "match_126343994.json"
ACCOUNT_ID = 190481303


def load_record():
    meta = json.loads(FIXTURE.read_text())
    return player_record(meta, ACCOUNT_ID)

def test_names_resolved():
    rec = load_record()
    assert rec["hero_name"] == "Drifter"
    assert not any(i["name"].startswith("unknown_") for i in rec["items"] + rec["abilities"])

def test_basic_fields():
    rec = load_record()
    assert rec["won"] is True
    assert rec["hero_id"] == 64
    assert (rec["kills"], rec["deaths"], rec["assists"]) == (7, 7, 18)


def test_deaths_at_marks_match_death_events():
    rec = load_record()
    death_times = [d["t"] for d in rec["deaths_detail"]]
    for mark, row in rec["stats_at"].items():
        expected = sum(1 for t in death_times if t <= int(mark))
        assert row["deaths"] == expected


def test_items_and_abilities_split():
    rec = load_record()
    assert all(i["upgrade_id"] == 1 for i in rec["items"])
    assert len({a["id"] for a in rec["abilities"]}) == 4


def test_path_covers_match():
    rec = load_record()
    assert len(rec["path"]) >= rec["duration_s"]