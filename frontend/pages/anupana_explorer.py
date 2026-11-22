"""Direct AyurParam-only Anupana Explorer."""
from __future__ import annotations

import httpx
import streamlit as st

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from ayurform_formulation_research import (
    FORMULATION_DISCLAIMER,
    UNVERIFIED_CITATION_WARNING,
    OllamaError,
    ResponseSchemaError,
    build_anupana_explanation,
    configured_provider,
    new_formulation_request_id,
)


POPULAR_ANUPANA = (
    "Water (Jala)", "Honey (Madhu)", "Milk (Ksheera)", "Ghee (Ghrita)",
    "Buttermilk (Takra)", "Warm water (Ushnodaka)", "Ginger juice (Ardraka Swarasa)",
    "Sugarcane juice (Ikshu Rasa)", "Herbal decoction (Kwatha)", "Rice water (Tandulodaka)",
    "Lemon juice (Nimbu Swarasa)", "Milk-based vehicle",
)


def _select_anupana(name: str) -> None:
    st.session_state["anupana_name"] = name
    st.session_state["anupana_suggestion_run"] = True
    st.session_state["anupana_answer"] = None
    st.session_state["anupana_error"] = None
    st.session_state["anupana_request_id"] = None


def _clear_anupana_answer() -> None:
    st.session_state["anupana_answer"] = None
    st.session_state["anupana_error"] = None
    st.session_state["anupana_request_id"] = None


def _model_status(provider: str) -> str:
    if provider != "ollama":
        return "Unavailable · Ollama provider is not configured"
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        response.raise_for_status()
        models = response.json().get("models", [])
        return "Available" if any(
            item.get("name") == OLLAMA_MODEL or item.get("model") == OLLAMA_MODEL for item in models
        ) else "Model not listed by Ollama"
    except (httpx.HTTPError, ValueError, AttributeError):
        return "Ollama unavailable"


def render_anupana_explorer() -> None:
    st.markdown(
        "<div class='anupana-page-intro'><div class='formulation-eyebrow'>AYURVEDA KNOWLEDGE WORKSPACE</div>"
        "<h1>Explore Anupana</h1><p>Explore an Anupana concept with a direct AyurParam explanation.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown("""
    <style>
    .anupana-page-intro{padding:.2rem 0 1rem;border-bottom:1px solid #E3E9E2;margin-bottom:1rem}
    .formulation-eyebrow{font:700 .68rem 'DM Sans',sans-serif;letter-spacing:.15em;color:#287557;margin-bottom:.35rem}
    .anupana-page-intro h1{margin:0 0 .25rem!important;color:#10372D!important}
    .anupana-page-intro p{margin:0;color:#64736A;font-size:.98rem}
    .anupana-result-label{font:700 .68rem 'DM Sans',sans-serif;letter-spacing:.13em;color:#287557;margin-bottom:.25rem}
    @media(max-width:640px){.anupana-page-intro{padding-bottom:.75rem}.anupana-page-intro p{font-size:.9rem}}
    </style>
    """, unsafe_allow_html=True)
    st.markdown("### Popular Anupana")
    st.caption("Suggestions are shortcuts for direct model generation, not approved records or verified relationships.")
    for start in range(0, len(POPULAR_ANUPANA), 3):
        columns = st.columns(3)
        for column, name in zip(columns, POPULAR_ANUPANA[start:start + 3]):
            with column:
                st.button(name, key=f"popular_anupana_{start}_{name.casefold().replace(' ', '_')}",
                          use_container_width=True, on_click=_select_anupana, args=(name,))

    provider = configured_provider()
    st.caption(f"Configured AyurParam · {OLLAMA_MODEL} · {_model_status(provider)}")
    st.info(FORMULATION_DISCLAIMER)
    if provider == "mock":
        st.warning("Mock mode is configured. No mock answer will be substituted for AyurParam.")
    elif provider != "ollama":
        st.warning(f"Configured provider '{provider}' is not supported for this direct AyurParam workflow.")

    with st.container(border=True):
        st.markdown("### Research an Anupana")
        name = st.text_input(
            "Anupana name",
            key="anupana_name",
            placeholder="For example, honey or warm water",
            on_change=_clear_anupana_answer,
        )
        st.caption("Only the entered Anupana name is sent for direct generation. No source retrieval or database lookup is used.")
        generate_clicked = st.button("Generate Explanation", type="primary", use_container_width=True,
                                     disabled=not name.strip() or provider != "ollama")

    suggestion_run = st.session_state.pop("anupana_suggestion_run", False)
    if generate_clicked or suggestion_run:
        st.session_state["anupana_answer"] = None
        st.session_state["anupana_error"] = None
        request_id = new_formulation_request_id()
        st.session_state["anupana_request_id"] = request_id
        if not name.strip():
            st.session_state["anupana_error"] = "Enter an Anupana name or select a suggestion."
        elif provider != "ollama":
            st.session_state["anupana_error"] = "AyurParam Ollama is not configured; no answer was generated."
        else:
            try:
                from models.llm import OllamaLLM
                with st.spinner("Generating a direct AyurParam explanation…"):
                    result = build_anupana_explanation(name, OllamaLLM(), request_id=request_id)
                st.session_state["anupana_answer"] = result
            except OllamaError:
                st.session_state["anupana_error"] = "AyurParam is unavailable or the request timed out. No fallback answer was used."
            except ResponseSchemaError as exc:
                st.session_state["anupana_error"] = f"AyurParam's response could not be safely displayed: {exc}"
            except (RuntimeError, ValueError) as exc:
                st.session_state["anupana_error"] = str(exc)
            except Exception:
                st.session_state["anupana_error"] = "The AyurParam request failed. No fallback answer was used."

    error = st.session_state.get("anupana_error")
    if error:
        st.error(error)
        if st.session_state.get("anupana_request_id"):
            with st.expander("Request diagnostics"):
                st.caption(f"Request ID: {st.session_state['anupana_request_id']}")
    result = st.session_state.get("anupana_answer")
    if result:
        with st.container(border=True):
            st.markdown("<div class='anupana-result-label'>AYURPARAM RESEARCH RESPONSE</div>", unsafe_allow_html=True)
            st.subheader(result["canonical_name"])
            st.caption(f"{result.get('model', OLLAMA_MODEL)} · Direct generation · Not source-verified")
            if result.get("result_category") == "model_abstention":
                st.info("AyurParam could not identify this Anupana.")
            # Render the original Markdown returned by the service without rewriting it.
            st.markdown(result["answer"])
            if result.get("citation_warning"):
                st.warning(UNVERIFIED_CITATION_WARNING)
        if result.get("request_id"):
            with st.expander("Generation diagnostics"):
                st.caption(f"Request ID: {result['request_id']}")
    elif not error:
        st.info("Enter an Anupana name or choose a suggestion to begin.")


__all__ = ["POPULAR_ANUPANA", "render_anupana_explorer"]
