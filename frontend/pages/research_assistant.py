"""Academic, source-grounded Research Assistant Streamlit interface."""
from __future__ import annotations

import re

import httpx
import streamlit as st

from config import (
    ACTIVE_CHROMA_COLLECTION,
    EMBEDDING_MODEL_NAME,
    KNOWLEDGE_MODE,
    OLLAMA_BASE_URL,
    OLLAMA_CONNECT_TIMEOUT_SECONDS,
    OLLAMA_GENERATION_TIMEOUT_SECONDS,
    OLLAMA_MODEL,
)
from ayurform_research import NO_EVIDENCE_MESSAGE, model_mode, research
from ayurform_research import CitationValidationError, SourceRegistryError
from models.llm import (
    OllamaError,
    OllamaGenerationTimeoutError,
    OllamaIncompleteResponseError,
    OllamaInvalidResponseError,
    OllamaModelLoadError,
    OllamaModelNotFoundError,
    OllamaServerError,
    OllamaUnavailableError,
    ResponseSchemaError,
)
from rag.retriever import ChromaRetrievalError, EmbeddingError, get_retriever
from utils.diagnostics import correlation_id


EXAMPLE_QUESTIONS = (
    "What are the traditionally described properties of Triphala?",
    "What is the traditional significance of Anupana in Ayurveda?",
    "What are the classical descriptions of Pippali?",
    "How is Agni described in Ayurvedic literature?",
    "What traditional uses of Haritaki are documented in the available sources?",
    "What is the relationship between Rasa, Guna and Vipaka?",
)


def _select_example(question: str) -> None:
    st.session_state["research_question"] = question
    st.session_state["research_example_run"] = True
    st.session_state["research_result"] = None
    st.session_state["research_error"] = None
    st.session_state["research_error_category"] = None
    st.session_state["research_error_diagnostics"] = None


def _clear_result() -> None:
    st.session_state["research_result"] = None
    st.session_state["research_error"] = None
    st.session_state["research_error_category"] = None
    st.session_state["research_error_diagnostics"] = None


def _model_status() -> str:
    if model_mode() != "ollama":
        return "Unavailable · AyurParam Ollama is not configured"
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        response.raise_for_status()
        models = response.json().get("models", [])
        if any(item.get("name") == OLLAMA_MODEL or item.get("model") == OLLAMA_MODEL for item in models):
            return "Available"
        return "Model not listed by Ollama"
    except (httpx.HTTPError, ValueError, AttributeError):
        return "Ollama unavailable"


def _retrieval_status() -> tuple[str, int | None]:
    try:
        count = int(get_retriever().collection.count())
        label = "Development-only collection" if KNOWLEDGE_MODE == "development" else "Production collection"
        return f"{label}: {ACTIVE_CHROMA_COLLECTION} · {count:,} passages", count
    except Exception:
        return f"ChromaDB unavailable · {ACTIVE_CHROMA_COLLECTION}", None


def _citation_summary(result: dict) -> str:
    references = []
    for row in result.get("evidence", []):
        pieces = [row.get("citation_id")]
        if row.get("source_title"):
            pieces.append(str(row["source_title"]))
        if row.get("page") is not None:
            pieces.append(f"p. {row['page']}")
        references.append(" · ".join(str(piece) for piece in pieces if piece))
    return "; ".join(references)


def _render_evidence(result: dict) -> None:
    evidence = result.get("evidence", [])
    if not evidence:
        return
    st.markdown("### Retrieved classical evidence")
    st.caption("Only the translated-source passages below were supplied to AyurParam. Modern clinical literature was not retrieved.")
    for row in evidence:
        citation_id = row.get("citation_id", "")
        safe_id = citation_id if re.fullmatch(r"P\d+", str(citation_id)) else "source"
        title = row.get("source_title") or "Source title not recorded"
        with st.expander(f"{citation_id} · {title}"):
            st.markdown(f'<span id="source-{safe_id}"></span>', unsafe_allow_html=True)
            metadata = []
            for label, value in (
                ("Author/editor", row.get("author")),
                ("Translator", row.get("translator")),
                ("Publisher", row.get("publisher")),
                ("Edition", row.get("edition")),
                ("Chapter", row.get("chapter")),
                ("Page", row.get("page")),
                ("Verse/reference", row.get("verse")),
                ("Stable passage ID", row.get("passage_id")),
                ("Provenance", row.get("provenance_role")),
                ("Rights status", row.get("rights_status")),
                ("Review status", row.get("review_status")),
                ("Usage scope", row.get("usage_scope")),
                ("Cosine distance", row.get("distance")),
            ):
                if value not in (None, ""):
                    metadata.append(f"{label}: {value}")
            st.caption(" · ".join(metadata) if metadata else "No additional source metadata was recorded.")
            st.text(row.get("text", ""))


def _render_history() -> None:
    history = st.session_state.get("research_history", [])
    if not history:
        return
    with st.expander("Recent research in this session"):
        st.caption("Session-only history; it is not an approved scholarly record.")
        for entry in reversed(history[-8:]):
            st.markdown(f"**Question:** {entry['question']}")
            if entry.get("answer"):
                if not entry.get("answer_complete", True):
                    st.warning("Incomplete AyurParam response; not a completed answer.")
                elif not entry.get("source_verified", False):
                    st.warning("This original AI response did not pass source verification.")
                st.markdown(entry["answer"])
            elif entry.get("limitations"):
                st.caption(entry["limitations"])
            if entry.get("references"):
                st.caption(f"Evidence references: {entry['references']}")


def _save_history(result: dict) -> None:
    history = st.session_state.setdefault("research_history", [])
    request_id = result.get("request_id")
    if request_id and any(item.get("request_id") == request_id for item in history):
        return
    history.append({
        "request_id": request_id,
        "question": result.get("question", ""),
        "answer": result.get("answer"),
        "limitations": result.get("limitations"),
        "references": _citation_summary(result),
        "source_verified": result.get("source_verified", False),
        "answer_complete": result.get("answer_complete", True),
    })
    del history[:-8]


def _render_result(result: dict) -> None:
    st.markdown("---")
    st.caption(f"Intent: {result.get('intent', 'academic research')} · {result.get('model', OLLAMA_MODEL)} · Request {result.get('request_id', 'unavailable')}")
    if result.get("mode") == "safety_abstention":
        st.warning(result.get("limitations"))
    elif result.get("mode") == "abstention":
        st.info(result.get("limitations") or NO_EVIDENCE_MESSAGE)
    else:
        if result.get("development_warning"):
            st.warning(result["development_warning"])
        if not result.get("answer_complete", True):
            st.warning("AyurParam's generation ended before completion. The original text below is incomplete and must not be treated as a completed answer.")
        if result.get("citation_validation_status") == "failed":
            st.warning("AyurParam's original answer is shown, but its citations did not validate against this request's retrieved passages. The answer is not source-verified.")
        elif result.get("evidence_validation_status") == "failed":
            st.warning("AyurParam's original answer is shown, but it did not pass source/evidence validation. The answer is not source-verified.")
        elif result.get("source_verified"):
            st.caption("Citation and evidence checks passed for this request; the answer remains an AI-generated interpretation of the displayed passages.")
        heading = "Incomplete AyurParam response" if not result.get("answer_complete", True) else (
            "AyurParam response · not source-verified" if not result.get("source_verified", False) else "Research Overview"
        )
        st.markdown(f"### {heading}")
        st.markdown(result.get("answer") or "")
        if result.get("limitations"):
            st.info(result["limitations"])
    _render_evidence(result)
    if result.get("request_id"):
        with st.expander("Research diagnostics"):
            st.caption(f"Correlation ID: {result['request_id']}")
            retrieval = result.get("retrieval", {})
            st.write(
                f"Retrieved candidates: {retrieval.get('retrieved_count', 0)} · "
                f"Eligible: {retrieval.get('eligible_count', 0)} · "
                f"Included in model context: {retrieval.get('context_passage_count', 0)}"
            )
            st.write(
                f"Answer complete: {result.get('answer_complete', True)} · "
                f"Citation validation: {result.get('citation_validation_status', 'not available')} · "
                f"Evidence validation: {result.get('evidence_validation_status', 'not available')} · "
                f"Source verified: {result.get('source_verified', False)} · "
                f"Finish reason: {retrieval.get('finish_reason', 'not available')}"
            )
            if result.get("validation_failure_category"):
                st.caption(f"Validation category: {result['validation_failure_category']}")
            if retrieval.get("retrieval_duration_ms") is not None:
                st.caption(
                    f"Retrieval: {retrieval['retrieval_duration_ms']} ms · "
                    f"Context construction: {retrieval.get('context_construction_duration_ms', 0)} ms · "
                    f"Generation: {retrieval.get('generation_duration_ms', 'not run')} ms"
                )
            if retrieval.get("excluded"):
                st.write("Excluded by filter: " + ", ".join(
                    f"{key}={value}" for key, value in retrieval["excluded"].items() if value
                ))


def render_research_assistant() -> None:
    # The dashboard queues a question before routing here. Consume it before
    # creating the keyed widget so Streamlit applies the value on this run.
    prefill = st.session_state.pop("research_prefill", None)
    if isinstance(prefill, str) and prefill.strip():
        st.session_state["research_question"] = prefill.strip()
        _clear_result()

    st.markdown(
        "<div class='research-page-intro'><div class='research-eyebrow'>AYURFORM · ACADEMIC WORKSPACE</div>"
        "<h1>AyurParam Research Assistant</h1><p>Academic literature exploration using source-grounded AI.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown("""
    <style>
    .research-page-intro{padding:.2rem 0 1rem;border-bottom:1px solid #E3E9E2;margin-bottom:1rem}
    .research-eyebrow{font:700 .68rem 'DM Sans',sans-serif;letter-spacing:.15em;color:#287557;margin-bottom:.35rem}
    .research-page-intro h1{margin:0 0 .25rem!important;color:#10372D!important}
    .research-page-intro p{margin:0;color:#64736A;font-size:.98rem}
    </style>
    """, unsafe_allow_html=True)

    provider = model_mode()
    model_state = _model_status()
    retrieval_state, indexed_count = _retrieval_status()
    status_cols = st.columns(3)
    with status_cols[0]:
        st.caption(f"AyurParam · {OLLAMA_MODEL} · {model_state}")
    with status_cols[1]:
        st.caption(f"BGE embeddings · {EMBEDDING_MODEL_NAME} · configured")
    with status_cols[2]:
        st.caption(retrieval_state)
    if provider == "mock":
        st.warning("Mock mode is active. The Research Assistant will not return mock answers or citations.")
    elif provider != "ollama":
        st.warning(f"Configured provider '{provider}' is not the required AyurParam Ollama provider.")

    st.markdown("### Example research questions")
    st.caption("Examples are query suggestions, not claims that the indexed corpus contains an answer.")
    for start in range(0, len(EXAMPLE_QUESTIONS), 2):
        columns = st.columns(2)
        for column, question in zip(columns, EXAMPLE_QUESTIONS[start:start + 2]):
            with column:
                key = "research_example_" + str(start) + "_" + str(EXAMPLE_QUESTIONS.index(question))
                st.button(question, key=key, use_container_width=True, on_click=_select_example, args=(question,))

    with st.container(border=True):
        query = st.text_area(
            "Research question",
            key="research_question",
            placeholder="Ask an academic question about concepts documented in the indexed sources…",
            height=140,
            on_change=_clear_result,
        )
        ask = st.button(
            "Ask Research Assistant",
            type="primary",
            use_container_width=True,
            disabled=provider != "ollama",
        )

    example_run = st.session_state.pop("research_example_run", False)
    if ask or example_run:
        st.session_state["research_result"] = None
        st.session_state["research_error"] = None
        st.session_state["research_error_category"] = None
        st.session_state["research_error_diagnostics"] = None
        if not query.strip():
            st.session_state["research_error"] = "Enter a research question."
        elif provider != "ollama":
            st.session_state["research_error"] = "AyurParam Ollama is unavailable or Mock mode is active; no fallback answer was used."
        else:
            request_id = correlation_id()
            st.session_state["research_request_id"] = request_id
            try:
                from models.llm import OllamaLLM
                with st.spinner("Creating the BGE query embedding, retrieving eligible passages, and preparing a grounded answer…"):
                    model = OllamaLLM(
                        connect_timeout=OLLAMA_CONNECT_TIMEOUT_SECONDS,
                        generation_timeout=OLLAMA_GENERATION_TIMEOUT_SECONDS,
                    )
                    result = research(query, model, request_id=request_id)
                st.session_state["research_result"] = result
                _save_history(result)
            except OllamaUnavailableError:
                st.session_state["research_error"] = "Ollama could not be reached. Check that the local Ollama service is running. No fallback answer was used."
                st.session_state["research_error_category"] = "ollama_unavailable"
            except OllamaModelNotFoundError:
                st.session_state["research_error"] = f"The configured AyurParam model ({OLLAMA_MODEL}) is not available in Ollama. No fallback answer was used."
                st.session_state["research_error_category"] = "model_missing"
            except OllamaModelLoadError:
                st.session_state["research_error"] = "Ollama could not load AyurParam. Check the Ollama model runner and available memory."
                st.session_state["research_error_category"] = "model_load_failure"
            except OllamaGenerationTimeoutError:
                st.session_state["research_error"] = "AyurParam did not complete within the configured generation timeout. The local model may still be loading or generating; no fallback answer was used."
                st.session_state["research_error_category"] = "generation_timeout"
            except OllamaIncompleteResponseError:
                st.session_state["research_error"] = "AyurParam reached its output limit before completing the answer. The incomplete response was withheld."
                st.session_state["research_error_category"] = "truncated_response"
            except OllamaInvalidResponseError as exc:
                st.session_state["research_error"] = "Ollama responded, but AyurParam returned no usable answer text. No fallback answer was used."
                st.session_state["research_error_category"] = "invalid_model_response"
                st.session_state["research_error_diagnostics"] = dict(exc.diagnostics)
            except OllamaServerError:
                st.session_state["research_error"] = "Ollama returned a server error while generating the answer. Check the Ollama service logs."
                st.session_state["research_error_category"] = "ollama_server_error"
            except OllamaError:
                st.session_state["research_error"] = "AyurParam generation failed. No fallback answer was used."
                st.session_state["research_error_category"] = "ollama_failure"
            except EmbeddingError:
                st.session_state["research_error"] = f"The BGE query embedding failed using {EMBEDDING_MODEL_NAME}. Check that the configured embedding model is available."
                st.session_state["research_error_category"] = "embedding_failure"
            except ChromaRetrievalError:
                st.session_state["research_error"] = f"ChromaDB could not retrieve passages from the selected collection ({ACTIVE_CHROMA_COLLECTION})."
                st.session_state["research_error_category"] = "chroma_retrieval_failure"
            except SourceRegistryError:
                st.session_state["research_error"] = "The source registry is unavailable or invalid. Research was stopped before generation."
                st.session_state["research_error_category"] = "source_registry_failure"
            except CitationValidationError as exc:
                citation_messages = {
                    "missing_citation": "AyurParam omitted a required passage citation. The answer was withheld.",
                    "unknown_citation_id": "AyurParam used an unknown citation ID. The answer was withheld.",
                    "citation_not_retrieved": "AyurParam cited a passage that was not retrieved for this request. The answer was withheld.",
                    "malformed_citation": "AyurParam used a malformed citation. Use of exact [P#] markers is required; the answer was withheld.",
                }
                st.session_state["research_error"] = citation_messages.get(exc.category, "AyurParam's citations did not pass validation. The answer was withheld.")
                st.session_state["research_error_category"] = exc.category
            except ResponseSchemaError as exc:
                detail = str(exc).casefold()
                if "citation" in detail or "passage" in detail:
                    st.session_state["research_error"] = "AyurParam's generated citations did not match the retrieved evidence. The answer was withheld."
                    st.session_state["research_error_category"] = "citation_validation_failure"
                else:
                    st.session_state["research_error"] = "AyurParam's answer did not pass evidence or safety validation. The answer was withheld."
                    st.session_state["research_error_category"] = "answer_validation_failure"
            except RuntimeError:
                st.session_state["research_error"] = "The configured AyurParam provider is unavailable or Mock mode is active. No fallback answer was used."
                st.session_state["research_error_category"] = "provider_unavailable"
            except Exception:
                st.session_state["research_error"] = "The Research Assistant encountered an unexpected retrieval or generation error. No fallback answer was used."
                st.session_state["research_error_category"] = "unexpected_failure"

    error = st.session_state.get("research_error")
    if error:
        st.error(error)
        if st.session_state.get("research_request_id"):
            with st.expander("Request diagnostics"):
                st.caption(f"Correlation ID: {st.session_state['research_request_id']}")
                if st.session_state.get("research_error_category"):
                    st.caption(f"Failure category: {st.session_state['research_error_category']}")
                details = st.session_state.get("research_error_diagnostics") or {}
                if details:
                    st.write(" · ".join(f"{key.replace('_', ' ')}: {value}" for key, value in details.items()))
    result = st.session_state.get("research_result")
    if result:
        _render_result(result)
    elif not error:
        if indexed_count == 0:
            st.info("No passages are currently indexed in the selected collection. Ask a question after an eligible source has been indexed.")
        else:
            st.info("Enter a research question or choose an example to begin.")
    _render_history()


__all__ = ["EXAMPLE_QUESTIONS", "render_research_assistant"]
