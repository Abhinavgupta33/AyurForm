from contextlib import nullcontext

import pytest

from frontend.pages import research_assistant as page
from ayurform_research import CitationValidationError, SourceRegistryError
from models.llm import (
    OllamaError,
    OllamaGenerationTimeoutError,
    OllamaIncompleteResponseError,
    OllamaInvalidResponseError,
    OllamaModelLoadError,
    OllamaModelNotFoundError,
    OllamaServerError,
    OllamaUnavailableError,
    ResponseSchemaError,
)
from rag.retriever import ChromaRetrievalError, EmbeddingError
from config import OLLAMA_CONNECT_TIMEOUT_SECONDS, OLLAMA_GENERATION_TIMEOUT_SECONDS


class FakeStreamlit:
    def __init__(self, *, clicked=None, state=None):
        self.clicked = clicked
        self.session_state = dict(state or {})
        self.messages = {key: [] for key in ("markdown", "caption", "info", "warning", "error", "text")}
        self.buttons = []

    def markdown(self, value, **kwargs): self.messages["markdown"].append(value)
    def caption(self, value, **kwargs): self.messages["caption"].append(value)
    def info(self, value, **kwargs): self.messages["info"].append(value)
    def warning(self, value, **kwargs): self.messages["warning"].append(value)
    def error(self, value, **kwargs): self.messages["error"].append(value)
    def write(self, value, **kwargs): self.messages["markdown"].append(str(value))
    def text(self, value, **kwargs): self.messages["text"].append(value)
    def text_area(self, label, **kwargs): return self.session_state.get(kwargs.get("key"), "")
    def button(self, label, **kwargs):
        self.buttons.append(label)
        if self.clicked is None or self.clicked not in (label, kwargs.get("key")):
            return False
        if kwargs.get("on_click"):
            kwargs["on_click"](*(kwargs.get("args") or ()))
        return True
    def columns(self, count, **kwargs): return [nullcontext() for _ in range(count)]
    def container(self, **kwargs): return nullcontext()
    def expander(self, *args, **kwargs): return nullcontext()
    def spinner(self, *args, **kwargs): return nullcontext()


def setup(monkeypatch, *, clicked=None, state=None, count=5):
    ui = FakeStreamlit(clicked=clicked, state=state)
    monkeypatch.setattr(page, "st", ui)
    monkeypatch.setattr(page, "model_mode", lambda: "ollama")
    monkeypatch.setattr(page, "_model_status", lambda: "Available")
    monkeypatch.setattr(page, "_retrieval_status", lambda: (f"Production collection · {count} passages", count))
    return ui


def grounded_result(*, answer="## Research Overview\n\nA grounded statement [P1].", development=False):
    return {
        "question": "What does the source say?",
        "intent": "source_retrieval",
        "request_id": "corr-test-1",
        "model": page.OLLAMA_MODEL,
        "knowledge_mode": "development" if development else "production",
        "development_only": development,
        "development_warning": "Development-only evidence is not production-approved." if development else None,
        "evidence_type": "translated classical source text",
        "mode": "grounded",
        "answer": answer,
        "answer_complete": True,
        "citation_validation_status": "passed",
        "evidence_validation_status": "passed",
        "source_verified": True,
        "limitations": "Limited to retrieved evidence.",
        "retrieval": {"retrieved_count": 1, "eligible_count": 1, "excluded": {}},
        "evidence": [{
            "citation_id": "P1", "passage_id": "source-p1", "text": "A source-backed excerpt.",
            "source_title": "Recorded source", "translator": "Recorded translator", "page": 12,
            "chapter": "Chapter 2", "verse": "5", "provenance_role": "translated_source",
            "rights_status": "licensed", "review_status": "approved",
            "usage_scope": "development_only" if development else "production", "distance": 0.2,
        }],
    }


def test_workspace_shows_academic_title_examples_and_index_status(monkeypatch):
    ui = setup(monkeypatch, count=17)
    page.render_research_assistant()
    assert any("AyurParam Research Assistant" in message for message in ui.messages["markdown"])
    assert any("Academic literature exploration using source-grounded AI." in message for message in ui.messages["markdown"])
    assert all(question in ui.buttons for question in page.EXAMPLE_QUESTIONS)
    assert any("BAAI/bge-base-en-v1.5" in caption for caption in ui.messages["caption"])
    assert any("17 passages" in caption for caption in ui.messages["caption"])


def test_example_question_populates_input_and_runs_research(monkeypatch):
    question = page.EXAMPLE_QUESTIONS[0]
    key = "research_example_0_0"
    ui = setup(monkeypatch, clicked=key)
    calls = []
    monkeypatch.setattr(page, "research", lambda value, llm, **kwargs: calls.append(value) or grounded_result())
    class LocalModel:
        def __init__(self, **kwargs): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)

    page.render_research_assistant()

    assert ui.session_state["research_question"] == question
    assert calls == [question]
    assert ui.session_state["research_result"]["mode"] == "grounded"


def test_dashboard_prefill_is_consumed_before_research_widget(monkeypatch):
    question = "Explore the traditional properties of Tulsi"
    ui = setup(monkeypatch, state={"research_prefill": question})
    calls = []
    monkeypatch.setattr(page, "research", lambda *args, **kwargs: calls.append(args))
    page.render_research_assistant()
    assert ui.session_state["research_question"] == question
    assert "research_prefill" not in ui.session_state
    assert calls == []


def test_research_page_uses_bounded_separate_ollama_timeouts(monkeypatch):
    ui = setup(monkeypatch, clicked="Ask Research Assistant", state={"research_question": "Question"})
    created = []
    monkeypatch.setattr(page, "research", lambda *args, **kwargs: grounded_result())
    class LocalModel:
        def __init__(self, **kwargs): created.append(kwargs)
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)

    page.render_research_assistant()

    assert created == [{
        "connect_timeout": OLLAMA_CONNECT_TIMEOUT_SECONDS,
        "generation_timeout": OLLAMA_GENERATION_TIMEOUT_SECONDS,
    }]


def test_successful_result_displays_answer_citation_anchor_and_source_metadata(monkeypatch):
    ui = setup(monkeypatch, clicked="Ask Research Assistant", state={"research_question": "What does the source say?"})
    monkeypatch.setattr(page, "research", lambda *args, **kwargs: grounded_result(answer="## Research Overview\n\nA grounded statement [P1](#source-P1)."))
    class LocalModel:
        def __init__(self, **kwargs): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)

    page.render_research_assistant()

    assert "## Research Overview\n\nA grounded statement [P1](#source-P1)." in ui.messages["markdown"]
    assert any('id="source-P1"' in message for message in ui.messages["markdown"])
    assert any("Recorded translator" in caption and "Page: 12" in caption for caption in ui.messages["caption"])
    assert "A source-backed excerpt." in ui.messages["text"]
    assert any("Request ID" in caption or "Correlation ID: corr-test-1" in caption for caption in ui.messages["caption"])
    assert any("Limited to retrieved evidence" in value for value in ui.messages["info"])
    assert any("Session-only history" in value for value in ui.messages["caption"])


def test_unvalidated_citation_answer_is_rendered_original_with_warning(monkeypatch):
    ui = setup(monkeypatch)
    original = "## Evidence\n\nOriginal **AyurParam** wording [P99]."
    result = grounded_result(answer=original)
    result.update({
        "mode": "unverified_answer", "citation_validation_status": "failed",
        "evidence_validation_status": "failed", "source_verified": False,
        "validation_failure_category": "unknown_citation_id",
    })
    page._render_result(result)
    assert original in ui.messages["markdown"]
    assert any("did not validate against this request's retrieved passages" in text for text in ui.messages["warning"])
    assert any("not source-verified" in text for text in ui.messages["markdown"])
    assert "AyurParam **text**" not in ui.messages["markdown"]


def test_incomplete_response_is_rendered_with_incomplete_warning(monkeypatch):
    ui = setup(monkeypatch)
    partial = "## Direct answer\n\nAn incomplete source-grounded response"
    result = grounded_result(answer=partial)
    result.update({"mode": "incomplete", "answer_complete": False, "source_verified": False})
    page._render_result(result)
    assert partial in ui.messages["markdown"]
    assert any("ended before completion" in text for text in ui.messages["warning"])
    assert any("Incomplete AyurParam response" in text for text in ui.messages["markdown"])


def test_development_evidence_has_clear_nonproduction_warning(monkeypatch):
    ui = setup(monkeypatch, clicked="Ask Research Assistant", state={"research_question": "Question"})
    monkeypatch.setattr(page, "research", lambda *args, **kwargs: grounded_result(development=True))
    class LocalModel:
        def __init__(self, **kwargs): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_research_assistant()
    assert any("not production-approved" in value for value in ui.messages["warning"])
    assert any("Rights status: licensed" in value and "Usage scope: development_only" in value for value in ui.messages["caption"])


def test_no_evidence_state_is_explicit_and_does_not_render_answer(monkeypatch):
    ui = setup(monkeypatch, clicked="Ask Research Assistant", state={"research_question": "Question"})
    monkeypatch.setattr(page, "research", lambda *args, **kwargs: {
        "mode": "abstention", "answer": None, "limitations": page.NO_EVIDENCE_MESSAGE,
        "evidence": [], "intent": "source_retrieval", "request_id": "corr-no-evidence",
        "retrieval": {"retrieved_count": 0, "eligible_count": 0, "excluded": {}},
    })
    class LocalModel:
        def __init__(self, **kwargs): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_research_assistant()
    assert page.NO_EVIDENCE_MESSAGE in ui.messages["info"]
    assert not any("Research Overview" in value for value in ui.messages["markdown"])


def test_empty_collection_shows_index_empty_state(monkeypatch):
    ui = setup(monkeypatch, count=0)
    page.render_research_assistant()
    assert any("No passages are currently indexed" in value for value in ui.messages["info"]), ui.messages


@pytest.mark.parametrize("error,expected", [
    (OllamaUnavailableError("offline"), "Ollama could not be reached"),
    (OllamaModelNotFoundError("missing"), "is not available in Ollama"),
    (OllamaModelLoadError("load"), "could not load AyurParam"),
    (OllamaGenerationTimeoutError("slow"), "generation timeout"),
    (OllamaIncompleteResponseError("truncated"), "output limit"),
    (OllamaInvalidResponseError("empty"), "no usable answer text"),
    (OllamaServerError("500"), "server error"),
    (OllamaError("other"), "AyurParam generation failed"),
    (EmbeddingError("bge"), "BGE query embedding failed"),
    (ChromaRetrievalError("chroma"), "ChromaDB could not retrieve"),
    (SourceRegistryError("registry"), "source registry is unavailable"),
    (ResponseSchemaError("citation failed"), "citations did not match"),
])
def test_service_errors_are_shown_without_raw_tracebacks(monkeypatch, error, expected):
    ui = setup(monkeypatch, clicked="Ask Research Assistant", state={"research_question": "Question"})
    monkeypatch.setattr(page, "research", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    class LocalModel:
        def __init__(self, **kwargs): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_research_assistant()
    assert any(expected in value for value in ui.messages["error"])
    assert not any("Traceback" in value for value in ui.messages["error"])


def test_empty_model_response_displays_safe_response_diagnostics(monkeypatch):
    ui = setup(monkeypatch, clicked="Ask Research Assistant", state={"research_question": "Question"})
    exc = OllamaInvalidResponseError("empty", diagnostics={
        "http_status": 200, "response_json_keys": ["message", "done"],
        "extracted_field": "missing", "raw_response_length": 40,
        "extracted_answer_length": 0, "finish_reason": "stop",
        "generation_completed": True, "answer_extraction_succeeded": False,
    })
    monkeypatch.setattr(page, "research", lambda *args, **kwargs: (_ for _ in ()).throw(exc))
    class LocalModel:
        def __init__(self, **kwargs): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_research_assistant()
    assert any("no usable answer text" in value for value in ui.messages["error"])
    assert any("http status: 200" in value and "extracted answer length: 0" in value for value in ui.messages["markdown"])


@pytest.mark.parametrize("category,expected", [
    ("missing_citation", "omitted a required passage citation"),
    ("unknown_citation_id", "unknown citation ID"),
    ("citation_not_retrieved", "not retrieved for this request"),
    ("malformed_citation", "malformed citation"),
])
def test_ui_displays_precise_citation_failure_category(monkeypatch, category, expected):
    ui = setup(monkeypatch, clicked="Ask Research Assistant", state={"research_question": "Question"})
    error = CitationValidationError(category, "safe internal validation message")
    monkeypatch.setattr(page, "research", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    class LocalModel:
        def __init__(self, **kwargs): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)

    page.render_research_assistant()

    assert any(expected in value for value in ui.messages["error"])
    assert any(category in value for value in ui.messages["caption"])


def test_page_router_uses_research_assistant_renderer(monkeypatch):
    import frontend.pages.research_assistant as module
    import frontend.pages.ayurform_pages as router
    calls = []
    monkeypatch.setattr(module, "render_research_assistant", lambda: calls.append(True))
    router.render_ayurform_page("Research Assistant")
    assert calls == [True]
