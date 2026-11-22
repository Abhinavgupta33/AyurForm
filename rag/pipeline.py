"""End-to-end retrieval and grounded educational response generation."""

from __future__ import annotations

import re
import logging
import time
from collections.abc import Callable

from config import LLM_MODE, LLM_PROVIDER, MAX_COSINE_DISTANCE, TOP_K
from models.llm import AyurParamLLM, OllamaLLM, ResponseSchemaError, build_prompt_with_passages, validate_generation
from rag.retriever import get_retriever
from utils.citations import format_reference
from utils.safety import disclaimer, urgent_care_warning
from utils.diagnostics import LOGGER, correlation_id


SYMPTOM_TERMS = (
    "pain", "burning", "nausea", "vomiting", "vomit", "diarrhea", "loose stools", "constipation",
    "bloating", "belching", "burping", "sour burps", "fever", "cough", "headache", "dizziness",
    "fatigue", "itching", "rash", "swelling", "shortness of breath", "breathlessness", "loss of appetite",
)


def extract_symptoms(query: str) -> list[str]:
    lowered = query.lower()
    found = [term for term in SYMPTOM_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered)]
    return found


def _get_ayurvedic_response(
    user_query: str,
    retriever=None,
    llm=None,
    llm_mode: str | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
    _trace_id: str | None = None,
) -> dict:
    """Return validated source passages and a tentative explanation, never a diagnosis."""
    trace_id = _trace_id or correlation_id()
    LOGGER.info("pipeline stage=start correlation=%s", trace_id)
    query = user_query.strip()
    if not query:
        raise ValueError("Please enter a symptom description.")

    def report(stage: str, state: str) -> None:
        if progress_callback is not None:
            progress_callback(stage, state)

    report("understand", "running")
    LOGGER.info("pipeline stage=understand correlation=%s", trace_id)
    extracted_symptoms = extract_symptoms(query)
    report("understand", "complete")
    report("search", "running")
    report("retrieve", "running")
    retriever = retriever or get_retriever()
    hits = retriever.retrieve(query, top_k=TOP_K)
    roles = [str((hit.get("metadata") or {}).get("provenance_role", "unknown")) for hit in hits]
    counts = {role: roles.count(role) for role in sorted(set(roles))}
    LOGGER.info("pipeline stage=retrieve correlation=%s passage_count=%d provenance_counts=%s", trace_id, len(hits), counts)
    report("search", "complete")
    hits = [hit for hit in hits if hit.get("distance", 0.0) <= MAX_COSINE_DISTANCE]
    report("retrieve", "complete")
    result = {
        "user_query": query,
        "extracted_symptoms": extracted_symptoms,
        "possible_concepts": [],
        "evidence_summary": "",
        "limitations": "",
        "passages": [],
        "evidence_sufficient": bool(hits),
        "mode": "not_run",
        "urgent_care": urgent_care_warning(query),
        "disclaimer": disclaimer(),
    }
    for hit in hits:
        metadata = hit.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        result["passages"].append(
            {**hit, "metadata": metadata, "reference": format_reference(metadata)}
        )
    if not hits:
        report("generate", "skipped")
        report("validate", "skipped")
        result["evidence_summary"] = "Sufficient classical evidence was not found in the indexed source. No concept association is provided."
        result["limitations"] = "This is an educational retrieval tool, not a diagnosis."
        return result

    mode = (llm_mode or LLM_MODE or LLM_PROVIDER or "mock").lower()
    if mode == "mock":
        report("generate", "skipped")
        report("validate", "skipped")
        result["mode"] = "mock"
        result["evidence_summary"] = "Mock mode is active: passages were retrieved, but no model-generated concept or explanation is being shown."
        result["limitations"] = "Set AYURSUTRA_LLM_MODE=ayurparam on hardware with adequate memory to run the official AyurParam model."
        return result
    if mode not in {"ayurparam", "ollama"}:
        raise ValueError("LLM provider must be 'mock', 'ollama', or 'ayurparam'.")

    report("generate", "running")
    llm = llm or (OllamaLLM() if mode == "ollama" else AyurParamLLM())
    prompt, prompt_hits = build_prompt_with_passages(query, hits)
    started = time.monotonic()
    try:
        raw = llm.generate(prompt)
    except Exception as exc:
        LOGGER.exception("pipeline stage=generation correlation=%s exception=%s elapsed_ms=%d", trace_id, type(exc).__name__, int((time.monotonic()-started)*1000))
        raise
    report("generate", "complete")
    report("validate", "running")
    try:
        generated = validate_generation(raw, prompt_hits, correlation=trace_id)
    except (ValueError, TypeError, KeyError) as exc:
        # Some local models intermittently ignore JSON mode. Retry once with a
        # stricter instruction; the response still must pass the same validator.
        if mode != "ollama":
            raise
        LOGGER.warning("pipeline stage=validation correlation=%s retry=true exception=%s", trace_id, type(exc).__name__)
        raw = llm.generate(prompt + "\nReturn only the required JSON object. Do not include prose, markdown, or advice.")
        try:
            generated = validate_generation(raw, prompt_hits, correlation=trace_id)
        except (ValueError, TypeError, KeyError) as retry_exc:
            LOGGER.error("pipeline stage=validation correlation=%s retry_failed=true exception=%s", trace_id, type(retry_exc).__name__)
            result["mode"] = mode
            result["validation_failed"] = True
            result["evidence_sufficient"] = False
            result["evidence_summary"] = "The model response could not be validated against the required structured-answer schema."
            result["limitations"] = "No generated explanation or concept association is shown because response validation failed."
            report("validate", "failed")
            return result
    report("validate", "complete")
    result.update(generated)
    result["mode"] = mode
    has_translated_source = any((p.get("metadata") or {}).get("provenance_role") == "translated_source" for p in hits)
    citation_valid = all(all(pid in {f"P{i}" for i in range(1, len(hits)+1)} for pid in c.get("supporting_passage_ids", [])) for c in generated.get("possible_concepts", []))
    provenance_valid = has_translated_source
    safety_valid = not (generated.get("limitations", "").startswith("No recommendation is provided"))
    LOGGER.info("pipeline stage=validation correlation=%s schema=passed citations=%s provenance=%s safety=%s", trace_id, citation_valid, provenance_valid, safety_valid)
    result["evidence_sufficient"] = bool(has_translated_source and (generated["possible_concepts"] or generated["evidence_summary"]))
    if not has_translated_source:
        result["limitations"] = "Retrieved passages did not include verified translated-source evidence; editorial or unknown material is not sufficient for a classical-text claim."
    if not generated["possible_concepts"] and not generated["evidence_summary"]:
        result["evidence_summary"] = "Retrieved text did not support a reliable conceptual association."
        result["evidence_sufficient"] = False
    return result


def get_ayurvedic_response(*args, **kwargs) -> dict:
    """Run one analysis and always emit a terminal lifecycle event."""
    trace_id = correlation_id()
    try:
        trace_id = correlation_id()
        kwargs["_trace_id"] = trace_id
        result = _get_ayurvedic_response(*args, **kwargs)
        outcome = "grounded_answer" if result.get("evidence_sufficient") else "abstention"
        LOGGER.info("pipeline stage=final correlation=%s outcome=%s mode=%s", trace_id, outcome, result.get("mode"))
        return result
    except Exception as exc:
        LOGGER.exception("pipeline stage=final correlation=%s outcome=technical_failure exception=%s", trace_id, type(exc).__name__)
        raise
