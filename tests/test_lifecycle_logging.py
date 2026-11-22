import rag.pipeline as pipeline


class Retriever:
    def __init__(self, hits): self.hits = hits
    def retrieve(self, query, top_k=5): return self.hits


class LLM:
    def __init__(self, text): self.text = text
    def generate(self, prompt, max_new_tokens=350): return self.text


def hit(role="translated_source"):
    return {"id":"x", "text":"evidence", "metadata":{"provenance_role": role}, "distance":.1}


def valid():
    return '{"extracted_symptoms":[],"possible_concepts":[],"evidence_summary":"supported","limitations":""}'


def test_lifecycle_logs_final_abstention_and_counts(caplog):
    with caplog.at_level("INFO", logger="ayursutra.rag"):
        result = pipeline.get_ayurvedic_response("agni", retriever=Retriever([hit("editor_note"), hit("unknown")]), llm=LLM(valid()), llm_mode="ollama")
    text = " ".join(r.getMessage() for r in caplog.records)
    assert result["evidence_sufficient"] is False
    assert "stage=start" in text and "provenance_counts" in text and "outcome=abstention" in text


def test_lifecycle_logs_technical_failure(caplog):
    class Broken:
        def retrieve(self, query, top_k=5): raise RuntimeError("backend")
    with caplog.at_level("ERROR", logger="ayursutra.rag"):
        try: pipeline.get_ayurvedic_response("x", retriever=Broken())
        except RuntimeError: pass
    assert "outcome=technical_failure" in " ".join(r.getMessage() for r in caplog.records)
