import hashlib
import json
from pathlib import Path

import pytest

from src.config import ROOT
from src.database.connection import database_exists
from src.database.sql_validator import execute_sql
from src.llm.review_tagger import validate_tags
from src.models.intent import StayIntent


def load(name):
    return json.loads((ROOT/"evaluation"/name).read_text())


def test_final_v2_intent_set_is_stratified_and_well_formed():
    cases=load("intent_final_v2_cases.json")
    assert len(cases)==100
    assert len({case["id"] for case in cases})==100
    assert len({case["input"] for case in cases})==100
    assert {case["category"] for case in cases}=={
        "complete_core","missing_or_ambiguous","budget_semantics","date_and_duration",
        "location_entities","preferences","bilingual_colloquial","instruction_robustness",
    }
    fields=set(StayIntent.model_fields)
    assert all(set(case["expected"]).issubset(fields) for case in cases)


def test_final_v2_sql_set_has_supported_and_unsupported_contracts():
    cases=load("sql_final_v2_cases.json")
    assert len(cases)==50
    assert len({case["id"] for case in cases})==50
    assert sum(case["status"]=="supported" for case in cases)==38
    assert sum(case["status"]=="unsupported" for case in cases)==12
    assert all(bool(case["reference_sql"])==(case["status"]=="supported") for case in cases)


def test_final_v2_manifest_hashes_match_files():
    manifest=load("final_v2_manifest.json")
    assert manifest["status"]=="frozen_before_live_run"
    for item in manifest["datasets"]:
        raw=(ROOT/"evaluation"/item["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==item["sha256"]
    for name,expected_hash in manifest["prompt_sha256_at_freeze"].items():
        assert hashlib.sha256((ROOT/"prompts"/name).read_bytes()).hexdigest()==expected_hash


@pytest.mark.skipif(not database_exists(),reason="real snapshot database not built")
def test_all_supported_final_sql_references_execute_with_contract_columns():
    for case in load("sql_final_v2_cases.json"):
        if case["status"]!="supported":
            continue
        _,frame=execute_sql(case["reference_sql"])
        assert set(case["expected_columns"]).issubset(frame.columns),case["id"]


def test_review_reference_set_and_manifest_are_frozen_and_evidence_is_exact():
    cases=load("review_reference_v1.json")
    manifest=load("review_reference_v1_manifest.json")
    assert len(cases)==55
    assert sum(len(x["expected_tags"]) for x in cases)==138
    raw=(ROOT/"evaluation/review_reference_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest()==manifest["dataset_sha256"]
    prompt=(ROOT/"prompts/review_tagger.txt").read_bytes()
    assert hashlib.sha256(prompt).hexdigest()==manifest["prompt_sha256_at_freeze"]
    for case in cases:
        validate_tags({"reviews":[{"review_id":case["review_id"],"tags":case["expected_tags"]}]},[case])
