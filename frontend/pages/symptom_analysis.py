"""Educational symptom analysis UI backed by the existing RAG pipeline."""
from __future__ import annotations

from html import escape

import streamlit as st

from config import LLM_MODE, LLM_PROVIDER
from frontend.symptom_components import (
    STAGES,
    analysis_plain_text,
    build_analysis_pdf,
    render_copy_button,
    render_loading_steps,
)
from rag.pipeline import get_ayurvedic_response

EXAMPLES = [
    "Burning sensation and sour belching",
    "Frequent headaches",
    "Joint pain and stiffness",
    "Difficulty sleeping",
    "Abdominal discomfort",
    "Irregular menstrual patterns",
]
MAX_CHARS = 1200


def _set_example(value: str) -> None:
    st.session_state["symptom_description"] = value
    _clear_previous_result()


def _clear_input() -> None:
    st.session_state["symptom_description"] = ""
    _clear_previous_result()


def _clear_previous_result() -> None:
    st.session_state.pop("symptom_analysis_result", None)
    st.session_state.pop("symptom_analysis_error", None)
    st.session_state.pop("symptom_analysis_saved", None)
    st.session_state.pop("symptom_analysis_pdf", None)
    st.session_state["show_analysis_sources"] = False


def _start_new_analysis() -> None:
    st.session_state["symptom_description"] = ""
    st.session_state["analysis_duration"] = ""
    st.session_state["analysis_severity"] = "Not provided"
    st.session_state["analysis_frequency"] = "Not provided"
    st.session_state["analysis_age_range"] = "Prefer not to say"
    st.session_state.pop("symptom_analysis_result", None)
    st.session_state.pop("symptom_analysis_error", None)
    st.session_state.pop("symptom_analysis_saved", None)
    st.session_state.pop("symptom_analysis_pdf", None)
    st.session_state["show_analysis_sources"] = False


def _optional_details() -> dict:
    values = {
        "duration": st.session_state.get("analysis_duration", "").strip(),
        "severity": st.session_state.get("analysis_severity", "Not provided"),
        "frequency": st.session_state.get("analysis_frequency", "Not provided"),
        "age_range": st.session_state.get("analysis_age_range", "Prefer not to say"),
    }
    return {key: value for key, value in values.items() if value and value not in {"Not provided", "Prefer not to say"}}


def _render_page_style() -> None:
    st.html(
        """<style>
        .symptom-intro{margin:0 0 1.15rem}.symptom-intro h1{margin:.1rem 0 .4rem!important}
        .symptom-intro p{max-width:920px;color:#64736A!important;margin:0!important;font-size:1rem}
        .symptom-mode-note{display:inline-flex;align-items:center;gap:7px;padding:6px 10px;margin-top:12px;border:1px solid #E3E9E2;border-radius:999px;background:#fff;color:#64736A;font-size:.78rem}
        .st-key-symptom_input_card,.st-key-symptom_examples_card{border:1px solid #E3E9E2!important;border-radius:17px!important;background:#fff!important;box-shadow:0 6px 20px rgba(16,55,45,.04)!important;padding:clamp(1rem,2.2vw,1.6rem)!important}
        .st-key-symptom_input_card h2{font:600 clamp(1.35rem,2.2vw,1.7rem) 'Playfair Display',serif!important;color:#10372D!important;margin:.1rem 0 .25rem!important}
        .symptom-help{color:#64736A;font-size:.91rem;margin-bottom:.85rem}
        .st-key-symptom_input_card textarea{min-height:180px!important;border:1px solid #DCE5DC!important;border-radius:12px!important;background:#fff!important;color:#1D2E26!important;font-size:1rem!important;line-height:1.6!important;padding:14px!important}
        .st-key-symptom_input_card textarea:focus{border-color:#287557!important;box-shadow:0 0 0 3px rgba(40,117,87,.12)!important}
        .symptom-counter{display:flex;justify-content:space-between;color:#78877D;font-size:.76rem;margin-top:-.5rem;margin-bottom:.5rem}
        .st-key-symptom_input_card [data-testid=stExpander]{border:1px solid #E3E9E2;border-radius:12px;background:#FCFDFB}
        .st-key-symptom_examples_card{padding:1rem 1.2rem!important;margin-top:1rem}
        .example-title{color:#153D30;font-size:.92rem;font-weight:700;margin-bottom:.15rem}.example-copy{color:#64736A;font-size:.82rem;margin-bottom:.7rem}
        .st-key-symptom_examples_card .stButton>button{min-height:40px!important;padding:.35rem .65rem!important;font-size:.82rem!important;font-weight:500!important;background:#F8FAF7!important;border-color:#E3E9E2!important;color:#29483A!important;text-align:left!important;white-space:normal!important}
        .st-key-symptom_examples_card .stButton>button:hover{border-color:#A9BFA9!important;background:#EDF3EC!important}
        .symptom-actions [data-testid=stHorizontalBlock]{align-items:center;gap:12px!important}
        .analysis-result{border:1px solid #E3E9E2;border-radius:16px;background:#fff;padding:1.2rem 1.35rem;margin:.65rem 0;box-shadow:0 4px 14px rgba(16,55,45,.035)}
        .analysis-result h3{font:600 1.15rem 'Playfair Display',serif!important;color:#10372D!important;margin:.1rem 0 .5rem}
        .analysis-result p,.analysis-result li{color:#1D2E26!important}.analysis-pill{display:inline-block;background:#EDF3EC;color:#174C3C;border-radius:999px;padding:4px 9px;font-size:.72rem;font-weight:700;letter-spacing:.03em}
        .analysis-reference-meta{font-size:.8rem;color:#64736A;margin:.15rem 0 .65rem}.analysis-concept{border-left:3px solid #A9BFA9;background:#F8FAF7;padding:.85rem 1rem;border-radius:0 11px 11px 0;margin:.55rem 0 0}
        .analysis-safety{border:1px solid #E5EBDD;border-radius:13px;background:#F7F9F4;padding:1rem 1.1rem;color:#42594B;font-size:.86rem;line-height:1.55;margin-top:1rem}
        .analysis-source-note{color:#64736A;font-size:.84rem;margin:.25rem 0 .7rem}
        [data-testid=stSidebar] .stButton>button[kind=primary][data-testid="stBaseButton-primary"]{background:#EDF3EC!important;border-color:#DCE8DC!important;color:#10372D!important;box-shadow:inset 3px 0 #287557!important}
        [data-testid=stSidebar] .stButton>button[kind=primary][data-testid="stBaseButton-primary"] p,[data-testid=stSidebar] .stButton>button[kind=primary][data-testid="stBaseButton-primary"] [data-testid=stIconMaterial]{color:#10372D!important}
        @media screen and (max-height: 800px){.symptom-intro{margin-bottom:.7rem!important}.st-key-symptom_input_card{padding:1rem!important}.st-key-symptom_input_card textarea{height:145px!important;min-height:145px!important}.symptom-mode-note{margin-top:8px!important}}
        @media(max-width:640px){.st-key-symptom_input_card,.st-key-symptom_examples_card{padding:1rem!important}.st-key-symptom_input_card textarea{min-height:160px!important}.symptom-actions [data-testid=stHorizontalBlock]{display:grid!important;grid-template-columns:minmax(0,1fr)!important}.symptom-actions [data-testid=stColumn]{width:auto!important;min-width:0!important}.analysis-result{padding:1rem}}
        </style>""",
    )


def _validate_description(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return "Describe the symptoms you are experiencing before starting an analysis."
    if len(cleaned) < 5:
        return "Please add a little more detail so the system can search the classical sources meaningfully."
    if len(cleaned) > MAX_CHARS:
        return f"Keep the description to {MAX_CHARS:,} characters or fewer."
    return None


def _run_analysis(description: str, details: dict) -> None:
    states = {key: "pending" for key, _ in STAGES}
    st.session_state.pop("symptom_analysis_error", None)
    st.session_state.pop("symptom_analysis_result", None)
    st.session_state.pop("symptom_analysis_pdf", None)
    status = st.status("Analyzing symptom description", expanded=True)
    progress = st.empty()
    render_loading_steps(progress, states)

    def update_stage(stage: str, state: str) -> None:
        states[stage] = state
        render_loading_steps(progress, states)

    try:
        result = get_ayurvedic_response(description, progress_callback=update_stage)
        result["original_description"] = description.strip()
        result["optional_details"] = details
        st.session_state["symptom_analysis_result"] = result
        st.session_state["symptom_analysis_saved"] = False
        st.session_state["show_analysis_sources"] = False
        status.update(label="Analysis workflow complete", state="complete", expanded=False)
    except Exception as exc:
        running = [key for key, state in states.items() if state == "running"]
        for key in running:
            states[key] = "failed"
        for key, state in states.items():
            if state == "pending":
                states[key] = "skipped"
        render_loading_steps(progress, states)
        status.update(label="Analysis could not be completed", state="error", expanded=True)
        st.session_state["symptom_analysis_error"] = str(exc)[:240]


def _render_result(result: dict) -> None:
    details = result.get("optional_details", {})
    mode = result.get("mode")
    passages = result.get("passages") or []
    concepts = result.get("possible_concepts") or []
    extracted = result.get("extracted_symptoms") or []

    st.markdown('<div class="shell-header"><div class="shell-crumb">Analysis result</div><h2>Symptom analysis</h2><p class="shell-desc">A source-grounded educational summary of the description you shared.</p></div>', unsafe_allow_html=True)
    if mode == "mock" or (mode == "not_run" and LLM_MODE == "mock"):
        st.info("DEMONSTRATION · MOCK MODE — AyurParam did not generate an explanation. Retrieved passages, if any, are shown separately.")
    elif mode == "ayurparam":
        if result.get("validation_failed"):
            st.error("AyurParam response validation failed. No unvalidated model explanation is displayed; retrieved evidence remains available below.")
        else:
            st.success("AyurParam explanation generated. Concept associations are limited to concepts linked to retrieved passage IDs.")
    elif not passages:
        st.warning("No relevant passages were found in the indexed collection. No concept association or model explanation is provided.")

    if result.get("urgent_care"):
        st.warning("Your description includes a symptom that may need urgent assessment. Please seek prompt medical care or contact local emergency services. This educational tool cannot assess emergencies.")

    st.markdown('<div class="analysis-result"><h3>Section A · Symptom summary</h3></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="analysis-result"><span class="analysis-pill">ORIGINAL DESCRIPTION</span><p>{escape(result.get("original_description", result.get("user_query", "")))}</p></div>', unsafe_allow_html=True)
    cols = st.columns(2)
    with cols[0]:
        st.markdown('<div class="analysis-result"><b>Extracted symptom terms</b>', unsafe_allow_html=True)
        if extracted:
            st.write(", ".join(extracted))
        else:
            st.write("No predefined symptom terms were identified by the current extractor.")
        st.markdown("</div>", unsafe_allow_html=True)
    with cols[1]:
        summary = [f"**{label}:** {details[key]}" for label, key in (("Duration", "duration"), ("Severity", "severity"), ("Frequency", "frequency"), ("Age range", "age_range")) if details.get(key)]
        st.markdown('<div class="analysis-result"><b>Optional details</b>', unsafe_allow_html=True)
        if summary:
            st.markdown("  \n".join(summary))
        else:
            st.write("No optional details provided.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="analysis-result"><h3>Section B · Possible Ayurvedic concepts</h3><p>These are tentative textual associations only. They are not diagnoses or statements of modern clinical evidence.</p></div>', unsafe_allow_html=True)
    if concepts:
        passage_map = {f"P{i}": p for i, p in enumerate(passages, 1)}
        for concept in concepts:
            name = escape(str(concept.get("name", "Concept")))
            reason = escape(str(concept.get("reason", "No explanation was provided.")))
            refs = [pid for pid in concept.get("supporting_passage_ids", []) if pid in passage_map]
            ref_html = ", ".join(escape(pid) for pid in refs) if refs else "No validated passage identifier was returned."
            st.markdown(f'<div class="analysis-concept"><b>{name}</b><p>{reason}</p><small>Validated supporting passage IDs: {ref_html}</small></div>', unsafe_allow_html=True)
    else:
        st.info("No possible concept association is presented. The current model mode does not generate concepts, or the retrieved evidence did not support one.")

    st.markdown('<div class="analysis-result"><h3>Section C · Retrieved classical references</h3></div>', unsafe_allow_html=True)
    if passages:
        st.markdown(f'<p class="analysis-source-note">{len(passages)} passage(s) passed the configured relevance threshold. Source details below come from indexed metadata; missing fields are omitted.</p>', unsafe_allow_html=True)
        for i, passage in enumerate(passages, 1):
            meta = passage.get("metadata", {}) or {}
            reference = passage.get("reference", "Source metadata unavailable")
            with st.expander(f"P{i} · {reference}", expanded=i == 1):
                labels = []
                for label, key in (("Source", "source_title"), ("Sthana", "sthana"), ("Chapter", "chapter_number"), ("Chapter title", "chapter_title"), ("Verse", "verse_number"), ("Page", "page_number"), ("Provenance", "provenance_role")):
                    if meta.get(key):
                        labels.append(f"**{label}:** {meta[key]}")
                if passage.get("distance") is not None:
                    labels.append(f"**Distance:** {passage['distance']:.4f}")
                if labels:
                    st.markdown(" · ".join(labels))
                st.markdown("**Retrieved excerpt**")
                st.write(passage.get("text", ""))
                st.caption("Retrieved by semantic similarity from the indexed collection. This is not a measure of medical confidence.")
    else:
        st.warning("No classical passages are currently indexed or no passage met the retrieval threshold. Evidence is insufficient for a textual association.")

    st.markdown('<div class="analysis-result"><h3>Section D · AyurParam explanation</h3></div>', unsafe_allow_html=True)
    if mode == "ayurparam" and result.get("evidence_summary"):
        st.markdown(f'<div class="analysis-result">{escape(result["evidence_summary"]).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
    elif result.get("validation_failed"):
        st.warning("No explanation is displayed because the model response failed structured validation. Retrieved passages above are evidence only.")
    elif mode == "mock":
        st.info("No AyurParam explanation is shown because the application is running in mock mode.")
    else:
        st.info("No explanation was generated because sufficient retrieved passages were not available.")

    st.markdown('<div class="analysis-result"><h3>Section E · Evidence limitations</h3></div>', unsafe_allow_html=True)
    if result.get("evidence_sufficient"):
        st.write(f"{len(passages)} retrieved passage(s) met the configured relevance threshold. Concepts shown above include only references validated against those passages.")
    else:
        st.write("The indexed evidence is insufficient to support a conceptual association. No confidence score is inferred.")
    if result.get("limitations"):
        st.info(result["limitations"])
    st.write("The indexed collection may be incomplete, and other textual concepts may be relevant. Consult the source excerpts and a qualified healthcare professional for personal health concerns.")

    result_text = analysis_plain_text(result, details)
    st.markdown("#### Result actions")
    action_cols = st.columns([1, 1, 1])
    with action_cols[0]:
        render_copy_button(result_text, key="copy-analysis-answer")
    with action_cols[1]:
        st.button("Save analysis", key="analysis_save", icon=":material/bookmark_add:", disabled=True, use_container_width=True)
        st.caption("Saving returns after account-owned records are enabled.")
    with action_cols[2]:
        if "symptom_analysis_pdf" not in st.session_state:
            st.session_state["symptom_analysis_pdf"] = build_analysis_pdf(result, details)
        st.download_button("Download PDF", data=st.session_state["symptom_analysis_pdf"], file_name="ayurform-research-review.pdf", mime="application/pdf", key="analysis_pdf", icon=":material/download:", use_container_width=True)
    control_cols = st.columns(2)
    with control_cols[0]:
        st.button("Start new analysis", key="analysis_new", icon=":material/add:", on_click=_start_new_analysis, use_container_width=True)
    with control_cols[1]:
        st.caption("Analysis history is restricted until records can be assigned to your account.")

    st.markdown(f'<div class="analysis-safety">{escape(result.get("disclaimer", "For education only. This is not a diagnosis or substitute for professional care."))}</div>', unsafe_allow_html=True)


def render_symptom_analysis() -> None:
    _render_page_style()
    st.markdown(
        '<div class="symptom-intro"><h1>Symptom Analysis</h1><p>Describe your symptoms in your own words and explore potentially relevant Ayurvedic concepts supported by classical knowledge.</p></div>',
        unsafe_allow_html=True,
    )
    provider = LLM_MODE or LLM_PROVIDER or "mock"
    mode_text = "Development mode · mock" if provider == "mock" else f"{provider.title()} configured"
    st.markdown(f'<div class="symptom-mode-note"><span aria-hidden="true">●</span>{escape(mode_text)} · Educational use only</div>', unsafe_allow_html=True)

    with st.container(border=True, key="symptom_input_card"):
        st.markdown("<h2>What are you experiencing?</h2><div class='symptom-help'>You don't need to know Ayurvedic terminology. Simply describe what you feel in everyday language.</div>", unsafe_allow_html=True)
        description = st.text_area(
            "Symptom description",
            key="symptom_description",
            height=180,
            max_chars=MAX_CHARS,
            label_visibility="collapsed",
            on_change=_clear_previous_result,
            placeholder="Example: I experience a burning sensation in my stomach, sour belching and occasional nausea, especially after meals...",
        )
        st.markdown(f'<div class="symptom-counter"><span>Do not include your name or other identifying details.</span><span>{len(description)}/{MAX_CHARS:,} characters</span></div>', unsafe_allow_html=True)
        with st.expander("Additional Details · optional", expanded=False):
            detail_cols = st.columns(2)
            with detail_cols[0]:
                st.text_input("Duration of symptoms", key="analysis_duration", placeholder="For example, a few days")
                st.selectbox("Severity", ["Not provided", "Mild", "Moderate", "Severe"], key="analysis_severity")
            with detail_cols[1]:
                st.selectbox("Frequency", ["Not provided", "Occasional", "Frequent", "Daily"], key="analysis_frequency")
                st.selectbox("Age range · optional", ["Prefer not to say", "Under 18", "18–29", "30–44", "45–59", "60+"], key="analysis_age_range")
        st.markdown('<div class="symptom-actions">', unsafe_allow_html=True)
        action_cols = st.columns([1, .42])
        with action_cols[0]:
            analyze = st.button("Analyze Symptoms", type="primary", icon=":material/psychology:", key="symptom_analyze", use_container_width=True)
        with action_cols[1]:
            st.button("Clear input", key="symptom_clear", icon=":material/backspace:", on_click=_clear_input, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        if analyze:
            issue = _validate_description(description)
            if issue:
                st.error(issue)
            else:
                _run_analysis(description, _optional_details())
        if st.session_state.get("symptom_analysis_error"):
            st.error("Analysis could not be completed. The local retrieval store or configured language model may be unavailable. Please check the setup and try again.")

    with st.container(border=True, key="symptom_examples_card"):
        st.markdown('<div class="example-title">Need a starting point?</div><div class="example-copy">Choose an example to place it in the description box. You can edit it before analyzing.</div>', unsafe_allow_html=True)
        cols = st.columns(3)
        for i, value in enumerate(EXAMPLES):
            with cols[i % len(cols)]:
                st.button(value, key=f"symptom_example_{i}", on_click=_set_example, args=(value,), use_container_width=True)

    result = st.session_state.get("symptom_analysis_result")
    if result:
        _render_result(result)
