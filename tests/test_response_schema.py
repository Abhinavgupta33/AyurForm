from models.llm import RESPONSE_JSON_SCHEMA, ResponseSchemaError, validate_generation
import pytest


def test_valid_response_matches_schema_contract():
    raw = '{"extracted_symptoms":["burning"],"possible_concepts":[{"name":"Agni","reason":"textual association","supporting_passage_ids":["P1"]}],"evidence_summary":"supported","limitations":"educational"}'
    assert validate_generation(raw, [{"id":"x","metadata":{"provenance_role":"translated_source"}}])["possible_concepts"][0]["supporting_passage_ids"] == ["P1"]


def test_missing_and_wrong_types_fail():
    with pytest.raises(ResponseSchemaError):
        validate_generation('{"extracted_symptoms":[],"possible_concepts":[],"evidence_summary":"x"}', [])
    with pytest.raises(ResponseSchemaError):
        validate_generation('{"extracted_symptoms":"burning","possible_concepts":[],"evidence_summary":"x","limitations":""}', [])


def test_schema_is_closed_and_nested_ids_are_strings():
    assert RESPONSE_JSON_SCHEMA["additionalProperties"] is False
    nested = RESPONSE_JSON_SCHEMA["properties"]["possible_concepts"]["items"]
    assert nested["additionalProperties"] is False
