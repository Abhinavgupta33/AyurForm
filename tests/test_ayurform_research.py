import json

import pytest

import ayurform_research as research_module
from models.llm import OllamaError, OllamaIncompleteResponseError, ResponseSchemaError
from ayurform_research import CitationValidationError
from rag.retriever import ChromaRetrievalError
from config import (
    AYURSUTRA_RESEARCH_CONTEXT_MAX_CHARS,
    AYURSUTRA_RESEARCH_NUM_CTX,
    AYURSUTRA_RESEARCH_NUM_PREDICT,
)


def passage(
    stable_id="stable-passage-1",
    text="The translated excerpt describes Triphala in a traditional context.",
    *,
    role="translated_source",
    distance=0.2,
    usage_scope="production",
    rights_status="licensed",
    review_status="approved",
    source_id="source-1",
    **extra,
):
    return {
        "id": stable_id,
        "text": text,
        "distance": distance,
        "metadata": {
            "source_id": source_id,
            "source_title": "Verified source title",
            "translator": "Verified translator",
            "chapter_reference": "Sutra section 1",
            "page_number": 12,
            "verse_number": "4",
            "provenance_role": role,
            "usage_scope": usage_scope,
            "rights_status": rights_status,
            "review_status": review_status,
            **extra,
        },
    }


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def retrieve(self, query, *, top_k, request_id=None):
        self.calls.append((query, top_k))
        return self.hits[:top_k]


class FakeModel:
    model_name = "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"

    def __init__(self, response=None, error=None):
        self.response = response or "## Research Overview\n\nThe excerpt describes a traditional account [P1]."
        self.error = error
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        return self.response


def _ollama(monkeypatch, knowledge_mode="production"):
    monkeypatch.setattr(research_module, "LLM_MODE", "ollama")
    monkeypatch.setattr(research_module, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(research_module, "KNOWLEDGE_MODE", knowledge_mode)
    monkeypatch.setattr(research_module, "_load_registry_entries", lambda _mode: {})


def test_successful_retrieval_and_generation_uses_eligible_passages_and_exact_citations(monkeypatch):
    _ollama(monkeypatch)
    hit = passage()
    retriever = FakeRetriever([hit])
    model = FakeModel()

    result = research_module.research("What does the source say about Triphala?", model, retriever=retriever, request_id="research-1")

    assert result["mode"] == "grounded"
    assert result["answer"].startswith("## Research Overview")
    assert result["answer"] == model.response
    assert result["citation_validation_status"] == "passed"
    assert result["source_verified"] is True
    assert result["evidence"][0]["passage_id"] == hit["id"]
    assert result["evidence"][0]["page"] == 12
    assert result["evidence"][0]["chapter"] == "Sutra section 1"
    assert result["evidence"][0]["translator"] == "Verified translator"
    assert result["request_id"] == "research-1"
    prompt, options = model.calls[0]
    assert "[P1]" in prompt and hit["text"] in prompt
    assert "[P2]" not in prompt
    assert options["request_id"] == "research-1"
    assert options["format_schema"] is False
    assert options["max_new_tokens"] == AYURSUTRA_RESEARCH_NUM_PREDICT == 800
    assert options["num_ctx"] == AYURSUTRA_RESEARCH_NUM_CTX == 4096
    assert options["reject_truncated"] is True
    assert "Every factual sentence must end" in options["system"]
    assert "concise academic answer" in options["system"]
    assert "Direct Answer" in options["system"]
    assert retriever.calls == [("What does the source say about Triphala?", research_module.TOP_K * 3)]


def test_empty_corpus_and_no_matching_evidence_abstain_without_model_call(monkeypatch):
    _ollama(monkeypatch)
    for hits in ([], [passage(distance=0.99)]):
        model = FakeModel()
        result = research_module.research("Explain Triphala", model, retriever=FakeRetriever(hits))
        assert result["mode"] == "abstention"
        assert result["answer"] is None
        assert result["limitations"] == research_module.NO_EVIDENCE_MESSAGE
        assert not model.calls


def test_only_translated_source_evidence_is_eligible(monkeypatch):
    _ollama(monkeypatch)
    hits = [
        passage("editor", role="editor_note"),
        passage("unknown", role="unknown"),
        passage("translator-note", role="translator_note"),
    ]
    result = research_module.research("Explain Triphala", FakeModel(), retriever=FakeRetriever(hits))
    assert result["evidence"] == []
    assert result["retrieval"]["excluded"]["provenance"] == 3


def test_rights_pending_and_unapproved_source_rejected_in_production(monkeypatch):
    _ollama(monkeypatch, "production")
    hits = [
        passage("pending-rights", rights_status="pending"),
        passage("unverified-rights", rights_status="unverified"),
        passage("pending-review", review_status="pending"),
        passage("dev-scope", usage_scope="development_only"),
    ]
    result = research_module.research("Explain Triphala", FakeModel(), retriever=FakeRetriever(hits))
    assert result["mode"] == "abstention"
    assert result["evidence"] == []
    excluded = result["retrieval"]["excluded"]
    assert excluded["rights"] == 2
    assert excluded["review_status"] == 1
    assert excluded["usage_scope"] == 1


def test_development_evidence_is_explicitly_labelled_and_rights_are_displayed(monkeypatch):
    _ollama(monkeypatch, "development")
    dev_hit = passage(
        "dev-passage", usage_scope="development_only", rights_status="unverified",
        review_status="inspected_not_production_approved",
    )
    result = research_module.research("What is recorded?", FakeModel(), retriever=FakeRetriever([dev_hit]))
    assert result["mode"] == "grounded"
    assert result["development_only"] is True
    assert "not production-approved" in result["development_warning"]
    assert result["evidence"][0]["rights_status"] == "unverified"
    assert result["evidence"][0]["usage_scope"] == "development_only"


def test_registry_metadata_is_attached_to_development_passage(monkeypatch):
    _ollama(monkeypatch, "development")
    monkeypatch.setattr(research_module, "_load_registry_entries", lambda _mode: {
        "source-1": {
            "source_id": "source-1", "title": "Registry title", "rights_status": "unverified",
            "review_status": "inspected_not_production_approved", "usage_scope": "development_only",
            "translator": "Registry translator",
        }
    })
    hit = passage("registry-hit", usage_scope="development_only", rights_status="", review_status="", source_id="source-1")
    selected, _ = research_module.select_research_evidence("query", retriever=FakeRetriever([hit]))
    assert selected[0]["metadata"]["rights_status"] == "unverified"
    assert selected[0]["metadata"]["source_title"] == "Registry title"
    assert selected[0]["metadata"]["translator"] == "Registry translator"


def test_citations_must_match_prompt_passages_and_cover_each_claim():
    hit = passage()
    assert "[P1](#source-P1)" in research_module.validate_research_answer(
        "## Overview\n\nThe excerpt records a traditional description [P1].", [hit]
    )
    with pytest.raises(CitationValidationError, match="not retrieved") as unknown:
        research_module.validate_research_answer("A claim [P9].", [hit])
    assert unknown.value.category == "citation_not_retrieved"
    with pytest.raises(CitationValidationError, match="did not include an exact passage citation") as missing:
        research_module.validate_research_answer("## Overview\n\nThis claim has no citation.", [hit])
    assert missing.value.category == "missing_citation"


def test_research_displays_original_answer_when_citation_validation_fails(monkeypatch, caplog):
    _ollama(monkeypatch)
    original = "## Research Overview\n\nOriginal **AyurParam** text with an invalid marker [P9]."
    result = research_module.research(
        "Explain the source", FakeModel(original), retriever=FakeRetriever([passage()]), request_id="display-invalid-cite",
    )
    assert result["answer"] == original
    assert result["mode"] == "unverified_answer"
    assert result["citation_validation_status"] == "failed"
    assert result["source_verified"] is False
    assert "category=citation_not_retrieved" in caplog.text
    assert "display-invalid-cite" in caplog.text


def test_hard_safety_rejection_still_blocks_answer_even_when_citation_is_missing(monkeypatch):
    _ollama(monkeypatch)
    unsafe = "Take two tablets daily for the condition."
    with pytest.raises(ResponseSchemaError, match="prohibited medical or hazardous"):
        research_module.research(
            "Explain the source", FakeModel(unsafe), retriever=FakeRetriever([passage()]), request_id="hard-safety-still-blocks",
        )


def test_incomplete_nonempty_generation_is_returned_only_as_incomplete(monkeypatch):
    _ollama(monkeypatch)
    partial = "## Direct answer\n\nThe retrieved passage describes an incomplete claim"
    model = FakeModel(error=OllamaIncompleteResponseError("truncated", response_text=partial, finish_reason="length"))
    result = research_module.research(
        "Explain the source", model, retriever=FakeRetriever([passage()]), request_id="partial-output",
    )
    assert result["answer"] == partial
    assert result["mode"] == "incomplete"
    assert result["answer_complete"] is False
    assert result["retrieval"]["finish_reason"] == "length"
    assert result["source_verified"] is False
    assert "incomplete" in result["limitations"]


def test_exact_request_local_ids_are_prompted_without_stable_ids_as_model_citations():
    left = passage("stable-source-a", "First complete evidence passage.")
    right = passage("stable-source-b", "Second complete evidence passage.")
    _system, prompt, included = research_module._make_prompt("Explain", [left, right])
    assert included == [left, right]
    assert "Allowed citation IDs for this request: [P1], [P2]." in prompt
    assert "Passage citation ID: [P1]" in prompt
    assert "Passage citation ID: [P2]" in prompt
    assert "stable-source-a" not in prompt
    assert "stable-source-b" not in prompt


def test_multiple_exact_valid_ids_resolve_to_their_request_evidence():
    passages = [passage("stable-a", "Evidence A."), passage("stable-b", "Evidence B.")]
    answer = research_module.validate_research_answer("The accounts differ [P1] [P2].", passages)
    assert "[P1](#source-P1)" in answer
    assert "[P2](#source-P2)" in answer


def test_case_variation_preserves_same_request_local_identifier():
    answer = research_module.validate_research_answer("A source-backed statement [p1].", [passage()])
    assert "[P1](#source-P1)" in answer


@pytest.mark.parametrize("raw", [
    "A claim [P 1].",
    "A claim (P1).",
    "A claim [P1, P2].",
    "A claim [P1](https://example.invalid/source).",
])
def test_noncanonical_citation_format_is_rejected_as_malformed(raw):
    with pytest.raises(CitationValidationError) as error:
        research_module.validate_research_answer(raw, [passage()])
    assert error.value.category == "malformed_citation"


def test_unknown_citation_identifier_is_distinct_from_request_evidence_miss():
    with pytest.raises(CitationValidationError) as error:
        research_module.validate_research_answer("A claim [X1].", [passage()])
    assert error.value.category == "unknown_citation_id"


def test_citation_from_another_request_is_rejected_without_replacement():
    earlier_request = [passage("old-a", "First evidence."), passage("old-b", "Second evidence.")]
    later_request = [passage("new-a", "New evidence.")]
    old_answer = "A claim [P2]."
    assert "[P2](#source-P2)" in research_module.validate_research_answer(old_answer, earlier_request)
    with pytest.raises(CitationValidationError) as error:
        research_module.validate_research_answer(old_answer, later_request)
    assert error.value.category == "citation_not_retrieved"
    assert "P1" not in str(error.value)


def test_no_citation_diagnostic_logs_ids_only_and_never_answer_text(monkeypatch, caplog):
    monkeypatch.setattr(research_module, "KNOWLEDGE_MODE", "development")
    passage_row = passage("charaka-dev-actual-42", "Source passage.", usage_scope="development_only", rights_status="unverified", review_status="pending")
    answer = "Private unsupported sentence with no citation."
    with pytest.raises(CitationValidationError) as error:
        research_module.validate_research_answer(answer, [passage_row], request_id="citation-log-1")
    assert error.value.category == "missing_citation"
    assert "correlation=citation-log-1" in caplog.text
    assert "retrieved_passage_ids=['charaka-dev-actual-42']" in caplog.text
    assert "generated_citation_ids=[]" in caplog.text
    assert "validated_citation_ids=[]" in caplog.text
    assert "missing_citation" in caplog.text
    assert answer not in caplog.text


def test_invalid_citation_diagnostic_records_generated_and_invalid_ids_only(monkeypatch, caplog):
    monkeypatch.setattr(research_module, "KNOWLEDGE_MODE", "development")
    answer = "A private factual sentence [P9]."
    with pytest.raises(CitationValidationError) as error:
        research_module.validate_research_answer(answer, [passage("stable-current")], request_id="invalid-id-log")
    assert error.value.category == "citation_not_retrieved"
    assert "generated_citation_ids=['P9']" in caplog.text
    assert "validated_citation_ids=[]" in caplog.text
    assert "not_retrieved_citation_ids=['P9']" in caplog.text
    assert "rejection_reason=citation_not_retrieved" in caplog.text
    assert answer not in caplog.text


def test_citation_diagnostics_are_development_only(monkeypatch, caplog):
    monkeypatch.setattr(research_module, "KNOWLEDGE_MODE", "production")
    assert "[P1](#source-P1)" in research_module.validate_research_answer("A factual sentence [P1].", [passage()])
    assert "stage=citation_validation" not in caplog.text


def test_concurrent_citation_diagnostics_remain_request_local(monkeypatch, caplog):
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(research_module, "KNOWLEDGE_MODE", "development")
    def validate(request_id, raw, evidence):
        try:
            return research_module.validate_research_answer(raw, evidence, request_id=request_id)
        except CitationValidationError as exc:
            return exc.category

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(validate, "concurrent-a", "A fact [P2].", [passage("a-1", "A."), passage("a-2", "B.")])
        second = pool.submit(validate, "concurrent-b", "A different fact [P2].", [passage("b-1", "C.")])
        assert "[P2](#source-P2)" in first.result()
        assert second.result() == "citation_not_retrieved"

    entries = [line for line in caplog.text.splitlines() if "stage=citation_validation" in line]
    assert any("correlation=concurrent-a" in line and "retrieved_passage_ids=['a-1', 'a-2']" in line and "validated_citation_ids=['P2']" in line for line in entries)
    assert any("correlation=concurrent-b" in line and "retrieved_passage_ids=['b-1']" in line and "not_retrieved_citation_ids=['P2']" in line for line in entries)


def test_each_citation_maps_to_actual_evidence_and_retrieved_passages_are_not_mixed(monkeypatch):
    _ollama(monkeypatch, "production")
    left = passage("source-a", "The passage records one account of Triphala.", source_title="Source A")
    right = passage("source-b", "Another passage records a different account of Triphala.", source_title="Source B")
    answer = "## Interpretation\n\nOne account is recorded [P1]. Another account differs [P2]."
    result = research_module.research("Compare accounts of Triphala", FakeModel(answer), retriever=FakeRetriever([left, right]))
    assert [row["passage_id"] for row in result["evidence"]] == ["source-a", "source-b"]
    assert [row["citation_id"] for row in result["evidence"]] == ["P1", "P2"]
    assert result["answer"] == answer


@pytest.mark.parametrize("unsafe", [
    "Take 2 grams daily [P1].",
    "This is clinically proven [P1].",
    "Use this for self-medication [P1].",
    "Diagnose the patient [P1].",
    "Purify mercury [P1].",
])
def test_unsafe_generated_instructions_and_clinical_claims_are_blocked(monkeypatch, unsafe):
    _ollama(monkeypatch)
    with pytest.raises(ResponseSchemaError):
        research_module.research("Explain the evidence", FakeModel(unsafe), retriever=FakeRetriever([passage()]))


def test_unsafe_patient_request_abstains_before_retrieval(monkeypatch):
    _ollama(monkeypatch)
    class NeverRetrieve:
        def retrieve(self, *args, **kwargs):
            pytest.fail("Unsafe patient-specific query must abstain before retrieval")

    result = research_module.research("What dose should I take?", FakeModel(), retriever=NeverRetrieve())
    assert result["mode"] == "safety_abstention"
    assert result["evidence"] == []
    assert result["answer"] is None


def test_no_mock_fallback_when_provider_is_mock(monkeypatch):
    monkeypatch.setattr(research_module, "LLM_MODE", "mock")
    monkeypatch.setattr(research_module, "LLM_PROVIDER", "ollama")
    class NeverRetrieve:
        def retrieve(self, *args, **kwargs):
            pytest.fail("Mock mode must not invoke retrieval or another model")
    with pytest.raises(RuntimeError, match="Mock mode"):
        research_module.research("What does the text say?", FakeModel(), retriever=NeverRetrieve())


def test_ollama_and_retrieval_failures_propagate_without_fallback(monkeypatch):
    _ollama(monkeypatch)
    with pytest.raises(OllamaError):
        research_module.research("Explain the source", FakeModel(error=OllamaError("offline")), retriever=FakeRetriever([passage()]))
    class BrokenRetriever:
        def retrieve(self, *args, **kwargs):
            raise RuntimeError("Chroma unavailable")
    with pytest.raises(ChromaRetrievalError, match="could not retrieve passages"):
        research_module.research("Explain the source", FakeModel(), retriever=BrokenRetriever())


def test_context_includes_complete_passages_or_excludes_them_without_truncation():
    oversized = passage("too-long", "x" * 7000)
    usable = passage("usable", "complete evidence text", source_title="Source B")
    system, prompt, included = research_module._make_prompt("Explain", [oversized, usable])
    assert "x" * 100 not in prompt
    assert "complete evidence text" in prompt
    assert "Source B" in prompt
    assert [item["id"] for item in included] == ["usable"]
    assert "[P1]" in prompt
    assert "usable" not in prompt


def test_context_budget_excludes_whole_passages_and_keeps_request_citations_exact(monkeypatch):
    monkeypatch.setattr(research_module, "AYURSUTRA_RESEARCH_CONTEXT_MAX_CHARS", 700)
    too_large = passage("too-large", "a" * 800)
    fits = passage("fits", "Short complete evidence.")
    _system, prompt, included = research_module._make_prompt("Explain", [too_large, fits])

    assert [item["id"] for item in included] == ["fits"]
    assert "a" * 100 not in prompt
    assert "Short complete evidence." in prompt
    assert "Allowed citation IDs for this request: [P1]." in prompt
    assert "[P2]" not in prompt
    assert AYURSUTRA_RESEARCH_CONTEXT_MAX_CHARS == 6500


def test_generation_uses_bounded_output_context_and_preserves_request_id(monkeypatch, caplog):
    _ollama(monkeypatch)
    model = FakeModel()
    result = research_module.research(
        "Explain the evidence", model, retriever=FakeRetriever([passage()]), request_id="token-budget-request",
    )
    assert result["mode"] == "grounded"
    _prompt, options = model.calls[0]
    assert options["request_id"] == "token-budget-request"
    assert options["max_new_tokens"] == 800
    assert options["num_ctx"] == 4096
    assert options["reject_truncated"] is True
    assert "output_token_limit=800 context_window=4096" in caplog.text


def test_exact_duplicate_passage_text_is_deduplicated_with_request_correlation(monkeypatch, caplog):
    _ollama(monkeypatch)
    first = passage("stable-a", "Same passage text.")
    duplicate = passage("stable-b", "  SAME   PASSAGE TEXT. ")
    result = research_module.research(
        "Explain the evidence", FakeModel(), retriever=FakeRetriever([first, duplicate]), request_id="dedupe-correlation",
    )
    assert [item["passage_id"] for item in result["evidence"]] == ["stable-a"]
    assert result["retrieval"]["excluded"]["duplicate"] == 1
    assert "correlation=dedupe-correlation" in caplog.text
    assert "query_embedding" not in caplog.text  # fake retriever does not generate embeddings


def test_pipeline_logs_context_generation_and_total_durations_without_query_text(monkeypatch, caplog):
    _ollama(monkeypatch)
    question = "private user research question content"
    research_module.research(question, FakeModel(), retriever=FakeRetriever([passage()]), request_id="duration-correlation")
    output = caplog.text
    assert "stage=retrieval_start correlation=duration-correlation" in output
    assert "stage=context_build correlation=duration-correlation" in output
    assert "stage=generation_start correlation=duration-correlation" in output
    assert "stage=final correlation=duration-correlation outcome=grounded_answer" in output
    assert "private user research question content" not in output


def test_empty_research_question_is_rejected():
    with pytest.raises(ValueError, match="required"):
        research_module.research("   ", FakeModel())


def test_intent_classification_preserves_existing_categories():
    assert research_module.classify_intent("What are the ingredients in a formulation?") == "formulation_ingredients"
    assert research_module.classify_intent("Compare two source descriptions") == "cross_source_comparison"
    assert research_module.classify_intent("What is the Anupana context?") == "anupana_context"
    assert research_module.classify_intent("What does Charaka say in this chapter?") == "source_retrieval"
