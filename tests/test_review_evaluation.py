from scripts.run_review_evaluation import keys,prf


def test_review_prf_counts_strict_labels():
    gold={(1,"noise","negative"),(1,"location","positive")}
    pred={(1,"noise","negative"),(1,"location","negative")}
    result=prf(gold,pred)
    assert result["precision"]==0.5
    assert result["recall"]==0.5
    assert result["f1"]==0.5


def test_review_keys_can_ignore_sentiment():
    items=[{"review_id":1,"tags":[{"category":"noise","sentiment":"negative","evidence":"x"}]}]
    assert keys(items,False)=={(1,"noise")}


def test_empty_gold_and_prediction_are_perfect():
    assert prf(set(),set())["f1"]==1.0
