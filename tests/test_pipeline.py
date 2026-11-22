from rag.pipeline import get_ayurvedic_response
from models.llm import validate_generation


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits

    def retrieve(self, query, top_k=5):
        return self.hits[:top_k]


def sample_hit(distance=0.2):
    return {
        "id": "passage-1",
        "text": "The text names Amlapitta and describes a burning sensation.",
        "metadata": {"book_name": "Charaka Samhita", "page_number": 8},
        "distance": distance,
    }


def test_empty_retrieval_abstains_and_reports_symptoms():
    result = get_ayurvedic_response("burning and nausea", retriever=FakeRetriever([]), llm_mode="mock")
    assert result["possible_concepts"] == []
    assert result["evidence_sufficient"] is False
    assert "not found" in result["evidence_summary"].lower()
    assert "burning" in result["extracted_symptoms"]


def test_mock_mode_does_not_claim_model_generation():
    result = get_ayurvedic_response("burning stomach", retriever=FakeRetriever([sample_hit()]), llm_mode="mock")
    assert result["mode"] == "mock"
    assert result["possible_concepts"] == []
    assert "Mock mode" in result["evidence_summary"]


def test_low_relevance_result_is_filtered_out():
    result = get_ayurvedic_response("unrelated question", retriever=FakeRetriever([sample_hit(distance=0.99)]), llm_mode="mock")
    assert result["passages"] == []
    assert result["evidence_sufficient"] is False


def test_ayurparam_generation_requires_valid_passage_id():
    raw = '{"extracted_symptoms":["burning"],"possible_concepts":[{"name":"Amlapitta","reason":"Named in context","supporting_passage_ids":["P1","P22"]}],"evidence_summary":"The passage mentions the term.","limitations":"Educational only."}'
    import pytest
    with pytest.raises(ValueError):
        validate_generation(raw, [sample_hit()])


def test_unsafe_medication_advice_is_suppressed():
    raw = '{"extracted_symptoms":[],"possible_concepts":[],"evidence_summary":"Take 20 mg medicine daily.","limitations":""}'
    result = validate_generation(raw, [sample_hit()])
    assert result["possible_concepts"] == []
    assert "withheld" in result["evidence_summary"]


def test_urgent_care_warning_is_triggered():
    result = get_ayurvedic_response("I have chest pain and trouble breathing", retriever=FakeRetriever([]), llm_mode="mock")
    assert result["urgent_care"] is True
