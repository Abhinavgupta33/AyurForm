import httpx
import pytest
import time

from models.llm import (
    OllamaError,
    OllamaGenerationTimeoutError,
    OllamaIncompleteResponseError,
    OllamaInvalidResponseError,
    OllamaModelLoadError,
    OllamaModelNotFoundError,
    OllamaUnavailableError,
    OllamaLLM,
)


def test_ollama_success_and_payload(monkeypatch):
    seen = {}
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "hello"}}
    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return Response()
    monkeypatch.setattr(httpx, "post", post)
    assert OllamaLLM(model_name="test:model", temperature=.4).generate("question", 22, "system") == "hello"
    assert seen["url"].endswith("/api/chat")
    assert seen["json"]["model"] == "test:model"
    assert seen["json"]["format"]["required"] == ["extracted_symptoms", "possible_concepts", "evidence_summary", "limitations"]
    assert seen["json"]["format"]["additionalProperties"] is False
    assert seen["json"]["messages"] == [{"role":"system","content":"system"},{"role":"user","content":"question"}]
    assert seen["json"]["options"] == {"temperature": .4, "num_predict": 22}


def test_ollama_research_context_window_and_output_budget_are_sent(monkeypatch):
    seen = {}

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "answer [P1]."}, "done_reason": "stop"}

    monkeypatch.setattr(httpx, "post", lambda url, **kwargs: (seen.update(kwargs) or Response()))
    OllamaLLM().generate("question", max_new_tokens=800, num_ctx=4096, format_schema=False)
    assert seen["json"]["options"] == {"temperature": .2, "num_predict": 800, "num_ctx": 4096}


def test_ollama_rejects_context_window_without_output_capacity(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: pytest.fail("Ollama must not be called"))
    with pytest.raises(ValueError, match="context window must exceed"):
        OllamaLLM().generate("question", max_new_tokens=800, num_ctx=800, format_schema=False)


def test_ollama_forwards_dravyas_custom_schema(monkeypatch):
    seen = {}

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "{}"}}

    monkeypatch.setattr(httpx, "post", lambda url, **kwargs: (seen.update(kwargs) or Response()))
    schema = {"type": "object", "required": ["canonical_name", "claims"]}
    OllamaLLM().generate("extract a Dravya profile", format_schema=schema)
    assert seen["json"]["format"] == schema


def test_ollama_natural_language_request_omits_format_schema(monkeypatch):
    seen = {}

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "Natural language answer."}}

    monkeypatch.setattr(httpx, "post", lambda url, **kwargs: (seen.update(kwargs) or Response()))
    answer = OllamaLLM().generate("Explain from evidence", system="Use natural language", format_schema=False)
    assert answer == "Natural language answer."
    assert "format" not in seen["json"]
    assert seen["json"]["stream"] is False


def test_ollama_alternate_response_field_is_extracted_without_rewriting(monkeypatch):
    original_markdown = "## Heading\n\nA source-grounded sentence [P1]."
    class Response:
        status_code = 200
        def json(self): return {"response": original_markdown, "done": True, "done_reason": "stop"}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    assert OllamaLLM().generate("question", format_schema=False) == original_markdown


@pytest.mark.parametrize("payload", [
    {"message": {"content": ""}, "done_reason": "stop"},
    {"message": {"content": "  \n "}, "done_reason": "stop"},
    {"done": True, "done_reason": "stop"},
    {"message": None, "done_reason": "stop"},
])
def test_ollama_success_status_with_missing_or_empty_text_is_rejected(monkeypatch, payload):
    class Response:
        status_code = 200
        def json(self): return payload
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with pytest.raises(OllamaInvalidResponseError, match="no usable answer text"):
        OllamaLLM().generate("question", format_schema=False)


def test_empty_response_diagnostics_are_development_only_and_privacy_safe(monkeypatch, caplog):
    import models.llm as llm_module
    monkeypatch.setattr(llm_module, "KNOWLEDGE_MODE", "development")
    class Response:
        status_code = 200
        def json(self):
            return {"message": {"content": ""}, "done_reason": "stop", "eval_count": 1, "prompt_eval_count": 1374}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with pytest.raises(OllamaInvalidResponseError):
        OllamaLLM().generate("private prompt", request_id="empty-shape-1", format_schema=False)
    assert "correlation" not in caplog.text
    assert "request_id=empty-shape-1" in caplog.text
    assert "root_keys=['done_reason', 'eval_count', 'message', 'prompt_eval_count']" in caplog.text
    assert "extracted_text_empty=True" in caplog.text
    assert "extracted_text_length=0" in caplog.text
    assert "prompt_eval_count=1374" in caplog.text
    assert "raw_response_length=0" in caplog.text
    assert "answer_extraction_succeeded=False" in caplog.text
    assert "private prompt" not in caplog.text


def test_ollama_failures(monkeypatch):
    class Response:
        status_code = 404
        def raise_for_status(self): raise httpx.HTTPStatusError("missing", request=None, response=None)
        def json(self): return {}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with pytest.raises(OllamaModelNotFoundError, match="not installed"):
        OllamaLLM().generate("x")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.TimeoutException("late")))
    with pytest.raises(OllamaGenerationTimeoutError, match="timeout"):
        OllamaLLM().generate("x")


def test_ollama_malformed_response(monkeypatch):
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"done": True}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with pytest.raises(OllamaInvalidResponseError, match="no usable answer text"):
        OllamaLLM().generate("x")


def test_research_timeout_has_bounded_separate_connect_and_generation_limits(monkeypatch):
    seen = {}

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "answer"}, "done_reason": "stop"}

    monkeypatch.setattr(httpx, "post", lambda url, **kwargs: (seen.update(kwargs) or Response()))
    client = OllamaLLM(connect_timeout=8, generation_timeout=480)
    assert client.generate("question") == "answer"
    timeout = seen["timeout"]
    assert timeout.connect == 8
    assert timeout.read == 480
    assert timeout.write == 480
    assert timeout.pool == 8


def test_model_load_delay_within_generation_timeout_completes(monkeypatch):
    seen = {}

    class Response:
        status_code = 200
        def json(self): return {"message": {"content": "loaded and ready"}, "done_reason": "stop"}

    def delayed_post(url, **kwargs):
        seen.update(kwargs)
        time.sleep(0.01)  # Simulate a cold model load without contacting Ollama.
        return Response()

    monkeypatch.setattr(httpx, "post", delayed_post)
    client = OllamaLLM(connect_timeout=1, generation_timeout=5)
    assert client.generate("question") == "loaded and ready"
    assert seen["timeout"].connect == 1
    assert seen["timeout"].read == 5


def test_connection_failure_is_distinct_from_generation_timeout(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("offline")))
    with pytest.raises(OllamaUnavailableError):
        OllamaLLM().generate("question")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    with pytest.raises(OllamaGenerationTimeoutError):
        OllamaLLM().generate("question")


def test_model_loading_http_error_is_distinguished_without_logging_response_body(monkeypatch, caplog):
    class Response:
        status_code = 500
        def json(self): return {"error": "model runner failed to load model: not enough memory"}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with pytest.raises(OllamaModelLoadError):
        OllamaLLM().generate("question", request_id="load-test-1")
    assert "model_load_failure" in caplog.text
    assert "not enough memory" not in caplog.text


def test_research_rejects_token_limit_truncation_as_a_distinct_error(monkeypatch):
    partial_text = "partial answer"
    class Response:
        status_code = 200
        content = b'{"message":{"content":"partial answer"},"done":true,"done_reason":"length"}'
        def json(self):
            return {"message": {"content": partial_text}, "done": True, "done_reason": "length", "eval_count": 1200}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with pytest.raises(OllamaIncompleteResponseError, match="token limit") as error:
        OllamaLLM().generate("question", reject_truncated=True, request_id="truncate-1")
    assert error.value.response_text == partial_text
    assert error.value.finish_reason == "length"
