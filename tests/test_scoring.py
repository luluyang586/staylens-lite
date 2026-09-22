import pandas as pd
import pytest
from src.analytics.geospatial import haversine_km
from src.analytics.scoring import final_score_candidates, pre_score_candidates
from src.models.intent import StayIntent


def _candidates():
    return pd.DataFrame([
        {"listing_id":1,"neighbourhood":"CBD","room_type":"Entire home/apt","accommodates":2,
         "avg_nightly_price_aud":150,"rating_5":5.0,"number_of_reviews":2,"distance_km":0.5},
        {"listing_id":2,"neighbourhood":"CBD","room_type":"Entire home/apt","accommodates":2,
         "avg_nightly_price_aud":180,"rating_5":4.8,"number_of_reviews":200,"distance_km":1.0},
    ])


def _reference():
    return pd.DataFrame([{"listing_id":i,"neighbourhood":"CBD","room_type":"Entire home/apt",
                          "accommodates":2,"reference_price":p,"rating_5":4.5}
                         for i,p in enumerate([100,120,140,160,180,200],10)])


def test_scores_are_bounded_and_bayesian_rating_shrinks_small_sample():
    intent=StayIntent(nights=5,guests=2,budget_amount=200)
    pre=pre_score_candidates(_candidates(),intent,_reference(),4.5)
    final=final_score_candidates(pre)
    assert final.final_score.between(0,100).all()
    a=pre.loc[pre.listing_id==1,"adjusted_rating"].iloc[0]
    assert 4.5 < a < 5.0


def test_reference_population_is_not_candidate_subset():
    intent=StayIntent(nights=5,guests=2,budget_amount=200)
    pre=pre_score_candidates(_candidates(),intent,_reference(),4.5)
    assert (pre.reference_n == 6).all()
    assert (pre.reference_basis == "区域/房型/人数±1").all()


def test_invalid_weights_fail_closed():
    pre=pre_score_candidates(_candidates(),StayIntent(nights=5,guests=2,budget_amount=200),_reference(),4.5)
    with pytest.raises(ValueError):
        final_score_candidates(pre,weights={"price_score":1,"rating_score":1,"location_score":0,"review_score":0})


def test_haversine_zero_distance():
    assert float(haversine_km(1,2,1,2)) == pytest.approx(0)
