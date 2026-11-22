from contextlib import nullcontext

import pytest

import ayurform_formulation_research as shared
from frontend.pages import anupana_explorer as page
from models.llm import OllamaError, ResponseSchemaError


ANSWER = "A natural-language academic description of the named Anupana."


class FakeModel:
    model_name = "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"

    def __init__(self, response=ANSWER, error=None):
        self.response, self.error, self.calls = response, error, []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        return self.response


def _ollama(monkeypatch):
    monkeypatch.setattr(shared, "LLM_MODE", "ollama")
    monkeypatch.setattr(shared, "LLM_PROVIDER", "ollama")


def test_anupana_service_generates_directly_with_shared_safety_and_no_retrieval(monkeypatch):
    _ollama(monkeypatch)
    model = FakeModel()
    result = shared.build_anupana_explanation("Honey (Madhu)", model, request_id="anupana-test-1")
    assert result["answer"] == ANSWER
    assert result["canonical_name"] == "Honey (Madhu)"
    assert result["mode"] == "direct_anupana"
    assert result["model"] == model.model_name
    assert result["request_id"] == "anupana-test-1"
    prompt, options = model.calls[0]
    assert "Explain the Anupana named Honey (Madhu)" in prompt
    assert "Keep the response concise, academic, and useful" in prompt
    assert options["format_schema"] is False
    assert options["request_id"] == "anupana-test-1"
    assert options["formulation_name"] == "Honey (Madhu)"
    for heading in (
        "Ayurvedic Identity", "Traditionally Described Properties", "Traditional Context and Associations",
        "Relationship with Dravya and Formulations", "Important Limitations and Uncertainty",
    ):
        assert heading in options["system"]
    assert "Omit any section you cannot support" in options["system"]
    assert "not JSON" in options["system"]
    assert "Do not invent classical references" in options["system"]
    assert "Do not give dosage" in options["system"]
    assert not any(hasattr(shared, key) for key in ("PersistentClient", "BGEEmbeddings", "get_retriever"))


def test_anupana_empty_input_rejected():
    with pytest.raises(ValueError, match="Anupana name"):
        shared.build_anupana_explanation("  ", FakeModel())


def test_anupana_empty_model_response_is_rejected(monkeypatch):
    _ollama(monkeypatch)
    with pytest.raises(ResponseSchemaError, match="empty"):
        shared.build_anupana_explanation("Water", FakeModel(response="  "))


def test_anupana_response_markdown_is_preserved_exactly(monkeypatch):
    _ollama(monkeypatch)
    response = "\n## Ayurvedic Identity\n\n- Traditional note.\n"
    result = shared.build_anupana_explanation("Water", FakeModel(response=response))
    assert result["answer"] == response


@pytest.mark.parametrize("error", [OllamaError("unavailable"), OllamaError("timeout"), OllamaError("HTTP 500")])
def test_anupana_ollama_errors_propagate_without_fallback(monkeypatch, error):
    _ollama(monkeypatch)
    model = FakeModel(error=error)
    with pytest.raises(OllamaError):
        shared.build_anupana_explanation("Water (Jala)", model)
    assert len(model.calls) == 1


def test_anupana_citation_is_preserved_and_warning_returned(monkeypatch):
    _ollama(monkeypatch)
    response = "According to Charaka Samhita, honey is described in this context."
    result = shared.build_anupana_explanation("Honey", FakeModel(response))
    assert result["answer"] == response
    assert result["citation_warning"] == shared.UNVERIFIED_CITATION_WARNING


def test_anupana_without_citation_has_no_citation_warning(monkeypatch):
    _ollama(monkeypatch)
    result = shared.build_anupana_explanation("Water", FakeModel())
    assert result["citation_warning"] is None
    assert result["disclaimer"] == shared.FORMULATION_DISCLAIMER


@pytest.mark.parametrize("unsafe", [
    "Take 2 teaspoons daily.",
    "This is clinically proven to treat disease.",
    "Diagnose the patient before use.",
    "Use it for self-medication.",
    "Purify mercury by heating the mixture.",
])
def test_anupana_keeps_shared_safety_rejections(monkeypatch, unsafe):
    _ollama(monkeypatch)
    with pytest.raises(ResponseSchemaError):
        shared.build_anupana_explanation("Milk", FakeModel(unsafe))


def test_traditional_academic_description_is_allowed(monkeypatch):
    _ollama(monkeypatch)
    response = "Traditionally described as a vehicle in Ayurvedic practice; this is not clinically verified."
    assert shared.build_anupana_explanation("Warm water", FakeModel(response))["answer"] == response


def test_anupana_model_abstention_is_preserved_and_labelled(monkeypatch):
    _ollama(monkeypatch)
    response = "I cannot confidently identify this Anupana from the information available."
    result = shared.build_anupana_explanation("Unfamiliar term", FakeModel(response))
    assert result["answer"] == response
    assert result["result_category"] == "model_abstention"


class FakeStreamlit:
    def __init__(self, clicked=None):
        self.clicked = clicked
        self.session_state = {}
        self.messages = {key: [] for key in ("markdown", "caption", "info", "warning", "error")}

    def markdown(self, value, **kwargs): self.messages["markdown"].append(value)
    def caption(self, value, **kwargs): self.messages["caption"].append(value)
    def info(self, value, **kwargs): self.messages["info"].append(value)
    def warning(self, value, **kwargs): self.messages["warning"].append(value)
    def error(self, value, **kwargs): self.messages["error"].append(value)
    def subheader(self, value, **kwargs): self.messages["markdown"].append(value)
    def text_input(self, label, **kwargs): return self.session_state.get(kwargs["key"], "")
    def button(self, label, **kwargs):
        if self.clicked not in (label, kwargs.get("key")):
            return False
        if kwargs.get("on_click"):
            kwargs["on_click"](*(kwargs.get("args") or ()))
        return True
    def columns(self, count, **kwargs): return [nullcontext() for _ in range(count)]
    def container(self, **kwargs): return nullcontext()
    def expander(self, *args, **kwargs): return nullcontext()
    def spinner(self, *args, **kwargs): return nullcontext()


class FakeResponse:
    def raise_for_status(self): pass
    def json(self): return {"models": [{"name": page.OLLAMA_MODEL}]}


def setup_ui(monkeypatch, clicked):
    ui = FakeStreamlit(clicked)
    monkeypatch.setattr(page, "st", ui)
    monkeypatch.setattr(page, "configured_provider", lambda: "ollama")
    monkeypatch.setattr(page.httpx, "get", lambda *a, **k: FakeResponse())
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    return ui


def test_popular_suggestion_selection_populates_and_runs_direct_generation(monkeypatch):
    assert page.POPULAR_ANUPANA == (
        "Water (Jala)", "Honey (Madhu)", "Milk (Ksheera)", "Ghee (Ghrita)",
        "Buttermilk (Takra)", "Warm water (Ushnodaka)", "Ginger juice (Ardraka Swarasa)",
        "Sugarcane juice (Ikshu Rasa)", "Herbal decoction (Kwatha)", "Rice water (Tandulodaka)",
        "Lemon juice (Nimbu Swarasa)", "Milk-based vehicle",
    )
    name = "Honey (Madhu)"
    key = f"popular_anupana_0_{name.casefold().replace(' ', '_')}"
    ui = setup_ui(monkeypatch, key)
    calls = []
    monkeypatch.setattr(page, "build_anupana_explanation", lambda value, llm, **kwargs: calls.append(value) or {
        "canonical_name": value, "answer": ANSWER, "model": page.OLLAMA_MODEL, "citation_warning": None,
    })
    page.render_anupana_explorer()
    assert ui.session_state["anupana_name"] == name
    assert calls == [name]
    assert ANSWER in ui.messages["markdown"]


def test_anupana_markdown_is_rendered_verbatim_in_academic_result_panel(monkeypatch):
    response = (
        "## Ayurvedic Identity\n\nA concise identity note.\n\n"
        "## Traditionally Described Properties\n\n- A traditional description.\n- Uncertainty remains."
    )
    ui = setup_ui(monkeypatch, "Generate Explanation")
    ui.session_state["anupana_name"] = "Honey"
    monkeypatch.setattr(page, "build_anupana_explanation", lambda name, llm, **kwargs: {
        "canonical_name": name,
        "answer": response,
        "model": page.OLLAMA_MODEL,
        "request_id": kwargs["request_id"],
        "citation_warning": None,
    })

    page.render_anupana_explorer()

    assert ui.messages["markdown"].count(response) == 1
    assert "Honey" in ui.messages["markdown"]
    assert any(page.OLLAMA_MODEL in caption and "Not source-verified" in caption for caption in ui.messages["caption"])
    assert any("Request ID:" in caption for caption in ui.messages["caption"])


def test_anupana_citation_warning_is_rendered_with_original_response(monkeypatch):
    response = "According to Charaka Samhita, honey is described in this context."
    ui = setup_ui(monkeypatch, "Generate Explanation")
    ui.session_state["anupana_name"] = "Honey"
    monkeypatch.setattr(page, "build_anupana_explanation", lambda name, llm, **kwargs: {
        "canonical_name": name,
        "answer": response,
        "model": page.OLLAMA_MODEL,
        "request_id": kwargs["request_id"],
        "citation_warning": shared.UNVERIFIED_CITATION_WARNING,
    })

    page.render_anupana_explorer()

    assert ui.messages["markdown"].count(response) == 1
    assert ui.messages["warning"].count(shared.UNVERIFIED_CITATION_WARNING) == 1


def test_anupana_abstention_has_neutral_status_and_preserves_text(monkeypatch):
    response = "I cannot confidently identify this Anupana from the information available."
    ui = setup_ui(monkeypatch, "Generate Explanation")
    ui.session_state["anupana_name"] = "Unfamiliar term"
    monkeypatch.setattr(page, "build_anupana_explanation", lambda name, llm, **kwargs: {
        "canonical_name": name,
        "answer": response,
        "model": page.OLLAMA_MODEL,
        "request_id": kwargs["request_id"],
        "result_category": "model_abstention",
        "citation_warning": None,
    })

    page.render_anupana_explorer()

    assert ui.messages["markdown"].count(response) == 1
    assert ui.messages["info"].count("AyurParam could not identify this Anupana.") == 1


def test_anupana_ui_reports_ollama_failure_without_fallback(monkeypatch):
    ui = setup_ui(monkeypatch, "Generate Explanation")
    ui.session_state["anupana_name"] = "Water"
    monkeypatch.setattr(page, "build_anupana_explanation", lambda *args, **kwargs: (_ for _ in ()).throw(OllamaError("offline")))

    page.render_anupana_explorer()

    assert any("AyurParam is unavailable" in error and "No fallback answer" in error for error in ui.messages["error"])
    assert not any(ANSWER in value for value in ui.messages["markdown"])


def test_anupana_router_dispatches_to_direct_explorer(monkeypatch):
    import frontend.pages.ayurform_pages as router
    calls = []
    monkeypatch.setattr(page, "render_anupana_explorer", lambda: calls.append(True))
    router.render_ayurform_page("Anupana Explorer")
    assert calls == [True]
