import rag.pipeline as pipeline


class Retriever:
    def retrieve(self, query, top_k=5):
        return [{"id": "p1", "text": "A supported passage", "metadata": {}, "distance": 0.1}]


class FakeLLM:
    def generate(self, prompt, max_new_tokens=350):
        return '{"extracted_symptoms":[],"possible_concepts":[],"evidence_summary":"ok","limitations":""}'


def test_provider_ollama_is_selected_when_mode_unset(monkeypatch):
    monkeypatch.setattr(pipeline, "LLM_MODE", "")
    monkeypatch.setattr(pipeline, "LLM_PROVIDER", "ollama")
    created = []
    monkeypatch.setattr(pipeline, "OllamaLLM", lambda: created.append(True) or FakeLLM())
    result = pipeline.get_ayurvedic_response("burning", retriever=Retriever())
    assert created == [True]
    assert result["mode"] == "ollama"


def test_explicit_mock_mode_wins_over_provider(monkeypatch):
    monkeypatch.setattr(pipeline, "LLM_MODE", "mock")
    monkeypatch.setattr(pipeline, "LLM_PROVIDER", "ollama")
    result = pipeline.get_ayurvedic_response("burning", retriever=Retriever())
    assert result["mode"] == "mock"
