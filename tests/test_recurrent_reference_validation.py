import pytest
from models.llm import parse_structured_response, validate_generation, ResponseSchemaError
import rag.pipeline as pipeline


def test_truncated_or_prose_output_is_rejected():
    with pytest.raises((ValueError,)):  # malformed model output must never become a citation
        parse_structured_response('{"possible_concepts": [')
    with pytest.raises(ValueError):
        parse_structured_response("clinical prose without JSON")


def test_missing_and_wrong_schema_fields_are_rejected():
    with pytest.raises(ResponseSchemaError):
        validate_generation('{"source_id":"fake"}', [], correlation="schema")
    with pytest.raises(ResponseSchemaError):
        validate_generation('{"extracted_symptoms":"burning","possible_concepts":[],"evidence_summary":"x","limitations":""}', [], correlation="schema")


def test_ollama_retries_invalid_json_but_still_validates(monkeypatch):
    class Retriever:
        def retrieve(self, query, top_k=5):
            return [{"id": "p", "text": "evidence", "metadata": {}, "distance": 0.1}]
    class LLM:
        calls = 0
        def generate(self, prompt, max_new_tokens=350):
            self.calls += 1
            return "prose" if self.calls == 1 else '{"extracted_symptoms":[],"possible_concepts":[],"evidence_summary":"insufficient","limitations":""}'
    llm = LLM()
    result = pipeline.get_ayurvedic_response("burning", retriever=Retriever(), llm=llm, llm_mode="ollama")
    assert llm.calls == 2
    assert result["mode"] == "ollama"
