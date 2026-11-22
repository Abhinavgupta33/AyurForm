from frontend.auth_pages import _auth_form
from frontend.navigation import SIDEBAR_PAGES

def test_auth_pages_use_ayurform_branding():
    for mode in ("login", "signup"):
        page = _auth_form(mode, False)
        assert "AYURFORM AI" in page
        assert "AyurSutra" not in page

def test_primary_navigation_uses_research_library_and_no_symptom_pages():
    assert "Research Library" in SIDEBAR_PAGES
    assert not any("Symptom" in page or "History" in page for page in SIDEBAR_PAGES)
