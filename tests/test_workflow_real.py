from datetime import date
import pytest
from src.database.connection import database_exists, metadata
from src.models.intent import StayIntent
from src.workflow.recommendation import run_recommendation

pytestmark=pytest.mark.skipif(not database_exists(),reason="real snapshot database not built")


def base(**overrides):
    data={"nights":3,"guests":2,"budget_amount":250}
    data.update(overrides)
    return StayIntent(**data)


def test_database_is_declared_real():
    assert metadata()["data_kind"] in {"real_public_snapshot", "real_public_sample"}


def test_real_exploration_enforces_budget_and_capacity(monkeypatch,tmp_path):
    monkeypatch.setattr("src.llm.review_tagger.CACHE",tmp_path/"review_cache.sqlite")
    result=run_recommendation(intent_override=base(),persist=False)
    assert result.status == "ok"
    assert not result.recommendations.empty
    assert (result.recommendations.avg_nightly_price_aud <= 250).all()
    assert (result.recommendations.accommodates >= 2).all()
    assert result.review_mode == "unavailable"


def test_unknown_poi_fails_closed():
    result=run_recommendation(intent_override=base(target_pois=["invented"],max_distance_km=2),persist=False)
    assert result.status == "unknown_poi"


def test_date_specific_budget_is_not_replaced_by_base_price():
    result=run_recommendation(intent_override=base(check_in_date=date(2026,7,1)),persist=False)
    assert result.status == "date_price_unavailable"
