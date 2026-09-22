import pytest

from src.database.sql_validator import SQLValidationError, validate_select_sql


def test_allows_read_only_query():
    sql = validate_select_sql(
        "SELECT neighbourhood, COUNT(*) AS n FROM listings_clean GROUP BY neighbourhood"
    )
    assert "SELECT" in sql.upper()


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE listings_clean",
        "DELETE FROM listings_clean",
        "SELECT * FROM secret_table",
        "SELECT * FROM read_csv_auto('/tmp/private.csv')",
        "SELECT * FROM listings_clean; SELECT * FROM poi",
    ],
)
def test_rejects_unsafe_queries(sql):
    with pytest.raises(SQLValidationError):
        validate_select_sql(sql)


def test_adds_limit_to_row_level_query():
    sql = validate_select_sql("SELECT * FROM listings_clean")
    assert "LIMIT 200" in sql.upper()


def test_cte_and_window_function_are_allowed():
    safe = validate_select_sql("""WITH x AS (
      SELECT neighbourhood, base_price_aud,
      ROW_NUMBER() OVER(PARTITION BY neighbourhood ORDER BY base_price_aud DESC) rk
      FROM listings_clean)
      SELECT neighbourhood, base_price_aud FROM x WHERE rk=1""")
    assert "BOUNDED_RESULT" in safe.upper()


def test_unknown_column_is_rejected():
    with pytest.raises(SQLValidationError):
        validate_select_sql("SELECT private_secret FROM listings_clean")


def test_existing_large_limit_is_still_outer_bounded():
    safe=validate_select_sql("SELECT * FROM listings_clean LIMIT 1000000")
    assert safe.upper().rstrip().endswith("LIMIT 200")


def test_date_trunc_and_bounded_date_range_are_allowed():
    safe=validate_select_sql("""SELECT DATE_TRUNC('month', review_date) AS month,
      COUNT(*) AS review_count FROM reviews_clean
      WHERE review_date >= DATE '2026-01-01' AND review_date < DATE '2027-01-01'
      GROUP BY DATE_TRUNC('month', review_date)""")
    assert "TIMESTAMP_TRUNC" in safe.upper() or "DATE_TRUNC" in safe.upper()
