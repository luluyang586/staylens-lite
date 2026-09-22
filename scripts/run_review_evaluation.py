"""One-shot live evaluation of review aspect/sentiment classification."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.config import ROOT,settings
from src.llm.client import complete_json,reset_usage_events,usage_summary
from src.llm.review_tagger import REVIEW_RESPONSE_SCHEMA
from src.models.intent import TaggedReview


def prf(gold,pred):
    true_positive=len(gold & pred)
    precision=true_positive/len(pred) if pred else (1.0 if not gold else 0.0)
    recall=true_positive/len(gold) if gold else (1.0 if not pred else 0.0)
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    return {"precision":precision,"recall":recall,"f1":f1,
            "true_positive":true_positive,"gold":len(gold),"predicted":len(pred)}


def keys(items,with_sentiment=True,category=None):
    values=set()
    for item in items:
        review_id=int(item["review_id"])
        for tag in item["tags"]:
            if category and tag["category"]!=category:
                continue
            values.add((review_id,tag["category"],tag["sentiment"]) if with_sentiment
                       else (review_id,tag["category"]))
    return values


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--confirm-live-calls",action="store_true")
    parser.add_argument("--allow-rerun",action="store_true")
    args=parser.parse_args()
    if not args.confirm_live_calls:
        raise SystemExit("Refusing API calls without --confirm-live-calls")
    if not settings.has_llm:
        raise SystemExit("Configure a supported provider, model and API key in .env")
    out=ROOT/"evaluation/llm_review_reference_v1_report.json"
    if out.exists() and not args.allow_rerun:
        raise SystemExit("Review report already exists; refusing overwrite without --allow-rerun")
    source=ROOT/"evaluation/review_reference_v1.json"
    dataset=json.loads(source.read_text())
    prompt_path=ROOT/"prompts/review_tagger.txt"
    prompt=prompt_path.read_text()
    reset_usage_events()
    started=time.perf_counter()
    predicted=[];batch_failures=[];contract_issues=[]
    evidence_valid=0;evidence_total=0
    for offset in range(0,len(dataset),10):
        batch=[{"review_id":x["review_id"],"comments":x["comments"]} for x in dataset[offset:offset+10]]
        try:
            payload=complete_json(prompt,json.dumps({"reviews":batch},ensure_ascii=False),max_tokens=6000,
                                  json_schema=REVIEW_RESPONSE_SCHEMA,schema_name="staylens_review_tags")
            raw_items=payload.get("reviews") if isinstance(payload,dict) else None
            if not isinstance(raw_items,list):
                raise ValueError("Expected reviews array")
            expected={int(x["review_id"]):str(x["comments"]) for x in batch}
            seen=set()
            for raw_item in raw_items:
                try:
                    item=TaggedReview.model_validate(raw_item)
                except Exception as exc:
                    contract_issues.append({"offset":offset,"type":"invalid_item","error":str(exc)})
                    continue
                review_id=int(item.review_id)
                if review_id not in expected:
                    contract_issues.append({"offset":offset,"type":"foreign_id","review_id":review_id})
                    continue
                if review_id in seen:
                    contract_issues.append({"offset":offset,"type":"duplicate_id","review_id":review_id})
                    continue
                seen.add(review_id)
                categories=[tag.category for tag in item.tags]
                if len(categories)!=len(set(categories)):
                    contract_issues.append({"offset":offset,"type":"duplicate_category","review_id":review_id})
                for tag in item.tags:
                    evidence_total+=1
                    evidence_valid+=int(tag.evidence in expected[review_id])
                predicted.append(item.model_dump(mode="json"))
            for missing_id in set(expected)-seen:
                contract_issues.append({"offset":offset,"type":"missing_id","review_id":missing_id})
        except Exception as exc:
            batch_failures.append({"offset":offset,"review_ids":[x["review_id"] for x in batch],
                                   "error":type(exc).__name__+": "+str(exc)})

    gold=[{"review_id":x["review_id"],"tags":x["expected_tags"]} for x in dataset]
    gold_strict=keys(gold,True);pred_strict=keys(predicted,True)
    gold_category=keys(gold,False);pred_category=keys(predicted,False)
    prediction_by_id={int(x["review_id"]):x["tags"] for x in predicted}
    exact=[]
    for item in gold:
        review_id=int(item["review_id"])
        expected={(x["category"],x["sentiment"]) for x in item["tags"]}
        actual={(x["category"],x["sentiment"]) for x in prediction_by_id.get(review_id,[])}
        exact.append(expected==actual)
    matched_pairs=gold_category & pred_category
    gold_sent={(r,c):s for r,c,s in gold_strict}
    pred_sent={(r,c):s for r,c,s in pred_strict}
    sentiment_correct=sum(gold_sent[p]==pred_sent[p] for p in matched_pairs)
    categories=["location","noise","cleanliness","value","host_service","amenities","accuracy","safety"]
    per_category={c:prf(keys(gold,True,c),keys(predicted,True,c)) for c in categories}
    empty_ids={int(x["review_id"]) for x in gold if not x["tags"]}
    empty_correct=sum(not prediction_by_id.get(review_id,[]) for review_id in empty_ids)
    cases=[]
    for item in gold:
        review_id=int(item["review_id"])
        cases.append({"review_id":review_id,"expected_tags":item["tags"],
                      "predicted_tags":prediction_by_id.get(review_id),
                      "exact":exact[len(cases)]})
    results={
        "review_count":len(dataset),"reference_tag_count":len(gold_strict),
        "classified_review_count":len(prediction_by_id),"batch_failures":batch_failures,
        "contract_issues":contract_issues,
        "strict_aspect_sentiment_micro":prf(gold_strict,pred_strict),
        "aspect_detection_micro":prf(gold_category,pred_category),
        "review_exact_match":sum(exact)/len(exact),
        "sentiment_accuracy_on_matched_aspects":sentiment_correct/len(matched_pairs) if matched_pairs else 0.0,
        "matched_aspect_count":len(matched_pairs),
        "empty_review_accuracy":empty_correct/len(empty_ids) if empty_ids else None,
        "empty_review_count":len(empty_ids),
        "evidence_exact_source_validation":evidence_valid/evidence_total if evidence_total else None,
        "valid_evidence_count":evidence_valid,"predicted_evidence_count":evidence_total,
        "per_category":per_category,"cases":cases,
    }
    report={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "provider":settings.llm_provider,"model":settings.llm_model,"temperature":0,
        "annotation_provenance":"Codex-assisted curated reference labels; not human-labelled",
        "dataset_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "prompt_sha256":hashlib.sha256(prompt_path.read_bytes()).hexdigest(),
        "api_usage":usage_summary(),"elapsed_seconds":time.perf_counter()-started,
        "results":results,
    }
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="results"},ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in results.items() if k not in {"cases","per_category"}},ensure_ascii=False,indent=2))
    if batch_failures:
        raise SystemExit(1)


if __name__=="__main__":
    main()
