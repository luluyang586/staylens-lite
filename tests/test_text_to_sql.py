import src.llm.text_to_sql as text_to_sql


def test_rechecks_false_unsupported(monkeypatch):
    replies=iter([
        {"status":"unsupported","sql":None,"reason":"field absent"},
        {"status":"supported","sql":"SELECT host_is_superhost, AVG(rating_5) AS avg_rating, COUNT(*) AS n FROM listings_clean GROUP BY host_is_superhost","reason":None},
    ])
    monkeypatch.setattr(text_to_sql,"complete_json",lambda *args,**kwargs: next(replies))
    result=text_to_sql.run_analysis("比较超赞房东与普通房东评分",use_llm=True)
    assert result.status=="ok"
    assert result.attempt_count==2
    assert {"host_is_superhost","avg_rating","n"}.issubset(result.data.columns)


def test_repairs_rejected_multiple_statements(monkeypatch):
    replies=iter([
        {"status":"supported","sql":"SELECT COUNT(*) FROM calendar_clean; SELECT 1","reason":None},
        {"status":"supported","sql":"SELECT COUNT(*) AS available_count FROM calendar_clean WHERE available","reason":None},
    ])
    monkeypatch.setattr(text_to_sql,"complete_json",lambda *args,**kwargs: next(replies))
    result=text_to_sql.run_analysis("可预订日历记录总数",use_llm=True)
    assert result.status=="ok"
    assert result.attempt_count==2
    assert "available_count" in result.data.columns


def test_confirms_genuinely_unsupported(monkeypatch):
    calls=[]
    def reply(*args,**kwargs):
        calls.append(kwargs)
        return {"status":"unsupported","sql":None,"reason":"No booking or revenue fields exist."}
    monkeypatch.setattr(text_to_sql,"complete_json",reply)
    result=text_to_sql.run_analysis("计算真实入住收入",use_llm=True)
    assert result.status=="unsupported"
    assert result.attempt_count==2
    assert len(calls)==2
