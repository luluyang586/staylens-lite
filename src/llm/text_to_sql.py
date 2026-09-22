"""Live Text-to-SQL, explicit offline examples, validated execution."""
import json
from dataclasses import dataclass
import pandas as pd
from src.config import ROOT
from src.database.connection import schema_map
from src.database.sql_validator import execute_sql
from src.llm.client import complete_json

SQL_RESPONSE_SCHEMA={
    "type":"object",
    "properties":{
        "status":{"type":"string","enum":["supported","unsupported"]},
        "sql":{"anyOf":[{"type":"string"},{"type":"null"}]},
        "reason":{"anyOf":[{"type":"string"},{"type":"null"}]},
    },
    "required":["status","sql","reason"],
    "additionalProperties":False,
}
EXAMPLES={
"各区域房源数量与基础价格中位数":"SELECT neighbourhood,COUNT(*) AS listing_count,MEDIAN(base_price_aud) AS median_price_aud FROM listings_clean GROUP BY neighbourhood ORDER BY listing_count DESC",
"房型供给与基础价格":"SELECT room_type,COUNT(*) AS listing_count,MEDIAN(base_price_aud) AS median_price_aud FROM listings_clean GROUP BY room_type",
"各区域超赞房东占比":"SELECT neighbourhood,AVG(CASE WHEN host_is_superhost THEN 1.0 ELSE 0 END) AS superhost_rate,COUNT(*) AS n FROM listings_clean GROUP BY neighbourhood",
"至少10个有效评分房源的区域排名":"SELECT neighbourhood,AVG(rating_5) AS avg_rating,COUNT(*) AS n FROM listings_clean WHERE rating_5 IS NOT NULL GROUP BY neighbourhood HAVING COUNT(*)>=10 ORDER BY avg_rating DESC"}
@dataclass
class AnalysisResult:
    status:str
    sql:str|None=None
    data:pd.DataFrame|None=None
    reason:str|None=None
    generation_mode:str="unknown"
    attempt_count:int=1
def run_analysis(question,use_llm=False):
    if not use_llm:
        try:
            if question not in EXAMPLES:return AnalysisResult("unsupported",reason="未启用LLM：仅能执行明确列出的示例分析。",generation_mode="fixed_example")
            safe,df=execute_sql(EXAMPLES[question])
            return AnalysisResult("ok",sql=safe,data=df,generation_mode="fixed_example")
        except Exception as e:
            return AnalysisResult("error",reason=type(e).__name__+": "+str(e),generation_mode="fixed_example")

    approved_schema=schema_map()
    system=(ROOT/"prompts/text_to_sql.txt").read_text()+"\nApproved database schema:\n"+json.dumps(approved_schema)
    context={"question":question}
    last_reason="Unknown generation failure"
    for attempt in range(1,3):
        try:
            payload=complete_json(
                system,
                json.dumps(context,ensure_ascii=False),
                json_schema=SQL_RESPONSE_SCHEMA,
                schema_name="staylens_text_to_sql",
            )
            if payload.get("status")!="supported":
                last_reason=payload.get("reason") or "数据不足"
                if attempt==1:
                    context["validation_feedback"]=(
                        "Re-check the approved schema field by field. Derived metrics and output aliases do not "
                        "need to exist as source columns. Return unsupported only when the required raw data is "
                        "genuinely absent; otherwise generate one SELECT query."
                    )
                    continue
                return AnalysisResult("unsupported",reason=last_reason,generation_mode="live_llm",attempt_count=attempt)
            sql=payload.get("sql")
            if not isinstance(sql,str) or not sql.strip():
                raise ValueError("Supported response must contain non-empty SQL")
            safe,df=execute_sql(sql)
            return AnalysisResult("ok",sql=safe,data=df,generation_mode="live_llm",attempt_count=attempt)
        except Exception as e:
            last_reason=type(e).__name__+": "+str(e)
            if attempt==1:
                context["validation_feedback"]=(
                    "The previous SQL was rejected or failed: "+last_reason+
                    ". Return exactly one DuckDB SELECT statement, with no prose and no second statement. "
                    "Repair it against the approved schema."
                )
                continue
    return AnalysisResult("error",reason=last_reason,generation_mode="live_llm",attempt_count=2)
