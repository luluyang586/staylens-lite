"""Run deterministic evaluations; never fabricate LLM metrics."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import ROOT, settings
from src.database.connection import metadata
from src.database.sql_validator import SQLValidationError, validate_select_sql
from src.models.intent import BudgetType, StayIntent
from src.workflow.recommendation import run_recommendation


def saved_llm_metrics():
    """Summarize saved live reports without making any API calls."""
    report_specs = {
        "intent_final_v2": ROOT / "evaluation/llm_intent_final_v2_report.json",
        "text_to_sql_final_v2": ROOT / "evaluation/llm_sql_final_v2_report.json",
        "review_reference_v1": ROOT / "evaluation/llm_review_reference_v1_report.json",
    }
    summaries = {}
    common = {}
    for label, path in report_specs.items():
        if not path.exists():
            summaries[label] = None
            continue
        payload = json.loads(path.read_text())
        results = payload.get("results", {})
        summaries[label] = {
            key: results.get(key)
            for key in (
                "case_exact",
                "field_accuracy",
                "status_execution_accuracy",
                "output_contract_accuracy",
                "semantic_result_accuracy",
                "target_field_count",
                "review_count",
                "review_exact_match",
                "sentiment_accuracy_on_matched_aspects",
                "evidence_exact_source_validation",
                "n",
            )
            if key in results
        }
        if label=="review_reference_v1":
            summaries[label]["strict_aspect_sentiment_micro"]=results.get("strict_aspect_sentiment_micro")
            summaries[label]["aspect_detection_micro"]=results.get("aspect_detection_micro")
        common[label] = {
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "prompt_sha256": payload.get("prompt_sha256"),
            "generated_at": payload.get("generated_at"),
            "report": str(path.relative_to(ROOT)),
        }
    return {
        "configured_now": settings.has_llm,
        "intent_final_v2": summaries.get("intent_final_v2"),
        "text_to_sql_final_v2": summaries.get("text_to_sql_final_v2"),
        "review_reference_v1": summaries.get("review_reference_v1"),
        "report_metadata": common,
        "note": (
            "Saved frozen-suite results are measured API outputs; this script only consolidates them. "
            "Review metrics use Codex-assisted curated reference labels, not human ground truth."
        ),
    }


def intent(**overrides):
    values={"nights":3,"guests":2,"budget_amount":250}
    values.update(overrides)
    return StayIntent(**values)


def evaluate_scenarios():
    cases=[
        ("basic_exploration",intent(),"ok"),
        ("total_budget",intent(nights=4,budget_amount=800,budget_type=BudgetType.TOTAL),"ok"),
        ("private_room",intent(room_type_preference="Private room"),"ok"),
        ("known_area",intent(preferred_neighbourhoods=["Sydney"]),"ok"),
        ("known_poi_distance",intent(target_pois=["Sydney Opera House"],max_distance_km=5),"ok"),
        ("unknown_poi",intent(target_pois=["Invented Place"],max_distance_km=2),"unknown_poi"),
        ("unknown_area",intent(preferred_neighbourhoods=["Invented Area"]),"unknown_area"),
        ("date_without_daily_price",intent(check_in_date=date(2026,7,1)),"date_price_unavailable"),
        ("impossible_budget",intent(budget_amount=1),"no_results"),
        ("transit_preference",intent(soft_preferences=["near_transit"]),"ok"),
    ]
    rows=[]
    for name,case,expected in cases:
        result=run_recommendation(intent_override=case,persist=False)
        assertions=[]
        if result.status=="ok":
            assertions += [
                bool((result.recommendations.accommodates >= case.guests).all()),
                bool((result.recommendations.avg_nightly_price_aud <= case.nightly_budget).all()),
                len(result.recommendations) <= 5,
            ]
        passed=result.status==expected and all(assertions or [True])
        rows.append({"id":name,"expected_status":expected,"actual_status":result.status,
                     "passed":passed,"rows":len(result.recommendations),"warnings":result.warnings})
    return rows


def evaluate_sql_boundary():
    accepted=[
        "SELECT neighbourhood,COUNT(*) n FROM listings_clean GROUP BY neighbourhood",
        "WITH x AS (SELECT listing_id,base_price_aud FROM listings_clean) SELECT * FROM x",
        "SELECT room_type,MEDIAN(base_price_aud) p FROM listings_clean GROUP BY room_type",
        "SELECT listing_id,ROW_NUMBER() OVER(ORDER BY base_price_aud) rk FROM listings_clean",
    ]
    rejected=[
        "DROP TABLE listings_clean",
        "DELETE FROM listings_clean",
        "SELECT * FROM secret_table",
        "SELECT secret_column FROM listings_clean",
        "SELECT * FROM read_csv_auto('/tmp/x.csv')",
        "SELECT * FROM listings_clean; SELECT * FROM poi",
        "COPY listings_clean TO '/tmp/x.csv'",
        "ATTACH 'other.db' AS other",
        "SELECT * FROM main.listings_clean",
        "PRAGMA database_list",
    ]
    rows=[]
    for i,sql in enumerate(accepted):
        try: validate_select_sql(sql); passed=True
        except Exception: passed=False
        rows.append({"id":f"accept_{i+1}","expected":"accept","passed":passed})
    for i,sql in enumerate(rejected):
        try: validate_select_sql(sql); passed=False
        except SQLValidationError: passed=True
        rows.append({"id":f"reject_{i+1}","expected":"reject","passed":passed})
    return rows


def main():
    scenario=evaluate_scenarios()
    sql=evaluate_sql_boundary()
    report={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "data":metadata(),
        "deterministic":{
            "end_to_end":{"passed":sum(x["passed"] for x in scenario),"total":len(scenario),"cases":scenario},
            "sql_boundary":{"passed":sum(x["passed"] for x in sql),"total":len(sql),"cases":sql},
        },
        "llm": saved_llm_metrics(),
    }
    out=ROOT/"evaluation/latest_report.json"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if any(not x["passed"] for x in scenario+sql): raise SystemExit(1)


if __name__=="__main__": main()
