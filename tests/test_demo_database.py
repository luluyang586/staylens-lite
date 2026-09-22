from pathlib import Path

import duckdb
import pytest

from src.config import ROOT


DEMO = ROOT / "data/staylens_demo.duckdb"


@pytest.mark.skipif(not DEMO.exists(), reason="deployment demo database not built")
def test_demo_database_is_real_sample_and_internally_consistent():
    with duckdb.connect(str(DEMO), read_only=True) as connection:
        metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
        assert metadata["data_kind"] == "real_public_sample"
        assert metadata["source_url"].startswith("https://insideairbnb.com/")
        listing_count = connection.execute("SELECT COUNT(*) FROM listings_clean").fetchone()[0]
        orphan_calendar = connection.execute(
            "SELECT COUNT(*) FROM calendar_clean c ANTI JOIN listings_clean l USING(listing_id)"
        ).fetchone()[0]
        orphan_reviews = connection.execute(
            "SELECT COUNT(*) FROM reviews_clean r ANTI JOIN listings_clean l USING(listing_id)"
        ).fetchone()[0]
        assert 0 < listing_count < 20_573
        assert orphan_calendar == 0
        assert orphan_reviews == 0
        assert connection.execute("SELECT COUNT(*) FROM poi").fetchone()[0] == 10
