import httpx
import pytest

from models.llm import OllamaLLM, parse_structured_response, validate_generation


def test_malformed_json_logs_sanitized_shape(caplog):
    with caplog.at_level("WARNING", logger="ayursutra.rag"):
        with pytest.raises(ValueError):
            parse_structured_response("private symptom text without json", correlation="abc")
    message = " ".join(record.getMessage() for record in caplog.records)
    assert "abc" in message and "response_length" in message
    assert "private symptom" not in message


def test_schema_ids_and_safety_rejections_are_logged(caplog):
    with caplog.at_level("WARNING", logger="ayursutra.rag"):
        with pytest.raises(ValueError):
            validate_generation('{"extracted_symptoms":[],"possible_concepts":[{"name":"x","reason":"r","supporting_passage_ids":["P9"]}],"evidence_summary":"","limitations":""}', [{"id":"x","metadata":{"provenance_role":"translated_source"}}], correlation="xyz")
    message = " ".join(record.getMessage() for record in caplog.records)
    assert "invalid_citation_count" in message and "xyz" in message
    caplog.clear()
    with caplog.at_level("WARNING", logger="ayursutra.rag"):
        validate_generation('{"extracted_symptoms":[],"possible_concepts":[],"evidence_summary":"take 10 mg medicine","limitations":""}', [{"id":"x"}], correlation="xyz")
    assert "unsafe_advice" in " ".join(r.getMessage() for r in caplog.records)


def test_ollama_http_500_logs_status(monkeypatch, caplog):
    class Response:
        status_code = 500
        def raise_for_status(self): raise httpx.HTTPStatusError("server", request=None, response=None)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with caplog.at_level("INFO", logger="ayursutra.rag"):
        with pytest.raises(Exception): OllamaLLM().generate("x")
    assert "status=500" in " ".join(r.getMessage() for r in caplog.records)
