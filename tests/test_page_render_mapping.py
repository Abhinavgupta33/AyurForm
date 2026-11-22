from frontend.pages.ayurform_pages import content_route_for_page


def test_review_dashboard_maps_only_to_review_renderer():
    assert content_route_for_page("Review Dashboard") == "review"
    assert content_route_for_page("Dravya Explorer") == "explorer"
    assert content_route_for_page("Research Assistant") == "research"


def test_unknown_or_legacy_page_cannot_fall_through_to_dravya_explorer():
    assert content_route_for_page("Symptom Analysis") == "unknown"
    assert content_route_for_page("Review") == "unknown"
