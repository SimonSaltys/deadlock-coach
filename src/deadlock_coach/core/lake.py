from pathlib import Path

import duckdb

LAKE_URL = "ducklake:https://data.deadlock-api.com/v1/catalog.ducklake"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PROJECT_ROOT / "data" / "coach.duckdb"


def connect(db_path: Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.sql("INSTALL ducklake; LOAD ducklake; INSTALL httpfs; LOAD httpfs;")
    con.sql(f"ATTACH IF NOT EXISTS '{LAKE_URL}' AS lake (READ_ONLY)")
    return con