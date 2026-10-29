from datetime import datetime
from pathlib import Path

import duckdb

LAKE_URL = "ducklake:https://data.deadlock-api.com/v1/catalog.ducklake"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PROJECT_ROOT / "data" / "coach.duckdb"

# DuckLake on Windows mistakes the catalog's absolute https:// file paths for relative
# ones and prefixes the cwd, so scans through `lake.*` fail. We read the catalog
# tables (attached as `meta`) ourselves and hand the URLs to read_parquet instead.


def connect(db_path: Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.sql("INSTALL ducklake; LOAD ducklake; INSTALL httpfs; LOAD httpfs;")
    con.sql(
        f"ATTACH IF NOT EXISTS '{LAKE_URL}' AS lake (READ_ONLY, METADATA_CATALOG 'meta')"
    )
    return con


def _table_id(con: duckdb.DuckDBPyConnection, table: str) -> int:
    row = con.execute(
        "SELECT table_id FROM meta.ducklake_table WHERE table_name = ? AND end_snapshot IS NULL",
        [table],
    ).fetchall()
    if not row:
        raise ValueError(f"no live lake table named {table!r}")
    return row[0][0]


def _check_plain_files(con: duckdb.DuckDBPyConnection, table_id: int) -> None:
    """Raise if the table has state that reading its parquet files directly would miss."""
    deletes = con.execute(
        "SELECT count(*) FROM meta.ducklake_delete_file WHERE table_id = ? AND end_snapshot IS NULL",
        [table_id],
    ).fetchall()[0][0]
    relative = con.execute(
        "SELECT count(*) FROM meta.ducklake_data_file"
        " WHERE table_id = ? AND end_snapshot IS NULL AND path_is_relative",
        [table_id],
    ).fetchall()[0][0]
    inlined = con.execute(
        "SELECT table_name FROM meta.ducklake_inlined_data_tables WHERE table_id = ?",
        [table_id],
    ).fetchall()
    inlined_rows = sum(
        con.sql(
            f'SELECT count(*) FROM meta."{name}" WHERE _ducklake_end_snapshot IS NULL'
        ).fetchall()[0][0]
        for (name,) in inlined
    )
    if deletes or relative or inlined_rows:
        raise RuntimeError(
            f"lake table {table_id} has {deletes} delete files, {relative} relative paths and "
            f"{inlined_rows} inlined rows; direct parquet reads would be wrong"
        )


def data_files(
    con: duckdb.DuckDBPyConnection,
    table: str,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[str]:
    """Live parquet URLs for a lake table.

    With since/until (timezone-aware), keeps only files whose start_time range
    overlaps [since, until). Files without start_time stats are always kept.
    """
    table_id = _table_id(con, table)
    _check_plain_files(con, table_id)
    rows = con.execute(
        """
        SELECT f.path
        FROM meta.ducklake_data_file f
        LEFT JOIN (
            SELECT s.data_file_id, s.min_value, s.max_value
            FROM meta.ducklake_file_column_stats s
            JOIN meta.ducklake_column c
              ON c.column_id = s.column_id AND c.table_id = s.table_id
             AND c.column_name = 'start_time' AND c.end_snapshot IS NULL
        ) st ON st.data_file_id = f.data_file_id
        WHERE f.table_id = $table_id AND f.end_snapshot IS NULL
          AND ($until IS NULL OR st.min_value IS NULL OR st.min_value::TIMESTAMPTZ < $until)
          AND ($since IS NULL OR st.max_value IS NULL OR st.max_value::TIMESTAMPTZ >= $since)
        ORDER BY f.file_order
        """,
        {"table_id": table_id, "since": since, "until": until},
    ).fetchall()
    return [r[0] for r in rows]


def match_player(
    con: duckdb.DuckDBPyConnection,
    since: datetime,
    until: datetime,
    columns: list[str] | None = None,
) -> duckdb.DuckDBPyRelation:
    """Rows of match_player_latest with start_time in [since, until).

    Same dedup as the lake's match_player_latest view, but over the parquet files directly.
    Pass columns to read only what you need; the files are large.
    """
    files = data_files(con, "match_player", since, until)
    if not files:
        raise ValueError(f"no match_player files cover {since} .. {until}")
    cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
    return con.sql(
        f"""
        SELECT {cols}
        FROM read_parquet($files, union_by_name = true)
        WHERE start_time >= $since AND start_time < $until
        QUALIFY row_number() OVER (
            PARTITION BY match_id, account_id, start_time ORDER BY created_at DESC
        ) = 1
        """,
        params={"files": files, "since": since, "until": until},
    )
