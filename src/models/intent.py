"""Validated intent and provenance-aware review schemas."""
from datetime import date, timedelta
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
class SearchMode(str, Enum):
    EXPLORATION = "exploration"
    DATE_SPECIFIC = "date_specific"
class BudgetType(str, Enum):
    PER_NIGHT = "per_night"
    TOTAL = "total"
class StayIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent_type: Literal["listing_recommendation", "market_analysis"] = "listing_recommendation"
    search_mode: SearchMode = SearchMode.EXPLORATION
    check_in_date: date | None = None
    nights: int | None = Field(None, ge=1, le=90)
    budget_amount: float | None = Field(None, gt=0, allow_inf_nan=False)
    budget_type: BudgetType = BudgetType.PER_NIGHT
    currency: str = "AUD"
    guests: int | None = Field(None, ge=1, le=30)
    room_type_preference: Literal["Entire home/apt","Private room","Shared room","Hotel room"] | None = None
    preferred_neighbourhoods: list[str] = Field(default_factory=list)
    target_pois: list[str] = Field(default_factory=list)
    max_distance_km: float | None = Field(None, gt=0, le=100, allow_inf_nan=False)
    hard_preferences: list[str] = Field(default_factory=list)
    soft_preferences: list[Literal["quiet","clean","safe","near_transit"]] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None
    @model_validator(mode="after")
    def derive_state(self):
        self.currency = self.currency.upper()
        self.search_mode = SearchMode.DATE_SPECIFIC if self.check_in_date else SearchMode.EXPLORATION
        missing = [k for k in ("guests","nights","budget_amount") if getattr(self,k) is None]
        if self.currency != "AUD": missing.append("currency")
        if self.max_distance_km is not None and not self.target_pois: missing.append("target_pois")
        self.missing_required_fields = missing
        self.needs_clarification = bool(missing)
        labels = {"guests":"入住人数","nights":"入住晚数（天数不等于晚数）","budget_amount":"预算",
                  "currency":"以AUD表示的预算","target_pois":"距离限制对应的地点"}
        self.clarification_question = "请补充" + "、".join(labels[k] for k in missing) + "。" if missing else None
        return self
    @property
    def check_out_date(self):
        return self.check_in_date + timedelta(days=self.nights) if self.check_in_date and self.nights else None
    @property
    def nightly_budget(self):
        if self.budget_amount is None: return None
        return self.budget_amount / self.nights if self.budget_type == BudgetType.TOTAL and self.nights else self.budget_amount
class ReviewTag(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["location","noise","cleanliness","value","host_service","amenities","accuracy","safety"]
    sentiment: Literal["positive","negative","neutral","mixed"]
    evidence: str = Field(min_length=1, max_length=400)
class TaggedReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: int
    tags: list[ReviewTag] = Field(default_factory=list)
