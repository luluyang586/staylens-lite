"""Build a small, deterministic deployment database from the full real snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data/staylens.duckdb"
TARGET = ROOT / "data/staylens_demo.duckdb"
STAGING = ROOT / "data/building-demo.duckdb"


def build() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError("Build data/staylens.duckdb from the verified raw snapshot first")
    if STAGING.exists():
        raise FileExistsError(f"Remove or inspect stale staging file: {STAGING}")

    source_sql = str(SOURCE).replace("'", "''")
    connection = duckdb.connect(str(STAGING))
    try:
        connection.execute(f"ATTACH '{source_sql}' AS source (READ_ONLY)")
        connection.execute(
            """
            CREATE TABLE listings_clean AS
            SELECT * EXCLUDE(sample_rank)
            FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY neighbourhood, room_type
                    ORDER BY HASH(listing_id), listing_id
                ) AS sample_rank
                FROM source.listings_clean
            )
            WHERE sample_rank <= 5
            """
        )
        connection.execute("CREATE UNIQUE INDEX listing_key ON listings_clean(listing_id)")
        connection.execute(
            """
            CREATE TABLE calendar_clean AS
            SELECT c.* FROM source.calendar_clean c
            JOIN listings_clean l USING (listing_id)
            """
        )
        connection.execute(
            "CREATE UNIQUE INDEX calendar_key ON calendar_clean(listing_id, stay_date)"
        )
        connection.execute(
            """
            CREATE TABLE reviews_clean AS
            SELECT * EXCLUDE(review_rank)
            FROM (
                SELECT r.*, ROW_NUMBER() OVER (
                    PARTITION BY r.listing_id
                    ORDER BY r.review_date DESC, r.review_id DESC
                ) AS review_rank
                FROM source.reviews_clean r
                JOIN listings_clean l USING (listing_id)
            )
            WHERE review_rank <= 20
            """
        )
        connection.execute("CREATE TABLE poi AS SELECT * FROM source.poi")
        connection.execute("CREATE TABLE metadata(key VARCHAR PRIMARY KEY, value VARCHAR)")
        original = dict(connection.execute("SELECT key, value FROM source.metadata").fetchall())
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("listings_clean", "calendar_clean", "reviews_clean", "poi")
        }
        values = [
            ("data_kind", "real_public_sample"),
            ("snapshot", original.get("snapshot", "unknown")),
            ("source_url", original.get("source_url", "unknown")),
            ("calendar_has_price", original.get("calendar_has_price", "false")),
            ("built_at", datetime.now(timezone.utc).isoformat()),
            (
                "sample_method",
                "deterministic hash sample: up to 5 listings per neighbourhood and room_type; "
                "all calendar rows and latest 20 reviews per sampled listing",
            ),
            ("sample_counts", json.dumps(counts, sort_keys=True)),
        ]
        connection.executemany("INSERT INTO metadata VALUES (?, ?)", values)
        connection.execute("CHECKPOINT")
        connection.close()
        os.replace(STAGING, TARGET)
        print(json.dumps(counts, ensure_ascii=False), TARGET.stat().st_size)
    except Exception:
        connection.close()
        raise


if __name__ == "__main__":
    build()
