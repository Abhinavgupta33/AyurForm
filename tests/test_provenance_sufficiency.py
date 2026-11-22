import rag.pipeline as pipeline


class Retriever:
    def __init__(self, role): self.role = role
    def retrieve(self, query, top_k=5):
        return [{"id": "x", "text": "evidence", "metadata": {"provenance_role": self.role}, "distance": .1}]


class LLM:
    def generate(self, prompt, max_new_tokens=350):
        return '{"extracted_symptoms":[],"possible_concepts":[],"evidence_summary":"supported","limitations":""}'


def test_editorial_only_is_not_sufficient():
    result = pipeline.get_ayurvedic_response("agni", retriever=Retriever("editor_note"), llm=LLM(), llm_mode="ollama")
    assert result["evidence_sufficient"] is False


def test_translated_source_is_sufficient_when_model_has_evidence():
    result = pipeline.get_ayurvedic_response("agni", retriever=Retriever("translated_source"), llm=LLM(), llm_mode="ollama")
    assert result["evidence_sufficient"] is True
