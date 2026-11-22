from contextlib import nullcontext
import sys
from types import SimpleNamespace

import pytest

from frontend.pages import ayurform_dashboard as dashboard


class StopRender(Exception):
    pass


class FakeStreamlit:
    def __init__(self, *, clicked=None, query="", state=None):
        self.clicked = clicked
        self.query = query
        self.session_state = dict(state or {})
        self.markdown_calls = []
        self.buttons = []
        self.errors = []
        self.captions = []
        self.text_inputs = []
        self.html_calls = []

    def html(self, value, **kwargs): self.html_calls.append((value, kwargs))
    def markdown(self, value, **kwargs): self.markdown_calls.append(value)
    def caption(self, value, **kwargs): self.captions.append(value)
    def container(self, **kwargs): return nullcontext()
    def form(self, *args, **kwargs): return nullcontext()
    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [nullcontext() for _ in range(count)]
    def text_input(self, *args, **kwargs):
        self.text_inputs.append((args, kwargs))
        return self.query
    def form_submit_button(self, label, **kwargs): return self.clicked == label
    def button(self, label, **kwargs):
        self.buttons.append(label)
        return self.clicked == label
    def error(self, message): self.errors.append(message)
    def rerun(self): raise StopRender()


def _setup(monkeypatch, *, clicked=None, query="", counts=None, user=None):
    ui = FakeStreamlit(clicked=clicked, query=query)
    monkeypatch.setattr(dashboard, "st", ui)
    monkeypatch.setattr(dashboard, "_snapshot", lambda: {"connected": True, "passages": 1555, "sources": []})
    monkeypatch.setattr(dashboard, "_count", lambda table: (counts or {}).get(table, 0))
    monkeypatch.setattr(dashboard, "_model_status", lambda: "Available")
    monkeypatch.setattr(dashboard, "_embedding_status", lambda: ("Configured", "Weights load on first retrieval"))
    monkeypatch.setattr(dashboard, "_database_status", lambda: ("Connected", "Postgresql · health check passed"))
    return ui, user


def test_research_query_queue_rejects_empty_and_preserves_question():
    state = {"page": "Dashboard"}
    assert dashboard.queue_research_query("  ", state) is False
    assert state == {"page": "Dashboard"}
    assert dashboard.queue_research_query("  What is Anupana?  ", state) is True
    assert state == {"page": "Research Assistant", "research_prefill": "What is Anupana?"}


def test_admin_shortcut_uses_existing_allowlist():
    assert dashboard.is_admin_email(" REVIEWER@example.org ", configured="reviewer@example.org,other@example.org")
    assert not dashboard.is_admin_email("user@example.org", configured="reviewer@example.org")
    assert not dashboard.is_admin_email(None, configured="reviewer@example.org")


def test_registered_source_count_includes_only_production_cleared_records(monkeypatch):
    records = [
        {"usage_scope": "production", "rights_status": "licensed"},
        {"usage_scope": "development_only", "rights_status": "licensed"},
        {"usage_scope": "production", "rights_status": "pending"},
    ]
    monkeypatch.setitem(sys.modules, "ayurform_store", SimpleNamespace(rows=lambda *args, **kwargs: records))
    assert dashboard._count("sources") == 1


def test_dashboard_renders_real_kpis_status_and_academic_workspace(monkeypatch):
    ui, user = _setup(
        monkeypatch,
        counts={"dravya": 2, "formulations": 0, "anupana_relationships": 1, "sources": 1},
    )
    dashboard.render_dashboard(user)
    rendered = "\n".join(map(str, ui.markdown_calls))
    for expected in (
        "AYURFORM AI · RESEARCH WORKSPACE",
        "Ancient Wisdom.",
        "Evidence-Led Discovery.",
        "Dravya records",
        "Formulations",
        "Anupana relationships",
        "Indexed passages",
        "Registered sources",
        "1,555",
        "Development-only · not production-approved",
        "AYURFORM AI",
        "Explore the knowledge domains",
        "Research deeper with AI",
        "Classical sources &amp; research tools",
        "Botanical leaf illustration",
        "Traditional vessel illustration",
        "Water drop and ripple illustration",
    ):
        assert expected in rendered
    assert "Review Dashboard" not in rendered
    assert "Review Dashboard" not in ui.buttons


def test_start_research_submits_form_and_routes_prefill(monkeypatch):
    ui, _ = _setup(monkeypatch, clicked="Start Research →", query="What is traditionally said about Tulsi?")
    with pytest.raises(StopRender):
        dashboard.render_dashboard()
    assert ui.session_state["page"] == "Research Assistant"
    assert ui.session_state["research_prefill"] == "What is traditionally said about Tulsi?"
    assert ui.text_inputs[0][1]["placeholder"] == "What would you like to explore today?"


def test_empty_research_submission_shows_validation_and_does_not_navigate(monkeypatch):
    ui, _ = _setup(monkeypatch, clicked="Start Research →", query=" ")
    dashboard.render_dashboard()
    assert "Enter a research question to continue." in ui.errors
    assert ui.session_state.get("page") is None
    assert "research_prefill" not in ui.session_state


def test_suggestion_navigates_with_selected_query_and_review_is_admin_only(monkeypatch):
    suggestion = dashboard.RESEARCH_SUGGESTIONS[2]
    ui, _ = _setup(monkeypatch, clicked=suggestion)
    with pytest.raises(StopRender):
        dashboard.render_dashboard()
    assert ui.session_state["page"] == "Research Assistant"
    assert ui.session_state["research_prefill"] == suggestion

    admin_ui, _ = _setup(monkeypatch)
    monkeypatch.setattr(dashboard, "is_admin_email", lambda email: True)
    dashboard.render_dashboard({"email": "admin@example.org"})
    assert "Review Dashboard" in "\n".join(map(str, admin_ui.markdown_calls))
    assert "Open review queue" in admin_ui.buttons


@pytest.mark.parametrize(
    ("button", "page"),
    [
        ("Open Dravya Explorer", "Dravya Explorer"),
        ("Open Formulation Explorer", "Formulation Explorer"),
        ("Open Anupana Explorer", "Anupana Explorer"),
        ("Open Research Assistant", "Research Assistant"),
        ("Browse sources", "Classical Sources"),
        ("Open library", "Research Library"),
    ],
)
def test_dashboard_domain_and_tool_actions_route_to_registered_pages(monkeypatch, button, page):
    ui, _ = _setup(monkeypatch, clicked=button)
    calls = []

    def navigate(target):
        calls.append(target)
        ui.session_state["page"] = target
        raise StopRender()

    monkeypatch.setattr(dashboard, "_go", navigate)
    with pytest.raises(StopRender):
        dashboard.render_dashboard()
    assert calls == [page]
    assert ui.session_state["page"] == page


def test_suggestions_are_queries_and_open_research_assistant(monkeypatch):
    assert dashboard.RESEARCH_SUGGESTIONS == (
        "Explore the traditional properties of Tulsi",
        "Investigate the ingredients of Chyawanprash",
        "Understand the concept of Anupana",
        "Explore classical references for Ashwagandha",
    )
    for index, suggestion in enumerate(dashboard.RESEARCH_SUGGESTIONS):
        ui, _ = _setup(monkeypatch, clicked=suggestion)
        with pytest.raises(StopRender):
            dashboard.render_dashboard()
        assert ui.session_state["page"] == "Research Assistant"
        assert ui.session_state["research_prefill"] == suggestion


def test_kpi_and_status_markup_distinguish_real_zeroes_and_development_scope(monkeypatch):
    ui, _ = _setup(
        monkeypatch,
        counts={"dravya": 0, "formulations": 0, "anupana_relationships": 0, "sources": 0},
    )
    dashboard.render_dashboard()
    rendered = "\n".join(map(str, ui.markdown_calls))
    assert "No approved records yet" in rendered
    assert "No approved relationships yet" in rendered
    assert "Development-only · not production-approved" in rendered
    assert "1,555" in rendered
    assert "DEVELOPMENT-ONLY" not in rendered


def test_dashboard_motion_is_scoped_reduced_motion_aware_and_interactive(monkeypatch):
    ui, _ = _setup(monkeypatch)
    dashboard.render_dashboard()
    styles = next(value for value, _ in ui.html_calls if "<style>" in value)
    script, options = next((value, options) for value, options in ui.html_calls if "<script>" in value)

    assert options == {"unsafe_allow_javascript": True}
    assert "prefers-reduced-motion:reduce" in styles
    assert "af-initial-entrance" in styles
    assert "af-card-hover" in styles
    assert "focus-within" in styles
    assert "af-light-drift" in styles
    assert "af-ai-orbit" in styles
    assert "IntersectionObserver" in script
    assert "MutationObserver" in script
    assert "prefers-reduced-motion: reduce" in script
    assert "pointermove" in script
    assert "sessionStorage" in script
    assert "st-key-ayurform_dashboard" in script
    assert "fetch(" not in script


def test_dashboard_animated_stats_remain_bound_to_real_count_markup(monkeypatch):
    ui, _ = _setup(monkeypatch, counts={"dravya": 3, "formulations": 0, "anupana_relationships": 1, "sources": 2})
    dashboard.render_dashboard()
    rendered = "\n".join(map(str, ui.markdown_calls))

    assert 'data-af-count-target="3" data-af-count-key="dravya-records"' in rendered
    assert 'data-af-count-target="0" data-af-count-key="formulations"' in rendered
    assert 'data-af-count-target="1" data-af-count-key="anupana-relationships"' in rendered
    assert 'data-af-count-target="2" data-af-count-key="registered-sources"' in rendered


def test_dashboard_motion_markup_has_distinct_botanical_and_ai_art(monkeypatch):
    ui, _ = _setup(monkeypatch)
    dashboard.render_dashboard()
    rendered = "\n".join(map(str, ui.markdown_calls))

    assert "af-leaf-sway" in rendered
    assert "af-art-particle" in rendered
    assert "af-art-node" in rendered
    assert "af-ai-visual" in rendered
    assert "af-ai-link" in rendered
    assert "aria-hidden=\"true\"" in rendered
