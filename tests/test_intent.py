from datetime import date
import pytest
from pydantic import ValidationError
from src.models.intent import BudgetType, SearchMode, StayIntent


def test_missing_required_fields_are_explicit():
    intent = StayIntent()
    assert intent.needs_clarification
    assert set(intent.missing_required_fields) == {"guests", "nights", "budget_amount"}


def test_total_budget_and_date_state():
    intent = StayIntent(check_in_date=date(2026, 7, 1), nights=4, guests=2,
                        budget_amount=1000, budget_type=BudgetType.TOTAL)
    assert intent.search_mode == SearchMode.DATE_SPECIFIC
    assert intent.check_out_date == date(2026, 7, 5)
    assert intent.nightly_budget == 250
    assert not intent.needs_clarification


def test_distance_without_poi_requires_clarification():
    intent = StayIntent(nights=3, guests=2, budget_amount=200, max_distance_km=2)
    assert "target_pois" in intent.missing_required_fields


@pytest.mark.parametrize("field,value", [("nights", 0), ("guests", 0), ("budget_amount", -1)])
def test_invalid_hard_constraints_rejected(field, value):
    payload = {"nights": 3, "guests": 2, "budget_amount": 200, field: value}
    with pytest.raises(ValidationError):
        StayIntent(**payload)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        StayIntent(nights=3, guests=2, budget_amount=200, invented=True)
