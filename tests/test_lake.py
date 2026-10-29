from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from deadlock_coach.core import lake

pytestmark = pytest.mark.network

SINCE = datetime(2026, 10, 27, 12, tzinfo=UTC)
UNTIL = SINCE + timedelta(hours=1)


@pytest.fixture(scope="module")
def con():
    try:
        c = lake.connect(Path(":memory:"))
    except duckdb.Error as e:
        pytest.skip(f"lake catalog unreachable: {e}")
    yield c
    c.close()


def test_data_files_are_remote_urls(con):
    files = lake.data_files(con, "match_player")
    assert files
    assert all(f.startswith("https://") and f.endswith(".parquet") for f in files)


def test_time_window_prunes_files(con):
    all_files = lake.data_files(con, "match_player")
    window = lake.data_files(con, "match_player", SINCE, UNTIL)
    assert 0 < len(window) < len(all_files)
    assert set(window) <= set(all_files)


def test_unknown_table(con):
    with pytest.raises(ValueError):
        lake.data_files(con, "no_such_table")


def test_match_player_window_is_deduped(con):
    rel = lake.match_player(con, SINCE, UNTIL, ["match_id", "account_id", "start_time"])
    rows, unique, too_early, too_late = rel.aggregate(
        "count(*), count(DISTINCT (match_id, account_id)),"
        f" count(*) FILTER (WHERE start_time < '{SINCE.isoformat()}'),"
        f" count(*) FILTER (WHERE start_time >= '{UNTIL.isoformat()}')"
    ).fetchall()[0]
    assert rows > 0
    assert rows == unique
    assert too_early == too_late == 0
