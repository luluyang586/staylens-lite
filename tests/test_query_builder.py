from datetime import date

from src.database.query_builder import build_recommendation_query
from src.models.intent import StayIntent


def test_exploration_query_is_parameterized():
    intent = StayIntent(nights=5, guests=2, budget_amount=250)
    sql, params = build_recommendation_query(intent)
    assert "base_price_aud <= ?" in sql
    assert 250 in params
    assert "250" not in sql


def test_date_query_checks_every_night():
    intent = StayIntent(
        check_in_date=date(2026, 10, 1), nights=5, guests=2, budget_amount=250
    )
    sql, params = build_recommendation_query(intent)
    assert "COUNT(DISTINCT c.stay_date)=" in sql
    assert "COUNT(DISTINCT CASE WHEN c.available" in sql
    assert intent.check_out_date == date(2026, 10, 6)


def test_room_and_neighbourhood_are_parameters_not_interpolated():
    intent = StayIntent(nights=2, guests=1, budget_amount=100,
        room_type_preference="Private room", preferred_neighbourhoods=["Sydney"])
    sql, params = build_recommendation_query(intent)
    assert "Private room" not in sql and "Sydney" not in sql
    assert "Private room" in params and "Sydney" in params
