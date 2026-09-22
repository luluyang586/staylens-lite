"""Review classification, exact evidence checks and versioned persistent cache."""
import hashlib,json,sqlite3
from datetime import datetime,timezone
from src.config import ROOT,settings
from src.llm.client import complete_json,LLMUnavailable
from src.models.intent import TaggedReview
CACHE=ROOT/"data/review_cache.sqlite"
REVIEW_RESPONSE_SCHEMA={
    "type":"object",
    "properties":{
        "reviews":{
            "type":"array",
            "items":{
                "type":"object",
                "properties":{
                    "review_id":{"type":"integer"},
                    "tags":{
                        "type":"array",
                        "items":{
                            "type":"object",
                            "properties":{
                                "category":{"type":"string","enum":["location","noise","cleanliness","value","host_service","amenities","accuracy","safety"]},
                                "sentiment":{"type":"string","enum":["positive","negative","neutral","mixed"]},
                                "evidence":{"type":"string","minLength":1,"maxLength":400},
                            },
                            "required":["category","sentiment","evidence"],
                            "additionalProperties":False,
                        },
                    },
                },
                "required":["review_id","tags"],
                "additionalProperties":False,
            },
        },
    },
    "required":["reviews"],
    "additionalProperties":False,
}
def validate_tags(payload,reviews):
    if not isinstance(payload,dict) or not isinstance(payload.get("reviews"),list):
        raise ValueError("Expected reviews array")
    expected={int(r["review_id"]):str(r["comments"]) for r in reviews}
    items=[TaggedReview.model_validate(x) for x in payload["reviews"]]
    ids=[x.review_id for x in items]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected):raise ValueError("Missing, duplicate or foreign review IDs")
    for r in items:
        categories=[t.category for t in r.tags]
        if len(categories)!=len(set(categories)):raise ValueError("Duplicate category")
        for t in r.tags:
            if t.evidence not in expected[r.review_id]:raise ValueError("Evidence is not an exact source excerpt")
    return items
def tag_reviews(reviews,use_llm=False,cache_path=None):
    if not reviews:return [],"no_reviews",[]
    prompt=(ROOT/"prompts/review_tagger.txt").read_text()
    prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()
    model=(settings.base_url or settings.llm_provider)+":"+settings.llm_model
    resolved_cache = cache_path or CACHE
    # SQLite does not create missing parent directories.  Keep the cache a
    # derived artifact and make its location explicit before opening it.
    resolved_cache.parent.mkdir(parents=True, exist_ok=True)
    cache=sqlite3.connect(str(resolved_cache))
    cache.execute("CREATE TABLE IF NOT EXISTS review_cache(cache_key TEXT PRIMARY KEY,payload TEXT,review_id INTEGER,model TEXT,prompt_hash TEXT,processed_at TEXT)")
    found=[];pending=[];warnings=[]
    def key(r):
        text=str(r["review_id"])+"|"+str(r["comments"])+"|"+model+"|"+prompt_hash
        return hashlib.sha256(text.encode()).hexdigest()
    for r in reviews:
        row=cache.execute("SELECT payload FROM review_cache WHERE cache_key=?",[key(r)]).fetchone()
        if row:
            try:found.extend(validate_tags({"reviews":[json.loads(row[0])]},[r]))
            except Exception:pending.append(r)
        else:pending.append(r)
    if pending and use_llm and settings.has_llm:
        for offset in range(0,len(pending),10):
            batch=pending[offset:offset+10]
            # Never truncate comments silently: bounded batches retain original source.
            if sum(len(str(x["comments"])) for x in batch)>60000:
                warnings.append("Skipped oversized review batch");continue
            try:
                payload=complete_json(prompt,json.dumps({"reviews":batch},ensure_ascii=False),max_tokens=6000,
                                      json_schema=REVIEW_RESPONSE_SCHEMA,schema_name="staylens_review_tags")
                items=validate_tags(payload,batch)
                by_id={i.review_id:i for i in items}
                for r in batch:
                    item=by_id[int(r["review_id"])]
                    cache.execute("INSERT OR REPLACE INTO review_cache VALUES (?,?,?,?,?,?)",
                     [key(r),item.model_dump_json(),item.review_id,model,prompt_hash,datetime.now(timezone.utc).isoformat()])
                cache.commit();found.extend(items)
            except Exception:
                warnings.append("A review batch failed API/output validation; its score remains unknown.")
    cache.close()
    if not found:return [],"unavailable",["评论尚未经过模型分析，使用中性分；不能据此判断没有风险。"]+warnings
    mode="validated_cache_or_live" if len(found)==len(reviews) else "partial"
    if mode=="partial":warnings.append(f"Only {len(found)}/{len(reviews)} reviews classified; incomplete evidence.")
    return found,mode,warnings
