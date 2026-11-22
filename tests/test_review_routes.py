from ayurform_api import app
from fastapi.testclient import TestClient


def test_pending_review_route_precedes_generic_two_segment_route():
    paths = [route.path for route in app.routes if getattr(route, "methods", None) and "GET" in route.methods]
    assert paths.index("/api/reviews/pending") < paths.index("/api/{entity}/{item_id}")


def test_review_routes_are_registered():
    routes = {(route.path, tuple(sorted(route.methods))) for route in app.routes if getattr(route, "methods", None)}
    assert ("/api/reviews/pending", ("GET",)) in routes
    assert ("/api/reviews/{entity}/{item_id}", ("GET",)) in routes
    assert ("/api/reviews/{entity}/{item_id}/history", ("GET",)) in routes
    assert ("/api/reviews/{entity}/{item_id}/approve", ("POST",)) in routes
    assert ("/api/reviews/{entity}/{item_id}/reject", ("POST",)) in routes

def test_pending_path_is_not_parsed_as_integer():
    response = TestClient(app, raise_server_exceptions=False).get("/api/reviews/pending")
    assert response.status_code == 401  # authorization is reached; no path 422
