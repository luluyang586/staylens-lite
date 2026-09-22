import json
import sqlite3
from src.llm.review_tagger import tag_reviews, validate_tags


def test_exact_evidence_and_mixed_sentiment_validate():
    reviews=[{"review_id":1,"comments":"Great location but noisy at night."}]
    payload={"reviews":[{"review_id":1,"tags":[
        {"category":"location","sentiment":"positive","evidence":"Great location"},
        {"category":"noise","sentiment":"negative","evidence":"noisy at night"}]}]}
    assert len(validate_tags(payload,reviews)) == 1


def test_cached_tags_work_without_api(tmp_path):
    reviews=[{"review_id":9,"comments":"Very clean room."}]
    # First call creates the cache and honestly reports no model classification.
    tags,mode,warnings=tag_reviews(reviews,use_llm=False,cache_path=tmp_path/"nested/cache.sqlite")
    assert tags == [] and mode == "unavailable" and warnings


def test_foreign_evidence_rejected():
    reviews=[{"review_id":1,"comments":"Clean."}]
    payload={"reviews":[{"review_id":1,"tags":[
        {"category":"cleanliness","sentiment":"positive","evidence":"invented quote"}]}]}
    try:
        validate_tags(payload,reviews)
        assert False, "must reject invented evidence"
    except ValueError:
        pass
