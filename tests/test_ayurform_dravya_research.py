import json

import pytest

import ayurform_dravya_research as module
from models.llm import OllamaError, ResponseSchemaError


def passage(text="Pippali is described in the source.", *, role="translated_source", distance=0.25, **metadata):
    return {
        "id": "stable-passage-pippali-542",
        "text": text,
        "distance": distance,
        "metadata": {
            "provenance_role": role,
            "usage_scope": "development_only",
            "rights_status": "pending",
            "source_title": "Test source",
            "chapter_reference": "Sutra 1",
            "page_number": 542,
            **metadata,
        },
    }


def test_valid_natural_language_answer_and_evidence_metadata(monkeypatch):
    hit = passage()
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    monkeypatch.setattr(module, "KNOWLEDGE_MODE", "development")
    monkeypatch.setattr(module, "select_evidence", lambda *a, **k: [hit])

    class FakeAyurParam:
        model_name = "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"

        def generate(self, prompt, max_new_tokens, system, format_schema):
            assert "Pippali" in prompt
            assert "Do not include citation markers" in system
            assert format_schema is False
            return "## Source description\n\nThe supplied passage describes Pippali. Its listed qualities are limited to the excerpt."

    result = module.build_dravya_answer("Pippali", FakeAyurParam())
    assert result["mode"] == "grounded"
    assert result["model"] == "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"
    assert result["answer"].startswith("## Source description")
    assert result["citation_ids"] == ["P1"]
    assert result["evidence"][0]["passage_id"] == "stable-passage-pippali-542"
    assert result["evidence"][0]["page"] == 542
    assert result["evidence"][0]["metadata"]["rights_status"] == "pending"
    assert result["evidence"][0]["metadata"]["usage_scope"] == "development_only"


def test_empty_natural_response_is_rejected():
    with pytest.raises(ResponseSchemaError, match="empty"):
        module.validate_natural_answer("  \n", [passage()])


@pytest.mark.parametrize("name", ["Tulsi", "Ashwagandha", "Pippali"])
def test_direct_ayurparam_generates_natural_answer_for_requested_name(monkeypatch, name):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    monkeypatch.setattr(module, "select_evidence", lambda *a, **k: pytest.fail("Direct mode must not retrieve evidence"))

    class Model:
        model_name = "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"
        def generate(self, prompt, max_new_tokens, system, format_schema):
            assert name in prompt
            assert "not verified against retrieved classical sources" in system
            assert "dosage" in system
            assert max_new_tokens == 1100
            assert "Sanskrit Names and Identity" in system
            assert "500–800 words" in system
            assert format_schema is False
            return (f"## Introduction\n\n{name} is the requested Dravya.\n\n"
                    "## Ayurvedic Properties\n\nThe model describes available properties cautiously.\n\n"
                    "## Summary\n\nUncertain details remain unverified.")

    result = module.build_direct_dravya_answer(name, Model())
    assert result["mode"] == "direct"
    assert result["canonical_name"] == name
    assert result["model"] == "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"
    assert result["answer"].startswith("## Introduction")
    assert result["evidence"] == []
    assert result["citation_ids"] == []
    assert "Not verified" in result["limitations"]


def test_direct_ayurparam_rejects_empty_response(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    class Model:
        def generate(self, *args, **kwargs): return "  "
    with pytest.raises(ResponseSchemaError, match="empty"):
        module.build_direct_dravya_answer("Tulsi", Model())


@pytest.mark.parametrize("output", [
    '{"rasa":"unknown"}',
    "```json\n{}\n```",
    "Tulsi is mentioned in Su1#41 and passage P99.",
    "Charaka Samhita describes Tulsi in detail.",
])
def test_direct_ayurparam_rejects_structured_or_fabricated_citations(monkeypatch, output):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    class Model:
        def generate(self, *args, **kwargs): return output
    with pytest.raises(ResponseSchemaError):
        module.build_direct_dravya_answer("Tulsi", Model())


def test_direct_ayurparam_rejects_unstructured_or_runaway_output():
    with pytest.raises(ResponseSchemaError, match="Markdown sections"):
        module.validate_direct_answer("A single unstructured paragraph.")
    verbose = "## A\n\n" + ("word " * 951) + "\n\n## B\n\nText.\n\n## Summary\n\nText."
    with pytest.raises(ResponseSchemaError, match="length limit"):
        module.validate_direct_answer(verbose)


def test_direct_ayurparam_retries_format_once_and_revalidates(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    class Model:
        model_name = "AyurParam"
        def __init__(self): self.calls = 0
        def generate(self, prompt, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return "A single paragraph without requested sections."
            assert "Formatting correction" in prompt
            return "## Introduction\n\nOverview.\n\n## Properties\n\nUncertain.\n\n## Summary\n\nNo unsupported details."
    model = Model()
    result = module.build_direct_dravya_answer("Tulsi", model)
    assert model.calls == 2
    assert result["answer"].startswith("## Introduction")


@pytest.mark.parametrize("error", [
    OllamaError("Ollama is unavailable"),
    OllamaError("Ollama request timed out."),
])
def test_direct_ayurparam_surfaces_unavailable_and_timeout_without_fallback(monkeypatch, error):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    class Model:
        def generate(self, *args, **kwargs): raise error
    with pytest.raises(OllamaError):
        module.build_direct_dravya_answer("Tulsi", Model())


def test_direct_ayurparam_rejects_mock_mode(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "mock")
    with pytest.raises(RuntimeError, match="Mock mode"):
        module.build_direct_dravya_answer("Tulsi", object())


def test_metadata_dump_instead_of_answer_is_rejected():
    with pytest.raises(ResponseSchemaError, match="metadata"):
        module.validate_natural_answer("usage_scope: development_only", [passage()])


def test_medical_claim_absent_from_source_is_rejected():
    with pytest.raises(ResponseSchemaError, match="medical claim absent"):
        module.validate_natural_answer(
            "Pippali treats respiratory ailments.", [passage()]
        )


@pytest.mark.parametrize(("answer", "reason"), [
    ("P99 supports this claim.", "not retrieved"),
    ("The text says Su99#999.", "absent from retrieved passages"),
])
def test_fabricated_citations_are_rejected(answer, reason):
    with pytest.raises(ResponseSchemaError, match=reason):
        module.validate_natural_answer(answer, [passage()])


def test_prompt_local_passage_marker_becomes_link_to_real_evidence():
    assert module.validate_natural_answer("This is described in P1.", [passage()]) == "This is described in [P1](#source-P1)."


def test_classical_reference_must_exist_in_retrieved_excerpt_and_links_to_passage():
    excerpt = passage("Pippali appears in Vi1#15 in this excerpt.")
    assert "[P1](#source-P1)" in module.validate_natural_answer("See Vi1#15.", [excerpt])


def test_model_claiming_subject_absent_is_retried_and_corrected(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    monkeypatch.setattr(module, "KNOWLEDGE_MODE", "development")
    monkeypatch.setattr(module, "select_evidence", lambda *a, **k: [passage()])

    class Model:
        model_name = "AyurParam"
        def __init__(self): self.calls = 0
        def generate(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1: return "The passage does not mention Pippali."
            return "The passage identifies Pippali and describes it in the supplied text."

    model = Model()
    result = module.build_dravya_answer("Pippali", model)
    assert model.calls == 2
    assert result["mode"] == "grounded"
    assert "identifies Pippali" in result["answer"]


def test_ollama_unavailable_is_not_replaced_with_mock(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    monkeypatch.setattr(module, "KNOWLEDGE_MODE", "development")
    monkeypatch.setattr(module, "select_evidence", lambda *a, **k: [passage()])

    class Unavailable:
        def generate(self, *args, **kwargs):
            raise OllamaError("Ollama request timed out.")

    with pytest.raises(OllamaError, match="timed out"):
        module.build_dravya_answer("Pippali", Unavailable())


def test_no_directly_relevant_passages_abstains_without_model_call(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    monkeypatch.setattr(module, "KNOWLEDGE_MODE", "development")
    monkeypatch.setattr(module, "select_evidence", lambda *a, **k: [passage("General herbal discussion.")])

    class NeverCall:
        def generate(self, *args, **kwargs):
            pytest.fail("Model must not be called without direct-name eligible evidence")

    result = module.build_dravya_answer("Pippali", NeverCall())
    assert result["mode"] == "abstention"
    assert result["answer"] == ""
    assert result["evidence"] == []
    assert "directly identifies" in result["limitations"]


def test_no_retrieved_passages_abstains(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    monkeypatch.setattr(module, "select_evidence", lambda *a, **k: [])
    result = module.build_dravya_answer("Pippali", object())
    assert result["mode"] == "abstention"
    assert result["citation_ids"] == []


def test_production_rights_and_relevance_filters_remain_enforced(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "ollama")
    monkeypatch.setattr(module, "KNOWLEDGE_MODE", "production")
    hits = [
        passage(usage_scope="development_only", rights_status="licensed"),
        passage(usage_scope="production", rights_status="pending"),
        passage(usage_scope="production", rights_status="licensed", distance=0.99),
    ]
    monkeypatch.setattr(module, "select_evidence", lambda *a, **k: hits)

    class NeverCall:
        def generate(self, *args, **kwargs):
            pytest.fail("Model must not receive rights-ineligible evidence")

    result = module.build_dravya_answer("Pippali", NeverCall())
    assert result["mode"] == "abstention"
    assert result["evidence"] == []


def test_mock_mode_is_identified_and_never_generates(monkeypatch):
    monkeypatch.setattr(module, "model_mode", lambda: "mock")
    with pytest.raises(RuntimeError, match="Mock mode"):
        module.build_dravya_answer("Pippali", object())


def test_legacy_pending_draft_functions_remain_user_scoped(tmp_path):
    old = {"mode": "grounded", "claims": [{"field": "rasa"}], "evidence": [{"passage_id": "p"}]}
    saved = module.save_pending_draft(old, "reviewer@example.org", owner_id=5, draft_dir=tmp_path)
    assert json.loads(saved.read_text(encoding="utf-8"))["review_status"] == "pending"
    assert module.list_user_drafts("reviewer@example.org", owner_id=5, draft_dir=tmp_path)
    assert not module.list_user_drafts("other@example.org", owner_id=6, draft_dir=tmp_path)
