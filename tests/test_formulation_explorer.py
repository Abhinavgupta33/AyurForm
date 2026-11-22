from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
import logging

import pytest

import ayurform_formulation_research as research
from frontend.pages import formulation_explorer as page
from models.llm import OllamaError, ResponseSchemaError


VALID_MARKDOWN = """## Triphala overview

Triphala is discussed here as a formulation. Its precise composition and traditional descriptions
remain uncertain where they are not independently verified.

- The explanation is general.
- No source attribution or clinical claim is made.
"""


class FakeModel:
    model_name = "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"

    def __init__(self, response=VALID_MARKDOWN, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        if isinstance(self.response, list):
            return self.response.pop(0)
        return self.response


def test_direct_formulation_generation_uses_configured_model_natural_language_only(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    monkeypatch.setattr(research, "LLM_PROVIDER", "ollama")
    model = FakeModel()
    result = research.build_formulation_explanation("Triphala", model)
    assert result["mode"] == "direct_formulation"
    assert result["model"] == "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"
    assert result["request_id"]
    assert result["answer"] == VALID_MARKDOWN
    assert result["result_category"] == "answer"
    prompt, options = model.calls[0]
    assert "Triphala" in prompt
    assert options["format_schema"] is False
    assert options["max_new_tokens"] == 1100
    assert "not JSON" in options["system"]
    assert "do not name or attribute any text" in options["system"]
    assert "reference numbers, quotations, citations" in options["system"]
    assert "500" not in options["system"]
    assert "## Introduction" not in options["system"]
    assert "not an ordinary" in prompt
    assert "Limitations and uncertainties" in prompt
    assert "cannot confidently identify" in prompt
    assert research.FORMULATION_DISCLAIMER == "Generated directly by AyurParam. Not verified against retrieved classical sources."


def test_formulation_service_has_no_retrieval_or_embedding_dependency(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    model = FakeModel(response="Trikatu is a traditional Ayurvedic formulation. Its ingredients are discussed as a blend of spices.")
    research.build_formulation_explanation("Trikatu", model)
    assert not any(hasattr(research, name) for name in ("get_retriever", "select_evidence", "BGEEmbeddings", "PersistentClient"))
    assert len(model.calls) == 1


def test_empty_formulation_response_is_rejected(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    with pytest.raises(ResponseSchemaError, match="empty"):
        research.build_formulation_explanation("Triphala", FakeModel(response="  "))


def test_natural_paragraph_markdown_passes_without_required_headings_or_retry(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    response = "Triphala is a formulation.\n\n- Details vary by source.\n- This overview is not clinically verified."
    model = FakeModel(response=response)
    result = research.build_formulation_explanation("Triphala", model)
    assert result["answer"] == response
    assert len(model.calls) == 1
    assert model.calls[0][1]["format_schema"] is False


def test_citation_text_is_preserved_without_retry(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    citation_answer = VALID_MARKDOWN.replace("No source attribution or clinical claim is made.", "Charaka described this.")
    model = FakeModel(response=citation_answer)
    result = research.build_formulation_explanation("Triphala", model)
    assert result["answer"] == citation_answer
    assert result["citation_warning"] == research.UNVERIFIED_CITATION_WARNING
    assert len(model.calls) == 1


def test_unqualified_efficacy_rejected_and_qualified_traditional_description_allowed():
    unqualified = VALID_MARKDOWN.replace(
        "Its precise composition and traditional descriptions\nremain uncertain where they are not independently verified.",
        "It supports digestion.",
    )
    with pytest.raises(ResponseSchemaError, match="unqualified efficacy claim"):
        research.validate_formulation_answer(unqualified)

    traditional = VALID_MARKDOWN.replace(
        "Its precise composition and traditional descriptions\nremain uncertain where they are not independently verified.",
        "A traditional Ayurvedic description associates it with digestion; that description is unverified and is not a clinical claim.",
    )
    assert research.validate_formulation_answer(traditional) == traditional.strip()

    explicitly_qualified_benefit = VALID_MARKDOWN.replace(
        "No source attribution or clinical claim is made.",
        "Traditionally described as supporting digestion; this is an unverified traditional description, not a clinical efficacy claim.",
    )
    assert research.validate_formulation_answer(explicitly_qualified_benefit) == explicitly_qualified_benefit.strip()


def test_clinical_rejection_logs_only_redacted_trigger_sentence_and_preserves_rejection(monkeypatch, caplog):
    monkeypatch.setenv("AYURSUTRA_ENV", "development")
    response = "Clinical studies prove efficacy; contact: private.person@example.com"
    with pytest.raises(ResponseSchemaError, match="modern clinical efficacy"):
        research.validate_formulation_answer(response, request_id="req-test-1", requested_formulation="Test Formulation")
    diagnostic = next(record.getMessage() for record in caplog.records if "formulation_validation" in record.getMessage())
    assert "category=modern_clinical_efficacy" in diagnostic
    assert "Clinical studies prove efficacy;" in diagnostic
    assert "traditional_framing_detected=False" in diagnostic
    assert "modern_clinical_efficacy_detected=true" in diagnostic
    assert "request_id=req-test-1" in diagnostic
    assert "formulation='Test Formulation'" in diagnostic
    assert "matched_pattern='Clinical studies prove'" in diagnostic
    assert "private.person@example.com" not in diagnostic
    assert "[REDACTED]" in diagnostic


def test_clinical_diagnostics_are_development_only(monkeypatch, caplog):
    monkeypatch.setenv("AYURSUTRA_ENV", "production")
    with pytest.raises(ResponseSchemaError):
        research.validate_formulation_answer("Clinical studies prove efficacy.")
    assert not any("formulation_validation" in record.getMessage() for record in caplog.records)


def test_request_id_is_passed_to_model_and_returned(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    model = FakeModel()
    result = research.build_formulation_explanation("Triphala", model, request_id="form-req-42")
    assert result["request_id"] == "form-req-42"
    assert model.calls[0][1]["request_id"] == "form-req-42"
    assert model.calls[0][1]["formulation_name"] == "Triphala"


def test_concurrent_validation_diagnostics_keep_request_and_name_paired(monkeypatch, caplog):
    monkeypatch.setenv("AYURSUTRA_ENV", "development")
    cases = [("corr-alpha", "Alpha Formula"), ("corr-beta", "Beta Formula")]

    def reject(case):
        request_id, formulation = case
        with pytest.raises(ResponseSchemaError):
            research.validate_formulation_answer(
                "This supports digestion.", request_id=request_id, requested_formulation=formulation
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(reject, cases))
    records = [r.getMessage() for r in caplog.records if "formulation_validation" in r.getMessage()]
    assert any("request_id=corr-alpha" in line and "formulation='Alpha Formula'" in line for line in records)
    assert any("request_id=corr-beta" in line and "formulation='Beta Formula'" in line for line in records)
    assert not any("request_id=corr-alpha" in line and "Beta Formula" in line for line in records)
    assert not any("request_id=corr-beta" in line and "Alpha Formula" in line for line in records)


@pytest.mark.parametrize("citation", [
    "P1",
    "Su1#41",
    "Ci1.4#3-6",
    "According to ancient texts, this is described.",
    "According to Charaka Samhita, this is described.",
])
def test_citation_like_content_is_detected_for_warning_and_preserved(citation):
    answer = VALID_MARKDOWN.replace("No source attribution or clinical claim is made.", citation)
    assert research.validate_formulation_answer(answer) == answer.strip()
    assert research.detect_unverified_citations(answer)


def test_citation_free_natural_language_response_passes():
    assert research.validate_formulation_answer(VALID_MARKDOWN) == VALID_MARKDOWN.strip()


def test_unrelated_sitopaladi_lentil_recipe_is_rejected_even_if_name_is_in_title(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    recipe = """# Sitopaladi Churna Recipe

Ingredients: lentils, rice, onions, garlic, tomatoes, cumin, and oil.

Method: fry the onions, cook the lentils, simmer with rice, and serve hot.
"""
    result = research.build_formulation_explanation("Sitopaladi Churna", FakeModel(recipe))
    assert result["answer"] == recipe
    assert result["relevance"]["status"] == "failed"
    assert result["validation_status"] == "failed"


def test_formulation_name_only_in_unrelated_recipe_heading_is_not_enough():
    recipe = """# Sitopaladi Churna

Ingredients: lentils, rice, onions, garlic, and oil.

Recipe: fry the onions, cook the lentils, and serve hot.
"""
    with pytest.raises(research.FormulationRelevanceError):
        research.validate_formulation_relevance("Sitopaladi Churna", recipe)


def test_relevant_formulation_overview_passes_relevance_check(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    response = "Sitopaladi Churna is an Ayurvedic powder formulation. Its ingredients and traditional descriptions vary across accounts."
    result = research.build_formulation_explanation("Sitopaladi Churna", FakeModel(response))
    assert result["answer"] == response


@pytest.mark.parametrize("name", ["Triphala", "Trikatu", "Chyawanprash"])
def test_other_relevant_formulations_are_accepted_when_academic_context_is_present(monkeypatch, name):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    response = f"{name} is an Ayurvedic formulation. Its traditional context and composition are not established by this direct response."
    assert research.build_formulation_explanation(name, FakeModel(response))["answer"] == response


def test_chyawanprash_unqualified_modern_claim_still_fails(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    response = "Chyawanprash is an Ayurvedic formulation. It is a powerful antioxidant and clinically effective."
    result = research.build_formulation_explanation("Chyawanprash", FakeModel(response))
    assert result["answer"] == response
    assert result["clinical_efficacy_status"] == "failed"
    assert result["validation_status"] == "failed"


def test_ashwagandharishta_citation_is_preserved_with_warning(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    response = "Ashwagandharishta is a traditional Ayurvedic fermented formulation. Charaka describes it in a classical source."
    result = research.build_formulation_explanation("Ashwagandharishta", FakeModel(response))
    assert result["answer"] == response
    assert result["citation_warning"] == research.UNVERIFIED_CITATION_WARNING


def test_legitimate_traditional_preparation_terminology_is_not_a_recipe_mismatch():
    answer = "Sitopaladi Churna is a traditional herbal powder formulation. The preparation is described as combining ingredients into a fine powder."
    research.validate_formulation_relevance("Sitopaladi Churna", answer)


def test_uncertain_or_insufficiently_relevant_answer_is_rejected():
    with pytest.raises(research.FormulationRelevanceError):
        research.validate_formulation_relevance("Sitopaladi Churna", "Here is an unrelated discussion of food and cooking.")


def test_sitopaladi_identified_as_gujarati_rice_lentil_dish_is_rejected():
    response = (
        "Sitopaladi Churna is a Gujarati rice-and-lentil dish. This regional cuisine recipe combines "
        "rice, lentils, onions, garlic and spices into a meal."
    )
    with pytest.raises(research.FormulationRelevanceError):
        research.validate_formulation_relevance("Sitopaladi Churna", response)


def test_repeated_formulation_name_does_not_rescue_unrelated_recipe():
    response = """# Sitopaladi Churna

Sitopaladi Churna is a Gujarati regional dish made with rice and lentils. This Sitopaladi Churna recipe
adds onions and garlic. Prepare the Sitopaladi Churna dish by frying the onions, cooking the lentils,
and serving the meal hot with rice.
"""
    with pytest.raises(research.FormulationRelevanceError):
        research.validate_formulation_relevance("Sitopaladi Churna", response)


def test_relevance_failure_uses_clear_ui_error(monkeypatch):
    ui, _ = _setup_ui(monkeypatch, clicked="Generate Explanation", state={"formulation_name": "Sitopaladi Churna"})
    request_ids = []
    def reject(*args, **kwargs):
        request_ids.append(kwargs["request_id"])
        return {
            "canonical_name": "Sitopaladi Churna", "request_id": kwargs["request_id"],
            "answer": "Sitopaladi Churna is a Gujarati lentil dish.",
            "validation_status": "failed", "safety_status": "passed",
            "relevance": {"status": "failed", "category": "identity_mismatch", "reason": "regional_dish"},
            "clinical_efficacy_status": "passed", "warnings": [],
        }
    monkeypatch.setattr(page, "build_formulation_explanation", reject)
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_formulation_explorer()
    assert sum("RELEVANCE WARNING:" in warning for warning in ui.messages["warning"]) == 1
    assert "AyurParam could not identify this formulation." not in ui.messages["info"]
    assert "Sitopaladi Churna is a Gujarati lentil dish." in ui.messages["markdown"]
    assert ui.session_state["formulation_error_request_id"] == request_ids[0]


def test_model_abstention_is_rendered_once_with_neutral_status_and_correlated_diagnostics(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    monkeypatch.setattr(research, "LLM_PROVIDER", "ollama")
    raw = (
        "I apologize, but I am unable to provide an explanation for the Sitopaladi Churna as the "
        "information provided is insufficient for me to accurately identify or explain the formulation."
    )
    result = research.build_formulation_explanation(
        "Sitopaladi Churna", FakeModel(raw), request_id="abstain-service-1"
    )
    assert result["answer"] == raw
    assert result["relevance"]["category"] == "model_abstention"
    assert result["result_category"] == "model_abstention"
    assert result["warnings"] == []

    ui, _ = _setup_ui(monkeypatch, clicked="Generate Explanation", state={"formulation_name": "Sitopaladi Churna"})
    def build(name, llm, **kwargs):
        return research.build_formulation_explanation(name, FakeModel(raw), **kwargs)
    monkeypatch.setattr(page, "build_formulation_explanation", build)
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_formulation_explorer()
    assert ui.messages["markdown"].count(raw) == 1
    assert ui.messages["info"].count("AyurParam could not identify this formulation.") == 1
    assert not any("RELEVANCE WARNING:" in value for value in ui.messages["warning"])
    assert not any(research.FORMULATION_RELEVANCE_ERROR in value for value in ui.messages["warning"])
    assert not any(research.FORMULATION_ABSTENTION_MESSAGE in value for value in ui.messages["warning"] + ui.messages["error"])
    answer = ui.session_state["formulation_answer"]
    assert answer["request_id"] == ui.session_state["formulation_error_request_id"]
    assert any(f"Request ID: {answer['request_id']}" in value for value in ui.messages["caption"])
    assert any("model_abstention · model_could_not_identify_formulation" in value for value in ui.messages["markdown"])


def test_build_blocks_actionable_content_but_returns_non_actionable_claims_with_status(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    for prohibited in ("Take 2 tablets daily.", "Use this for self-medication.", "Purify mercury by heating it."):
        with pytest.raises(ResponseSchemaError, match="prohibited instructions"):
            research.build_formulation_explanation("Triphala", FakeModel(prohibited))
    clinical = "Triphala is an Ayurvedic formulation. It is clinically proven to treat disease."
    result = research.build_formulation_explanation("Triphala", FakeModel(clinical))
    assert result["answer"] == clinical
    assert result["clinical_efficacy_status"] == "failed"


def test_relevance_acceptance_and_rejection_diagnostics_are_correlated(monkeypatch, caplog):
    monkeypatch.setenv("AYURSUTRA_ENV", "development")
    caplog.set_level(logging.INFO, logger="ayursutra.rag")
    accepted = "Sitopaladi Churna is an Ayurvedic powder formulation with documented traditional context."
    research.validate_formulation_relevance("  SITOPALADI   Churna ", accepted, request_id="rel-accept-1")
    rejected = "Sitopaladi Churna is a Gujarati rice-and-lentil dish."
    with pytest.raises(research.FormulationRelevanceError):
        research.validate_formulation_relevance("Sitopaladi Churna", rejected, request_id="rel-reject-1")
    events = [record.getMessage() for record in caplog.records if "formulation_relevance" in record.getMessage()]
    assert any("request_id=rel-accept-1" in event and "formulation_name='sitopaladi churna'" in event and "outcome=accepted" in event for event in events)
    assert any("request_id=rel-reject-1" in event and "outcome=rejected" in event and "rejection_category=identity_mismatch" in event for event in events)
    assert any("triggering_sentence='Sitopaladi Churna is a Gujarati rice-and-lentil dish.'" in event for event in events)


def test_concurrent_relevance_diagnostics_remain_isolated(monkeypatch, caplog):
    monkeypatch.setenv("AYURSUTRA_ENV", "development")
    caplog.set_level(logging.INFO, logger="ayursutra.rag")
    cases = [
        ("req-one", "Alpha Churna", "Alpha Churna is a Gujarati rice-and-lentil dish."),
        ("req-two", "Beta Churna", "Beta Churna is a Gujarati rice-and-lentil dish."),
    ]
    def run(item):
        request_id, formulation, response = item
        with pytest.raises(research.FormulationRelevanceError):
            research.validate_formulation_relevance(formulation, response, request_id=request_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, cases))
    events = [record.getMessage() for record in caplog.records if "formulation_relevance" in record.getMessage()]
    assert any("request_id=req-one" in e and "formulation_name='alpha churna'" in e and "Alpha Churna is a Gujarati" in e for e in events)
    assert any("request_id=req-two" in e and "formulation_name='beta churna'" in e and "Beta Churna is a Gujarati" in e for e in events)
    assert not any("request_id=req-one" in e and "Beta Churna" in e for e in events)
    assert not any("request_id=req-two" in e and "Alpha Churna" in e for e in events)


def test_unverified_quotation_is_rejected_not_removed():
    answer = VALID_MARKDOWN.replace("No source attribution or clinical claim is made.", "“A long classical quotation is written here.”")
    with pytest.raises(ResponseSchemaError, match="cannot verify quoted source text"):
        research.validate_formulation_answer(answer)


def test_descriptive_traditional_statement_is_allowed_when_clearly_qualified():
    answer = VALID_MARKDOWN.replace(
        "No source attribution or clinical claim is made.",
        "Traditionally described in Ayurveda as a digestive formulation, though not verified here.",
    )
    assert research.validate_formulation_answer(answer) == answer.strip()


@pytest.mark.parametrize("sentence", [
    "Historically, this formulation was used in traditional practice to support digestion.",
    "It was historically described as a traditional digestive preparation.",
    "The formulation was historically regarded as useful in traditional practice.",
    "This formulation was historically documented in traditional practice for digestive complaints.",
    "Historically, Arjunarishta was used to treat a range of ailments.",
])
def test_bounded_historical_framing_qualifies_efficacy_in_same_sentence(sentence):
    assert research.validate_formulation_answer(sentence) == sentence


@pytest.mark.parametrize("sentence", [
    "This formulation is clinically proven to treat digestive disorders.",
    "Historically important. This formulation treats digestive disorders.",
    "Historically used in traditional practice, this formulation is clinically proven to treat disease.",
])
def test_historical_framing_does_not_allow_unqualified_or_clinical_claims(sentence):
    with pytest.raises(ResponseSchemaError):
        research.validate_formulation_answer(sentence)


@pytest.mark.parametrize("unsafe_claim", [
    "This treats respiratory ailments.",
    "The formula contains equal parts of the ingredients.",
    "It supports overall health.",
    "Clinical studies prove its effectiveness.",
    "Modern research shows that it is clinically proven to work.",
])
def test_unverified_or_clinical_efficacy_claims_are_rejected(unsafe_claim):
    answer = VALID_MARKDOWN.replace(
        "Its precise composition and traditional descriptions\nremain uncertain where they are not independently verified.",
        unsafe_claim,
    )
    with pytest.raises(ResponseSchemaError):
        research.validate_formulation_answer(answer)


@pytest.mark.parametrize("instruction", [
    "Take 2 tablets every morning.",
    "Diagnose the condition before using it.",
    "Purify mercury by heating the mixture.",
    "This is a patient-specific treatment recommendation.",
])
def test_medical_and_hazardous_instructions_are_rejected(instruction):
    answer = VALID_MARKDOWN.replace(
        "Its precise composition and traditional descriptions\nremain uncertain where they are not independently verified.",
        instruction,
    )
    with pytest.raises(ResponseSchemaError, match="prohibited instructions"):
        research.validate_formulation_answer(answer)


@pytest.mark.parametrize("error", [
    OllamaError("Ollama unavailable"),
    OllamaError("Ollama request timed out"),
])
def test_ollama_unavailable_and_timeout_propagate_without_fallback(monkeypatch, error):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    model = FakeModel(error=error)
    with pytest.raises(OllamaError):
        research.build_formulation_explanation("Triphala", model)
    assert len(model.calls) == 1


def test_mock_mode_never_invokes_a_fallback_model(monkeypatch):
    monkeypatch.setattr(research, "LLM_MODE", "mock")
    model = FakeModel()
    with pytest.raises(RuntimeError, match="Mock mode"):
        research.build_formulation_explanation("Triphala", model)
    assert model.calls == []


@pytest.mark.parametrize("response", [
    '{"ingredients": []}',
    "## Introduction\n\nDosage instructions are not provided.",
])
def test_structured_citations_or_unsafe_instructions_are_rejected(monkeypatch, response):
    monkeypatch.setattr(research, "LLM_MODE", "ollama")
    if "Dosage" in response:
        with pytest.raises(ResponseSchemaError):
            research.build_formulation_explanation("Triphala", FakeModel(response=response))
    else:
        result = research.build_formulation_explanation("Triphala", FakeModel(response=response))
        assert result["answer"] == response
        assert result["relevance"]["status"] == "failed"


class FakeStreamlit:
    def __init__(self, *, clicked=None, state=None):
        self.clicked = clicked
        self.session_state = state or {}
        self.messages = {name: [] for name in ("markdown", "caption", "info", "warning", "error", "success")}
        self.buttons = []

    def markdown(self, value, **kwargs): self.messages["markdown"].append(value)
    def caption(self, value, **kwargs): self.messages["caption"].append(value)
    def info(self, value, **kwargs): self.messages["info"].append(value)
    def warning(self, value, **kwargs): self.messages["warning"].append(value)
    def error(self, value, **kwargs): self.messages["error"].append(value)
    def write(self, value, **kwargs): self.messages["markdown"].append(value)
    def subheader(self, value, **kwargs): self.messages["markdown"].append(value)
    def text_input(self, label, **kwargs): return self.session_state.get(kwargs["key"], "")
    def button(self, label, **kwargs):
        self.buttons.append(label)
        if self.clicked is None or self.clicked not in (label, kwargs.get("key")):
            return False
        callback = kwargs.get("on_click")
        if callback:
            callback(*(kwargs.get("args") or ()))
        return True
    def columns(self, count, **kwargs): return [nullcontext() for _ in range(count)]
    def container(self, **kwargs): return nullcontext()
    def expander(self, *args, **kwargs): return nullcontext()
    def spinner(self, *args, **kwargs): return nullcontext()


class FakeResponse:
    def raise_for_status(self): pass
    def json(self): return {"models": [{"name": "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"}]}


def _setup_ui(monkeypatch, *, clicked=None, state=None):
    ui = FakeStreamlit(clicked=clicked, state=state)
    monkeypatch.setattr(page, "st", ui)
    monkeypatch.setattr(page, "configured_provider", lambda: "ollama")
    api_calls = []
    monkeypatch.setattr(page.httpx, "get", lambda url, **kwargs: api_calls.append(url) or FakeResponse())
    return ui, api_calls


def test_popular_suggestions_present_and_chip_triggers_generation(monkeypatch):
    assert page.POPULAR_FORMULATIONS == (
        "Ashwagandha Churna",
        "Brahmi Vati",
        "Haridra Khanda",
        "Kaishora Guggulu",
        "Ashwagandha Arishta",
        "Shatavari Ghrita",
        "Guduchi Satva",
        "Dashamoola Kashaya",
        "Trikatu Churna",
        "Yashtimadhu Swarasa",
    )
    selected = "Ashwagandha Churna"
    ui, api_calls = _setup_ui(monkeypatch, clicked="popular_formulation_ashwagandha_churna")
    calls = []
    monkeypatch.setattr(page, "build_formulation_explanation", lambda name, llm, **kwargs: calls.append(name) or {
        "canonical_name": name, "answer": VALID_MARKDOWN, "model": "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M",
    })
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_formulation_explorer()
    assert all(suggestion in ui.buttons for suggestion in page.POPULAR_FORMULATIONS)
    assert calls == [selected]
    assert ui.session_state["formulation_name"] == selected
    assert api_calls == ["http://127.0.0.1:11434/api/tags"]
    assert VALID_MARKDOWN in ui.messages["markdown"]


@pytest.mark.parametrize("name", [
    "Ashwagandha Churna",
    "Brahmi Vati",
    "Haridra Khanda",
    "Kaishora Guggulu",
    "Ashwagandha Arishta",
    "Shatavari Ghrita",
    "Guduchi Satva",
    "Dashamoola Kashaya",
    "Trikatu Churna",
    "Yashtimadhu Swarasa",
])
def test_every_popular_formulation_is_rendered_and_can_generate(monkeypatch, name):
    key_name = name.casefold().replace(" ", "_")
    ui, _ = _setup_ui(monkeypatch, clicked=f"popular_formulation_{key_name}")
    submitted = []
    monkeypatch.setattr(page, "build_formulation_explanation", lambda value, llm, **kwargs: submitted.append(value) or {
        "canonical_name": value, "answer": VALID_MARKDOWN,
        "model": "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M",
    })
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)

    page.render_formulation_explorer()

    assert all(suggestion in ui.buttons for suggestion in page.POPULAR_FORMULATIONS)
    assert ui.session_state["formulation_name"] == name
    assert submitted == [name]


def test_previous_popular_formulation_suggestions_are_removed():
    previous_suggestions = {
        "Chyawanprash", "Triphala", "Trikatu", "Dashamoola", "Arjunarishta", "Brahmi Ghrita",
    }
    assert not previous_suggestions.intersection(page.POPULAR_FORMULATIONS)


def test_explorer_suggestions_keep_herbs_and_anupana_separate_from_formulations():
    from frontend.pages.ayurform_pages import POPULAR_DRAVYAS
    from frontend.pages.anupana_explorer import POPULAR_ANUPANA

    assert {"Turmeric", "Ginger", "Neem", "Amla", "Ashwagandha"}.issubset(POPULAR_DRAVYAS)
    assert not {"Turmeric", "Ginger", "Neem", "Amla", "Ashwagandha"}.intersection(page.POPULAR_FORMULATIONS)
    assert "Honey (Madhu)" in POPULAR_ANUPANA
    assert "Water (Jala)" in POPULAR_ANUPANA


def test_manual_generation_renders_markdown_and_single_disclaimer(monkeypatch):
    ui, api_calls = _setup_ui(monkeypatch, clicked="Generate Explanation", state={"formulation_name": "Custom formulation name"})
    submitted = []
    monkeypatch.setattr(page, "build_formulation_explanation", lambda name, llm, **kwargs: submitted.append(name) or {
        "canonical_name": name, "answer": VALID_MARKDOWN, "model": "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M",
    })
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_formulation_explorer()
    assert submitted == ["Custom formulation name"]
    assert VALID_MARKDOWN in ui.messages["markdown"]
    assert not any("RELEVANCE WARNING:" in value for value in ui.messages["warning"])
    assert ui.messages["info"].count(research.FORMULATION_DISCLAIMER) == 1
    assert not any("development corpus" in x.casefold() or "rights remain pending" in x.casefold() for x in ui.messages["warning"] + ui.messages["info"])
    assert api_calls == ["http://127.0.0.1:11434/api/tags"]


def test_ui_shows_citation_warning_only_when_result_has_it(monkeypatch):
    ui, _ = _setup_ui(monkeypatch, clicked="Generate Explanation", state={"formulation_name": "Ashwagandharishta"})
    generated = VALID_MARKDOWN.replace("No source attribution or clinical claim is made.", "Charaka Samhita describes it.")
    monkeypatch.setattr(page, "build_formulation_explanation", lambda name, llm, **kwargs: {
        "canonical_name": name,
        "answer": generated,
        "model": "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M",
        "citation_warning": research.UNVERIFIED_CITATION_WARNING,
    })
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_formulation_explorer()
    assert generated in ui.messages["markdown"]
    assert ui.messages["warning"].count(research.UNVERIFIED_CITATION_WARNING) == 1


def test_ui_does_not_show_citation_warning_without_citations(monkeypatch):
    ui, _ = _setup_ui(monkeypatch, clicked="Generate Explanation", state={"formulation_name": "Triphala"})
    monkeypatch.setattr(page, "build_formulation_explanation", lambda name, llm, **kwargs: {
        "canonical_name": name, "answer": VALID_MARKDOWN, "model": "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M",
        "citation_warning": None,
    })
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_formulation_explorer()
    assert research.UNVERIFIED_CITATION_WARNING not in ui.messages["warning"]


def test_ui_displays_safe_unavailable_error_without_mock_fallback(monkeypatch):
    ui, _ = _setup_ui(monkeypatch, clicked="Generate Explanation", state={"formulation_name": "Triphala"})
    monkeypatch.setattr(page, "configured_provider", lambda: "mock")
    page.render_formulation_explorer()
    assert any("Mock mode is configured" in x for x in ui.messages["warning"])
    assert any("no answer was generated" in x for x in ui.messages["error"])


def test_ui_reports_ollama_unavailable_without_fallback(monkeypatch):
    ui, _ = _setup_ui(monkeypatch, clicked="Generate Explanation", state={"formulation_name": "Triphala"})
    monkeypatch.setattr(page, "build_formulation_explanation", lambda *a, **k: (_ for _ in ()).throw(OllamaError("offline")))
    class LocalModel:
        def __init__(self): pass
    monkeypatch.setattr("models.llm.OllamaLLM", LocalModel)
    page.render_formulation_explorer()
    assert any("AyurParam is unavailable" in x and "No fallback" in x for x in ui.messages["error"])


def test_application_routes_formulation_page_to_new_explorer(monkeypatch):
    import frontend.pages.ayurform_pages as router
    calls = []
    monkeypatch.setattr(page, "render_formulation_explorer", lambda: calls.append("formulations"))
    router.render_ayurform_page("Formulation Explorer")
    assert calls == ["formulations"]


def test_empty_formulation_page_shows_prompt_and_exactly_one_disclaimer(monkeypatch):
    ui, _ = _setup_ui(monkeypatch)
    page.render_formulation_explorer()
    assert ui.messages["info"].count(research.FORMULATION_DISCLAIMER) == 1
    assert any("choose a suggestion" in x.casefold() for x in ui.messages["info"]), ui.messages["info"]

