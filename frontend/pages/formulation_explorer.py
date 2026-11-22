"""Direct AyurParam-only Formulation Explorer UI."""
from __future__ import annotations

import httpx
import streamlit as st

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from ayurform_formulation_research import (
    FORMULATION_DISCLAIMER,
    FORMULATION_ABSTENTION_MESSAGE,
    FORMULATION_RELEVANCE_ERROR,
    FormulationAbstentionError,
    FormulationRelevanceError,
    UNVERIFIED_CITATION_WARNING,
    OllamaError,
    ResponseSchemaError,
    build_formulation_explanation,
    configured_provider,
    new_formulation_request_id,
)


POPULAR_FORMULATIONS = (
    "Ashwagandha Churna",
    "Brahmi Vati",
    "Haridra Khanda",
    "Kaishora Guggulu",
    "Ashwagandha Arishta",
    "Shatavari Ghrita",
    "Guduchi Satva",
    "Dashamoola Kashaya",
    "Trikatu Churna",
    "Yashtimadhu Swarasa",
)


def _select_formulation(name: str) -> None:
    st.session_state["formulation_name"] = name
    st.session_state["formulation_suggestion_run"] = True
    st.session_state["formulation_answer"] = None
    st.session_state["formulation_error"] = None


def _clear_formulation_answer() -> None:
    st.session_state["formulation_answer"] = None
    st.session_state["formulation_error"] = None


def _model_status(provider: str) -> str:
    if provider != "ollama":
        return "Unavailable · Ollama provider is not configured"
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        response.raise_for_status()
        models = response.json().get("models", [])
        if any(item.get("name") == OLLAMA_MODEL or item.get("model") == OLLAMA_MODEL for item in models):
            return "Available"
        return "Model not listed by Ollama"
    except (httpx.HTTPError, ValueError, AttributeError):
        return "Ollama unavailable"


def render_formulation_explorer() -> None:
    st.markdown(
        "<div class='formulation-page-intro'><div class='formulation-eyebrow'>AYURVEDA KNOWLEDGE WORKSPACE</div>"
        "<h1>Formulation Explorer</h1><p>Explore an Ayurvedic formulation with a direct AyurParam explanation.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown("""
    <style>
    .formulation-page-intro{padding:.2rem 0 1rem;border-bottom:1px solid #E3E9E2;margin-bottom:1rem}
    .formulation-eyebrow{font:700 .68rem 'DM Sans',sans-serif;letter-spacing:.15em;color:#287557;margin-bottom:.35rem}
    .formulation-page-intro h1{margin:0 0 .25rem!important;color:#10372D!important}
    .formulation-page-intro p{margin:0;color:#64736A;font-size:.98rem}
    @media(max-width:640px){.formulation-page-intro{padding-bottom:.75rem}.formulation-page-intro p{font-size:.9rem}}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### Explore Popular Formulations")
    st.caption("Suggestions are starting points for direct model generation; they are not approved database records.")
    for start in range(0, len(POPULAR_FORMULATIONS), 3):
        columns = st.columns(3)
        for column, name in zip(columns, POPULAR_FORMULATIONS[start:start + 3]):
            with column:
                st.button(
                    name,
                    key=f"popular_formulation_{name.casefold().replace(' ', '_')}",
                    use_container_width=True,
                    on_click=_select_formulation,
                    args=(name,),
                )

    provider = configured_provider()
    status = _model_status(provider)
    st.caption(f"Configured AyurParam · {OLLAMA_MODEL} · {status}")
    st.info(FORMULATION_DISCLAIMER)
    if provider == "mock":
        st.warning("Mock mode is configured. No mock answer will be substituted for AyurParam.")
    elif provider != "ollama":
        st.warning(f"Configured provider '{provider}' is not supported for this direct AyurParam workflow.")

    with st.container(border=True):
        st.markdown("### Research a Formulation")
        name = st.text_input(
            "Formulation name",
            key="formulation_name",
            placeholder="Enter a formulation, such as Triphala",
            on_change=_clear_formulation_answer,
        )
        st.caption("This mode sends only the formulation name to the configured AyurParam model. It does not retrieve source passages.")
        generate_clicked = st.button(
            "Generate Explanation",
            type="primary",
            use_container_width=True,
            disabled=not name.strip() or provider != "ollama",
        )

    suggestion_run = st.session_state.pop("formulation_suggestion_run", False)
    if generate_clicked or suggestion_run:
        st.session_state["formulation_answer"] = None
        st.session_state["formulation_error"] = None
        if not name.strip():
            st.session_state["formulation_error"] = "Enter a formulation name or select a popular suggestion."
        elif provider != "ollama":
            st.session_state["formulation_error"] = "AyurParam Ollama is not configured; no answer was generated."
        else:
            request_id = new_formulation_request_id()
            st.session_state["formulation_error_request_id"] = request_id
            try:
                from models.llm import OllamaLLM
                with st.spinner("Generating a direct AyurParam explanation…"):
                    result = build_formulation_explanation(name, OllamaLLM(), request_id=request_id)
                st.session_state["formulation_answer"] = result
            except OllamaError:
                st.session_state["formulation_error"] = "AyurParam is unavailable or the request timed out. No fallback answer was used."
            except FormulationAbstentionError:
                st.session_state["formulation_error"] = FORMULATION_ABSTENTION_MESSAGE
            except FormulationRelevanceError:
                st.session_state["formulation_error"] = FORMULATION_RELEVANCE_ERROR
            except ResponseSchemaError as exc:
                st.session_state["formulation_error"] = f"AyurParam's response could not be safely displayed: {exc}"
            except (RuntimeError, ValueError) as exc:
                st.session_state["formulation_error"] = str(exc)
            except Exception:
                st.session_state["formulation_error"] = "The AyurParam request failed. No fallback answer was used."

    error = st.session_state.get("formulation_error")
    if error:
        st.error(error)
    answer = st.session_state.get("formulation_answer")
    if answer:
        st.markdown("---")
        st.subheader(answer["canonical_name"])
        st.caption(f"{answer.get('model', OLLAMA_MODEL)} · Generated directly by AyurParam")
        status = answer.get("validation_status", "failed")
        st.caption(f"Validation status: {status.title()} · Safety gate: {answer.get('safety_status', 'unknown').title()}")
        relevance = answer.get("relevance", {})
        is_abstention = (
            answer.get("result_category") == "model_abstention"
            or relevance.get("category") == "model_abstention"
        )
        if is_abstention:
            st.info(FORMULATION_ABSTENTION_MESSAGE)
        elif relevance.get("status") == "failed":
            warning = (
                "RELEVANCE WARNING: AyurParam's response did not pass the academic relevance check. "
                "It may describe an unrelated subject and must not be treated as a reliable explanation "
                "of the requested formulation."
            )
            st.warning(warning)
        if answer.get("clinical_efficacy_status") == "failed":
            st.warning("CLINICAL-EFFICACY WARNING: Unverified modern clinical claims were detected. Do not treat these claims as established facts.")
        for warning in answer.get("warnings", []):
            if warning in (FORMULATION_RELEVANCE_ERROR, FORMULATION_ABSTENTION_MESSAGE):
                continue
            if warning.startswith("Unverified modern clinical-efficacy"):
                continue
            if warning == answer.get("citation_warning"):
                continue
            st.warning(warning)
        st.markdown(answer["answer"])
        if answer.get("citation_warning"):
            st.warning(UNVERIFIED_CITATION_WARNING)
        if relevance.get("status") == "failed" or answer.get("clinical_efficacy_status") == "failed":
            with st.expander("Validation diagnostics"):
                st.caption(f"Request ID: {answer.get('request_id', 'unavailable')}")
                if relevance.get("status") == "failed":
                    st.write(f"Relevance: {relevance.get('category') or 'failed'} · {relevance.get('reason') or 'No relevance rule matched.'}")
                if answer.get("clinical_efficacy_sentences"):
                    st.write("Clinical-efficacy validation: unverified claims detected.")
                if answer.get("unqualified_efficacy_sentences"):
                    st.write("Efficacy validation: unqualified claims detected.")
    elif not error:
        st.info("Enter a formulation name or choose a suggestion to begin.")


__all__ = ["POPULAR_FORMULATIONS", "render_formulation_explorer"]
