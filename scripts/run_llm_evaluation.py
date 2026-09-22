"""Opt-in live-model evaluation. This script makes paid/external API calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config import ROOT,settings
from src.database.sql_validator import execute_sql
from src.llm.intent_parser import parse_intent
from src.llm.text_to_sql import run_analysis
from src.llm.client import reset_usage_events,usage_summary


def prompt_hash(name):
    return hashlib.sha256((ROOT/"prompts"/name).read_bytes()).hexdigest()


def intent_suite(filename="intent_final_v2_cases.json"):
    cases=json.loads((ROOT/"evaluation"/filename).read_text())
    rows=[];correct_fields=0;total_fields=0
    unordered_lists={"preferred_neighbourhoods","target_pois","hard_preferences","soft_preferences","missing_required_fields"}
    for case in cases:
        try:
            actual,_=parse_intent(case["input"])
            payload=json.loads(actual.model_dump_json())
            comparisons={
                k:(sorted(payload.get(k,[]))==sorted(v) if k in unordered_lists else payload.get(k)==v)
                for k,v in case["expected"].items()
            }
            status="ok"
        except Exception as exc:
            payload=None;comparisons={k:False for k in case["expected"]}
            status=type(exc).__name__+": "+str(exc)
        correct_fields+=sum(comparisons.values());total_fields+=len(comparisons)
        rows.append({"id":case["id"],"category":case.get("category","unspecified"),
                     "all_expected_fields":all(comparisons.values()),
                     "field_matches":comparisons,"actual":payload,"status":status})
    slices={}
    for category in sorted({x["category"] for x in rows}):
        subset=[x for x in rows if x["category"]==category]
        slice_fields=sum(len(x["field_matches"]) for x in subset)
        slice_correct=sum(sum(x["field_matches"].values()) for x in subset)
        slices[category]={"n":len(subset),
                          "case_exact":sum(x["all_expected_fields"] for x in subset)/len(subset),
                          "field_accuracy":slice_correct/slice_fields}
    return {"case_exact":sum(x["all_expected_fields"] for x in rows)/len(rows),
            "field_accuracy":correct_fields/total_fields,"n":len(rows),
            "target_field_count":total_fields,"slice_metrics":slices,"cases":rows}


def sql_suite(filename="sql_final_v2_cases.json"):
    cases=json.loads((ROOT/"evaluation"/filename).read_text())
    rows=[]
    for case in cases:
        result=run_analysis(case["question"],use_llm=True)
        expected=case["status"]
        actual="supported" if result.status=="ok" else "unsupported"
        columns=list(result.data.columns) if result.data is not None else []
        columns_ok=expected=="unsupported" or set(case["expected_columns"]).issubset(columns)
        status_match=actual==expected
        result_match=None
        if expected=="supported" and status_match and columns_ok and case.get("reference_sql"):
            _,reference=execute_sql(case["reference_sql"])
            selected=case["expected_columns"]
            actual_frame=result.data[selected].copy()
            reference_frame=reference[selected].copy()
            actual_frame=actual_frame.sort_values(selected,key=lambda col:col.astype(str)).reset_index(drop=True)
            reference_frame=reference_frame.sort_values(selected,key=lambda col:col.astype(str)).reset_index(drop=True)
            try:
                pd.testing.assert_frame_equal(actual_frame,reference_frame,check_dtype=False,rtol=1e-6,atol=1e-6)
                result_match=True
            except AssertionError:
                result_match=False
        contract_passed=status_match and columns_ok
        semantic_passed=contract_passed and result_match is not False
        rows.append({"id":case["id"],"expected_status":expected,"actual_status":actual,
                     "columns":columns,"columns_ok":columns_ok,"status_match":status_match,
                     "result_match":result_match,"passed":semantic_passed,
                     "sql":result.sql,"reason":result.reason,"attempt_count":result.attempt_count})
    return {"status_execution_accuracy":sum(x["status_match"] for x in rows)/len(rows),
            "output_contract_accuracy":sum(x["status_match"] and x["columns_ok"] for x in rows)/len(rows),
            "semantic_result_accuracy":sum(x["passed"] for x in rows)/len(rows),
            "n":len(rows),"cases":rows}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--suite",choices=["intent_final_v2","sql_final_v2"],required=True)
    parser.add_argument("--confirm-live-calls",action="store_true")
    parser.add_argument("--allow-final-rerun",action="store_true",
                        help="Required to overwrite an existing final-v2 report")
    args=parser.parse_args()
    if not args.confirm_live_calls: raise SystemExit("Refusing API calls without --confirm-live-calls")
    if not settings.has_llm: raise SystemExit("Configure a supported provider, model and API key in .env")
    reset_usage_events()
    if args.suite=="intent_final_v2": results=intent_suite("intent_final_v2_cases.json")
    else: results=sql_suite("sql_final_v2_cases.json")
    prompt="intent_parser.txt" if args.suite.startswith("intent") else "text_to_sql.txt"
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"suite":args.suite,
            "provider":settings.llm_provider,"model":settings.llm_model,
            "prompt_sha256":prompt_hash(prompt),
            "dataset_sha256":hashlib.sha256((ROOT/"evaluation"/(args.suite+"_cases.json")).read_bytes()).hexdigest(),
            "api_usage":usage_summary(),"results":results}
    out=ROOT/"evaluation"/f"llm_{args.suite}_report.json"
    if out.exists() and not args.allow_final_rerun:
        raise SystemExit("Final-v2 report already exists; refusing overwrite without --allow-final-rerun")
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!="results"},ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in results.items() if k!="cases"},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
