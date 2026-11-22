from contextlib import nullcontext

import frontend.pages.ayurform_pages as page_module


class FakeStreamlit:
    def __init__(self, mode, session_state=None):
        self.mode = mode
        self.session_state = session_state if session_state is not None else {}
        self.messages = {"markdown": [], "caption": [], "info": [], "warning": [], "success": [], "error": []}
        self.expander_labels = []
        self.clicked = None

    def markdown(self, value, **kwargs): self.messages["markdown"].append(value)
    def subheader(self, value, **kwargs): self.messages["markdown"].append(value)
    def caption(self, value, **kwargs): self.messages["caption"].append(value)
    def info(self, value, **kwargs): self.messages["info"].append(value)
    def warning(self, value, **kwargs): self.messages["warning"].append(value)
    def success(self, value, **kwargs): self.messages["success"].append(value)
    def error(self, value, **kwargs): self.messages["error"].append(value)
    def radio(self, *args, **kwargs): return self.mode
    def text_input(self, label, **kwargs): return self.session_state.get(kwargs.get("key"), "Tulsi")
    def button(self, label, **kwargs):
        if self.clicked is None or self.clicked not in {label, kwargs.get("key")}:
            return False
        callback=kwargs.get("on_click")
        if callback:
            callback(*(kwargs.get("args") or ()))
        return True
    def container(self, **kwargs): return nullcontext()
    def expander(self, label, **kwargs):
        self.expander_labels.append(label)
        return nullcontext()
    def columns(self, count, **kwargs): return [nullcontext() for _ in range(count if isinstance(count, int) else len(count))]
    def spinner(self, *args, **kwargs): return nullcontext()
    def json(self, value): pass


class JsonResponse:
    def __init__(self, payload, status=200): self.payload, self.status_code = payload, status
    def json(self): return self.payload
    def raise_for_status(self): pass


def _install_ui_mocks(monkeypatch, mode, *, session_state=None):
    import config
    ui = FakeStreamlit(mode, session_state)
    monkeypatch.setattr(page_module, "st", ui)
    monkeypatch.setattr(config, "KNOWLEDGE_MODE", "development")
    monkeypatch.setattr(page_module.httpx, "get", lambda *a, **k: JsonResponse({"models": [{"name": "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M"}]}))
    monkeypatch.setattr("ayurform_dravya_research.model_mode", lambda: "ollama")
    return ui


def test_direct_mode_has_no_corpus_warning_and_one_unverified_disclaimer(monkeypatch):
    ui = _install_ui_mocks(monkeypatch, "Direct AyurParam")
    page_module.render_ayurform_page("Dravya Explorer")
    disclaimer = "Generated directly by AyurParam. Not verified against retrieved classical sources."
    assert ui.messages["info"].count(disclaimer) == 1
    assert not any("Development corpus selected" in message or "rights remain pending" in message for message in ui.messages["warning"] + ui.messages["info"])
    assert not any("Development corpus selected" in message for message in ui.messages["caption"])


def test_source_grounded_mode_retains_development_rights_warning(monkeypatch):
    ui = _install_ui_mocks(monkeypatch, "Source-grounded RAG")
    page_module.render_ayurform_page("Dravya Explorer")
    assert any("Development corpus selected" in message and "rights remain pending" in message for message in ui.messages["warning"])
    assert not ui.messages["info"]


def test_approved_record_search_still_calls_api_and_shows_results(monkeypatch):
    ui = _install_ui_mocks(monkeypatch, "Search approved records")
    ui.clicked = "Search approved records"
    calls = []
    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return JsonResponse({"items": [{"canonical_name": "Tulsi"}]})
    monkeypatch.setattr(page_module.httpx, "get", get)
    page_module.render_ayurform_page("Dravya Explorer")
    assert calls and calls[0][1]["params"]["search"] == "Tulsi"
    assert "Tulsi" in ui.messages["markdown"]


def test_direct_long_markdown_is_passed_to_streamlit_markdown(monkeypatch):
    answer = "## Introduction\n\nTulsi overview.\n\n### Ayurvedic Properties\n\n- Uncertain rasa\n- Properties not established here"
    state = {
        "dravya_mode_active": "Direct AyurParam",
        "dravya_research_answer": {
            "mode": "direct", "canonical_name": "Tulsi", "model": "AyurParam",
            "answer": answer, "limitations": "Generated directly by AyurParam. Not verified against retrieved classical sources.",
        },
    }
    ui = _install_ui_mocks(monkeypatch, "Direct AyurParam", session_state=state)
    page_module.render_ayurform_page("Dravya Explorer")
    assert answer in ui.messages["markdown"]
    assert sum("Generated directly by AyurParam. Not verified against retrieved classical sources." in message for message in ui.messages["info"] + ui.messages["warning"]) == 1


def test_popular_suggestions_set_mode_specific_state():
    for mode, target in (
        ("Direct AyurParam", "dravya_ai_name"),
        ("Source-grounded RAG", "dravya_ai_name"),
        ("Search approved records", "search_dravya"),
    ):
        state = {"dravya_research_answer": {"mode": "stale"}}
        page_module.apply_popular_dravya_selection("Pippali", mode, state)
        assert state[target] == "Pippali"
        assert state["dravya_mode"] == mode
        assert state["dravya_research_answer"] is None
        assert ("dravya_suggestion_run" in state) == (mode != "Search approved records")
        assert ("dravya_search_suggestion" in state) == (mode == "Search approved records")


def test_direct_popular_chip_populates_and_generates(monkeypatch):
    ui = _install_ui_mocks(monkeypatch, "Direct AyurParam")
    ui.clicked = "popular_dravya_Direct AyurParam_Tulsi"
    calls = []
    import ayurform_dravya_research as research
    monkeypatch.setattr(research, "build_direct_dravya_answer", lambda name, model: calls.append(name) or {
        "mode": "direct", "canonical_name": name, "model": "AyurParam", "answer": "## Intro\n\nText.",
        "limitations": "Generated directly by AyurParam. Not verified against retrieved classical sources.", "evidence": [],
    })
    page_module.render_ayurform_page("Dravya Explorer")
    assert calls == ["Tulsi"]


def test_rag_popular_chip_populates_and_invokes_existing_retrieval_path(monkeypatch):
    ui = _install_ui_mocks(monkeypatch, "Source-grounded RAG")
    ui.clicked = "popular_dravya_Source-grounded RAG_Pippali"
    calls = []
    import ayurform_dravya_research as research
    monkeypatch.setattr(research, "build_dravya_answer", lambda name, model: calls.append(name) or {
        "mode": "abstention", "canonical_name": name, "model": "AyurParam", "answer": "",
        "limitations": "No eligible source evidence.", "evidence": [],
    })
    page_module.render_ayurform_page("Dravya Explorer")
    assert calls == ["Pippali"]


def test_approved_mode_popular_chip_searches_selected_name(monkeypatch):
    ui = _install_ui_mocks(monkeypatch, "Search approved records")
    ui.clicked = "popular_dravya_Search approved records_Amla"
    calls = []
    monkeypatch.setattr(page_module.httpx, "get", lambda *a, **k: calls.append(k) or JsonResponse({"items": []}))
    page_module.render_ayurform_page("Dravya Explorer")
    assert calls and calls[0]["params"]["search"] == "Amla"
    assert any("No approved Dravya record" in message for message in ui.messages["info"])


def test_clear_approved_search_resets_search_state(monkeypatch):
    ui = _install_ui_mocks(monkeypatch, "Search approved records", session_state={
        "search_dravya": "Tulsi", "dravya_search_results": [{"canonical_name": "Tulsi"}],
        "dravya_search_query": "Tulsi", "dravya_search_suggestion": True,
    })
    monkeypatch.setattr(page_module, "st", ui)
    page_module._clear_approved_dravya_search()
    assert ui.session_state["search_dravya"] == ""
    assert ui.session_state["dravya_search_results"] is None
    assert ui.session_state["dravya_search_query"] == ""
    assert ui.session_state["dravya_search_suggestion"] is False


def test_approved_search_displays_api_failure_separately(monkeypatch):
    ui = _install_ui_mocks(monkeypatch, "Search approved records")
    ui.clicked = "Search approved records"
    def failed(*args, **kwargs):
        request=httpx.Request("GET", "http://localhost/api/dravya")
        response=httpx.Response(503, request=request)
        raise httpx.HTTPStatusError("unavailable", request=request, response=response)
    import httpx
    monkeypatch.setattr(page_module.httpx, "get", failed)
    page_module.render_ayurform_page("Dravya Explorer")
    assert any("HTTP 503" in message for message in ui.messages["error"])
