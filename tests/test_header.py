import frontend.header as header
from frontend.header import matching_pages
from frontend.navigation import PAGES, visible_sidebar_pages


def test_empty_global_search_lists_only_pages_available_to_the_current_user(monkeypatch):
    assert matching_pages("") == list(visible_sidebar_pages())
    monkeypatch.setenv("AYURFORM_ADMIN_EMAILS", "reviewer@example.org")
    admin_pages = matching_pages("", {"email": "reviewer@example.org"})
    assert set(admin_pages) == set(PAGES)
    assert len(admin_pages) == len(PAGES)
    assert "Review Dashboard" in admin_pages


def test_global_search_matches_page_titles_and_descriptions_case_insensitively():
    assert matching_pages("research library") == ["Research Library"]


def test_global_search_does_not_invent_results():
    assert matching_pages("nonexistent term") == []


def test_indexed_passage_search_returns_only_real_collection_rows(monkeypatch):
    class Collection:
        def count(self):
            return 1

        def get(self, where_document, limit, include):
            if where_document["$contains"].casefold() not in {"burning", "burning sensation"}:
                return {"ids": [], "documents": [], "metadatas": []}
            return {
                "ids": ["real-passage-1"],
                "documents": ["Indexed excerpt containing burning sensation."],
                "metadatas": [{"source_title": "Actual indexed title", "page_number": 7}],
            }

    class Client:
        def __init__(self, path):
            pass

        def get_collection(self, name):
            return Collection()

    header.search_indexed_passages.clear()
    monkeypatch.setattr(header, "PersistentClient", Client)
    available, results = header.search_indexed_passages("burning sensation")
    assert available is True
    assert [row["id"] for row in results] == ["real-passage-1"]
    assert results[0]["metadata"]["page_number"] == 7
    header.search_indexed_passages.clear()


def test_empty_collection_does_not_return_passage_matches(monkeypatch):
    class Collection:
        def count(self):
            return 0

    class Client:
        def __init__(self, path):
            pass

        def get_collection(self, name):
            return Collection()

    header.search_indexed_passages.clear()
    monkeypatch.setattr(header, "PersistentClient", Client)
    available, results = header.search_indexed_passages("burning")
    assert available is False
    assert results == []
    header.search_indexed_passages.clear()
