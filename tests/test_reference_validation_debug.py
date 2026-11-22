import pytest
from models.llm import parse_structured_response, build_prompt


def test_non_json_model_output_is_rejected_without_fabricating_reference():
    with pytest.raises(ValueError, match="no structured JSON"):
        parse_structured_response("The symptoms may relate to digestion. Consult a doctor.")


def test_generation_prompt_bounds_context_for_local_model():
    passages = [{"text": "x" * 5000, "metadata": {"pdf_page": i}} for i in range(5)]
    assert len(build_prompt("query", passages)) < 10000
