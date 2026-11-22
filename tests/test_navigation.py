from frontend.navigation import (
    PAGE_ICONS,
    SIDEBAR_GROUPS,
    SIDEBAR_PAGES,
    is_admin_user,
    model_status,
    normalize_page,
    visible_sidebar_pages,
)


def test_missing_or_invalid_page_state_defaults_to_dashboard():
    assert normalize_page(None) == "Dashboard"
    assert normalize_page("stale-page") == "Dashboard"
    assert normalize_page("Profile", (*visible_sidebar_pages(), "Profile")) == "Profile"


def test_every_sidebar_page_has_icon_and_valid_state():
    assert set(SIDEBAR_PAGES).issubset(PAGE_ICONS)
    for page in SIDEBAR_PAGES:
        assert normalize_page(page) == page

def test_primary_navigation_uses_ayurform_research_pages():
    assert "Symptom Analysis" not in SIDEBAR_PAGES
    assert "Analysis History" not in SIDEBAR_PAGES
    assert "Saved References" not in SIDEBAR_PAGES
    assert "Research Library" in SIDEBAR_PAGES
    for page in ("Dashboard", "Dravya Explorer", "Formulation Explorer", "Anupana Explorer", "Research Assistant", "Classical Sources", "Review Dashboard", "About", "Settings"):
        assert page in SIDEBAR_PAGES


def test_sidebar_groups_follow_the_requested_information_architecture():
    assert list(SIDEBAR_GROUPS) == [
        "Workspace",
        "Explore Knowledge",
        "Research",
        "Management",
    ]
    assert SIDEBAR_GROUPS["Workspace"] == ("Dashboard",)
    assert SIDEBAR_GROUPS["Explore Knowledge"] == (
        "Dravya Explorer", "Formulation Explorer", "Anupana Explorer"
    )
    assert SIDEBAR_GROUPS["Research"] == (
        "Research Assistant", "Classical Sources", "Research Library"
    )
    assert SIDEBAR_GROUPS["Management"] == (
        "Review Dashboard", "Settings", "About"
    )


def test_review_dashboard_is_hidden_without_allowlisted_admin(monkeypatch):
    monkeypatch.setenv("AYURFORM_ADMIN_EMAILS", "reviewer@example.org")
    assert is_admin_user({"email": "other@example.org"}) is False
    assert "Review Dashboard" not in visible_sidebar_pages({"email": "other@example.org"})
    assert "Review Dashboard" not in visible_sidebar_pages(None)
    assert normalize_page("Review Dashboard", visible_sidebar_pages({"email": "other@example.org"})) == "Dashboard"
    assert "Review Dashboard" in visible_sidebar_pages({"email": "REVIEWER@example.org"})


def test_global_page_search_respects_review_dashboard_visibility(monkeypatch):
    from frontend.header import matching_pages

    monkeypatch.setenv("AYURFORM_ADMIN_EMAILS", "reviewer@example.org")
    assert "Review Dashboard" not in matching_pages("review", {"email": "other@example.org"})
    assert "Review Dashboard" in matching_pages("review", {"email": "reviewer@example.org"})
    assert "Dashboard" in matching_pages("", {"email": "other@example.org"})


def test_model_status_confirms_the_exact_ollama_model(monkeypatch):
    import frontend.navigation as navigation

    class FakeResponse:
        def raise_for_status(self):
            return None

        @staticmethod
        def json():
            return {"models": [{"name": navigation.OLLAMA_MODEL}]}

    monkeypatch.setattr(navigation, "LLM_MODE", "")
    monkeypatch.setattr(navigation, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(navigation.httpx, "get", lambda *args, **kwargs: FakeResponse())
    model_status.clear()
    try:
        status = model_status()
        assert status["available"] is True
        assert status["state"] == "available"
        assert status["model"] == navigation.OLLAMA_MODEL
    finally:
        model_status.clear()


def test_model_status_does_not_claim_mock_or_unavailable_model_is_ready(monkeypatch):
    import frontend.navigation as navigation

    monkeypatch.setattr(navigation, "LLM_MODE", "mock")
    monkeypatch.setattr(navigation, "LLM_PROVIDER", "ollama")
    model_status.clear()
    try:
        status = model_status()
        assert status["state"] == "mock"
        assert status["available"] is False
        assert "Mock" in str(status["label"])
    finally:
        model_status.clear()


def test_sidebar_styles_use_light_palette_reduced_motion_and_item_interactions(monkeypatch):
    import frontend.navigation as navigation

    rendered = []
    monkeypatch.setattr(navigation.st, "html", lambda value: rendered.append(value))
    navigation._sidebar_styles(animate_entrance=True)
    styles = rendered[0]
    assert "#FDFCF8" in styles
    assert "#EDF3EC" in styles
    assert "#0C342B" not in styles
    assert "prefers-reduced-motion:reduce" in styles
    for page in SIDEBAR_PAGES:
        selector = f".st-key-ayur_nav_item_{navigation._slug(page)}"
        assert selector in styles
        assert f"{selector} .stButton>button:hover" in styles
