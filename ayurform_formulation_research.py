"""Direct, non-RAG AyurParam explanations for formulation names."""
from __future__ import annotations

import re
import os
import uuid

from utils.diagnostics import LOGGER

from config import LLM_MODE, LLM_PROVIDER, OLLAMA_MODEL
from models.llm import OllamaError, ResponseSchemaError


FORMULATION_DISCLAIMER = (
    "Generated directly by AyurParam. Not verified against retrieved classical sources."
)
UNVERIFIED_CITATION_WARNING = (
    "AyurParam-generated citation — not independently verified against the original classical source."
)
FORMULATION_RELEVANCE_ERROR = (
    "AyurParam generated content that does not appear relevant to the requested Ayurvedic formulation. Please try again."
)
FORMULATION_ABSTENTION_MESSAGE = (
    "AyurParam could not identify this formulation."
)


class FormulationRelevanceError(ResponseSchemaError):
    """Generated text does not establish that it answers the requested formulation."""

    def __init__(self, category: str | None = None, reason: str | None = None) -> None:
        self.category = category
        self.reason = reason
        super().__init__(FORMULATION_RELEVANCE_ERROR)


class FormulationAbstentionError(FormulationRelevanceError):
    """Model explicitly abstained because it could not identify the formulation."""

    def __init__(self) -> None:
        super().__init__()
        self.args = (FORMULATION_ABSTENTION_MESSAGE,)

_CITATION_PATTERNS = {
    "passage ID": re.compile(r"\bP\d+\b", re.I),
    # Handles both Su1#41 and Ci1.4#3-6-style markers.
    "classical reference number": re.compile(
        r"\b(?:Su|Vi|Ci|Si|U|Ni|Ka)\s*\d+(?:\.\d+)?\s*#\s*\d+(?:\s*[-–]\s*\d+)?\b",
        re.I,
    ),
    "named classical source": re.compile(
        r"\b(?:Charaka|Caraka|Sushruta|Suśruta)(?:\s+(?:Samhita|Saṃhitā))?\b|"
        r"\b(?:Ashtanga|Aṣṭāṅga)\s+(?:Hridaya|Hṛdaya|Sangraha|Saṅgraha)\b|"
        r"\bBhavaprakasha\b|\bBhela(?:\s+Samhita)?\b|\bKashyapa(?:\s+Samhita)?\b",
        re.I,
    ),
    "unverified source attribution": re.compile(
        r"\b(?:according to|as stated in|as described in|as quoted in|the text says|the text states|"
        r"classical texts? (?:say|state|describe)|ancient texts? (?:say|state|describe)|"
        r"Ayurvedic texts? (?:say|state|describe)|scriptures? (?:say|state|describe)|"
        r"(?:classical|ancient|Ayurvedic) source (?:says|states|describes|records))\b",
        re.I,
    ),
}
_UNSAFE_INSTRUCTIONS = re.compile(
    r"\b(?:dosage|dose|prescribe|prescription|self[- ]medicat(?:e|ion|ing)?|diagnos(?:e|is|tic)|take\s+\d|"
    r"consume\s+\d|administer\s+\d|"
    r"patient[- ]specific treatment|prepare(?:d)?\s+(?:it|the formulation|this formulation)|"
    r"heat\s+(?:it|the mixture)|purif(?:y|ication)|incinerat(?:e|ion)|shodhana|marana)\b",
    re.I,
)
_UNSAFE_CATEGORIES = {
    "dosage or administration instruction": re.compile(
        r"\b(?:dosage|dose|take\s+\d|consume\s+\d|administer\s+\d)\b", re.I
    ),
    "self-medication or prescribing instruction": re.compile(
        r"\b(?:prescribe|prescription|self[- ]medicat(?:e|ion|ing)?)\b", re.I
    ),
    "diagnostic instruction": re.compile(r"\bdiagnos(?:e|is|tic)\b", re.I),
    "patient-specific treatment instruction": re.compile(r"\bpatient[- ]specific treatment\b", re.I),
    "preparation or hazardous-processing instruction": re.compile(
        r"\b(?:prepare(?:d)?\s+(?:it|the formulation|this formulation)|heat\s+(?:it|the mixture)|"
        r"purif(?:y|ication)|incinerat(?:e|ion)|shodhana|marana)\b", re.I
    ),
}
_CLINICAL_EFFICACY = re.compile(
    r"\b(?:clinically proven|proven (?:to|effective)|clinical (?:trials?|studies|study|evidence)\s+"
    r"(?:show|shows|demonstrate|demonstrates|prove|proves)|clinical efficacy|"
    r"modern (?:research|studies|science)\s+(?:show|shows|prove|proves|demonstrate|demonstrates)|"
    r"scientifically proven|evidence[- ]based treatment|anti[- ]inflammatory|antioxidant|"
    r"lipid[- ]lowering|clinically effective)\b",
    re.I,
)
_UNQUALIFIED_EFFICACY = re.compile(
    r"\b(?:treat(?:s|ed|ment)?|cure(?:s|d)?|prevent(?:s|ed|ion)?|"
    r"support(?:s|ed)?\s+(?:overall health|digestion|joint health|circulation)|"
    r"promote(?:s)?\s+(?:overall )?health|reduce(?:s)?\s+inflammation|"
    r"balance(?:s)?\s+(?:all three )?doshas?|detoxif(?:y|ies|ied|ication)|"
    r"boost(?:s|ed)?\s+immunity|improv(?:e|es|ed)\s+(?:digestion|health)|"
    r"enhanc(?:e|es|ed)\s+(?:digestion|health)|healing processes|therapeutic potential)\b",
    re.I,
)
_TRADITIONAL_FRAMING = re.compile(
    r"\b(?:traditionally|traditional (?:Ayurvedic )?(?:use|description|account|context|formulation|significance)|"
    r"in Ayurvedic tradition|used in Ayurveda|described in Ayurveda|Ayurveda traditionally|"
    r"historically,?(?:\s+\w+){0,5}\s+(?:used|described|regarded|documented)"
    r"(?:\s+in\s+traditional\s+practice)?)\b",
    re.I,
)
_FORMULA_PROPORTION = re.compile(
    r"\b(?:equal parts?|\d+\s*:\s*\d+(?:\s*:\s*\d+)?|\d+\s*(?:percent|%)|"
    r"(?:in|at) a ratio of\s+\d+|\d+\s+parts? (?:of|each))\b",
    re.I,
)
_METADATA_FIELDS = re.compile(
    r"\b(?:source_id|source_file|source_identifier|chapter_reference|edition_details|"
    r"provenance_role|pdf_page|page_number)\s*:",
    re.I,
)
_QUOTED_TEXT = re.compile(r'(?:“[^”\r\n]{8,}”|"[^"\r\n]{8,}")')
_EMAIL_OR_PHONE = re.compile(
    r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b|(?<!\w)(?:\+?\d[\d(). -]{7,}\d)(?!\w)"
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(?:email|phone|address|date of birth|dob|patient|name)\s*[:=]\s*[^,;.]{1,100}"
)
_FOOD_RECIPE_METHOD = re.compile(
    r"\b(?:recipe|serves\s+\d+|cooking time|prep(?:aration)? time|directions|method)\b|"
    r"\b(?:fry|sauté|saute|stir[- ]fry|cook|simmer|serve hot|season to taste)\b",
    re.I,
)
_ORDINARY_RECIPE_FOODS = re.compile(
    r"\b(?:lentils?|dal|rice|onions?|garlic|tomatoes?|potatoes?|flour|noodles?|pasta|"
    r"vegetables?|oil)\b",
    re.I,
)
_FORMULATION_CONTEXT = re.compile(
    r"\b(?:formulation|churna|powder|ingredients?|herbal|Ayurvedic|traditional|dravya|"
    r"rasa|guna|virya|vipaka|karma|ferment(?:ed|ation)?|anupana|preparation)\b",
    re.I,
)
_ORDINARY_DISH_IDENTITY = re.compile(
    r"\b(?:dish|recipe|regional cuisine|cuisine|meal|khichdi|khichri|khichuri)\b",
    re.I,
)
_DISH_IDENTITY_ASSERTION = re.compile(
    r"\b(?:is|was|refers to|known as|described as|popular as|considered)\b.{0,100}"
    r"\b(?:dish|recipe|regional cuisine|cuisine|meal|khichdi|khichri|khichuri)\b|"
    r"\b(?:dish|recipe|regional cuisine|cuisine|meal|khichdi|khichri|khichuri)\b.{0,100}"
    r"\b(?:is|was|refers to|known as|described as|popular as|considered)\b",
    re.I,
)
_REGIONAL_DISH_CUES = re.compile(
    r"\b(?:Gujarati|Rajasthani|Bengali|Punjabi|Maharashtrian|South Indian|regional)\b",
    re.I,
)
_MODEL_ABSTENTION = re.compile(
    r"\b(?:cannot|can't|unable to|not able to)\s+(?:reliably\s+)?(?:identify|provide|give|explain)\b|"
    r"\b(?:cannot|can't|unable to) confidently identify\b|"
    r"\bnot enough information to (?:identify|explain)\b",
    re.I,
)


def _safe_diagnostic_sentence(sentence: str) -> str:
    normalized = " ".join(sentence.split())
    normalized = _EMAIL_OR_PHONE.sub("[REDACTED]", normalized)
    normalized = _SENSITIVE_VALUE.sub("[REDACTED]", normalized)
    return normalized[:500]


def configured_provider() -> str:
    """Use explicit provider configuration; never substitute a mock provider."""
    return LLM_MODE or LLM_PROVIDER or "mock"


def new_formulation_request_id() -> str:
    return uuid.uuid4().hex[:16]


def validate_formulation_answer(
    raw: str, *, request_id: str | None = None, requested_formulation: str | None = None
) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ResponseSchemaError("AyurParam returned an empty formulation explanation")
    answer = raw.strip()
    if answer.startswith(("{", "[", "```")):
        raise ResponseSchemaError("AyurParam returned structured or malformed output")
    if _QUOTED_TEXT.search(answer):
        raise ResponseSchemaError("Direct formulation mode cannot verify quoted source text")
    if _METADATA_FIELDS.search(answer):
        raise ResponseSchemaError("AyurParam returned source metadata in direct mode")
    if _UNSAFE_INSTRUCTIONS.search(answer):
        categories = [name for name, pattern in _UNSAFE_CATEGORIES.items() if pattern.search(answer)]
        detail = ", ".join(categories) if categories else "prohibited instructions"
        raise ResponseSchemaError("AyurParam response contained prohibited instructions (" + detail + ")")
    for sentence in re.split(r"(?<=[.!?])\s+", answer):
        clinical_match = _CLINICAL_EFFICACY.search(sentence)
        if clinical_match:
            if os.getenv("AYURSUTRA_ENV", "").casefold() == "development":
                LOGGER.warning(
                    "formulation_validation request_id=%s formulation=%r category=modern_clinical_efficacy matched_pattern=%r sentence=%r "
                    "traditional_framing_detected=%s modern_clinical_efficacy_detected=true",
                    request_id or "-",
                    _safe_diagnostic_sentence(requested_formulation or "")[:120],
                    clinical_match.group(0),
                    _safe_diagnostic_sentence(sentence),
                    bool(_TRADITIONAL_FRAMING.search(sentence)),
                )
            nearby_negation = re.search(
                r"\b(?:not|no|cannot|does not|isn't|is not)\b.{0,45}\b(?:proven|evidence|efficacy|effective|clinical)\b",
                sentence,
                re.I,
            )
            if not nearby_negation:
                raise ResponseSchemaError("AyurParam presented an unverified claim as modern clinical efficacy")
        efficacy_match = _UNQUALIFIED_EFFICACY.search(sentence)
        traditional_framing = bool(_TRADITIONAL_FRAMING.search(sentence))
        if efficacy_match and not traditional_framing:
            if os.getenv("AYURSUTRA_ENV", "").casefold() == "development":
                LOGGER.warning(
                    "formulation_validation request_id=%s formulation=%r category=unqualified_efficacy matched_pattern=%r sentence=%r "
                    "traditional_framing_detected=false modern_clinical_efficacy_detected=false",
                    request_id or "-",
                    _safe_diagnostic_sentence(requested_formulation or "")[:120],
                    efficacy_match.group(0),
                    _safe_diagnostic_sentence(sentence),
                )
            raise ResponseSchemaError("AyurParam made an unqualified efficacy claim without traditional framing")
    if _FORMULA_PROPORTION.search(answer):
        raise ResponseSchemaError("AyurParam response asserted an unverified ingredient proportion")
    return answer


def detect_unverified_citations(answer: str) -> tuple[str, ...]:
    """Identify citation-like content for warning; never treat it as verified evidence."""
    if not isinstance(answer, str):
        return ()
    return tuple(name for name, pattern in _CITATION_PATTERNS.items() if pattern.search(answer))


def validate_formulation_relevance(
    name: str, answer: str, *, request_id: str | None = None
) -> None:
    """Reject obvious category mismatch or answers lacking formulation context.

    This is a conservative identity/relevance check, not verification of
    ingredients, traditional authenticity, or scholarly correctness.
    """
    subject = " ".join(str(name).casefold().split())
    display_name = _safe_diagnostic_sentence(subject)[:120]

    def reject(category: str, rule: str, sentence: str | None = None) -> None:
        if os.getenv("AYURSUTRA_ENV", "").casefold() == "development":
            LOGGER.warning(
                "formulation_relevance request_id=%s formulation_name=%r outcome=rejected "
                "rejection_category=%s matched_rule=%s triggering_sentence=%r",
                request_id or "-", display_name, category, rule,
                _safe_diagnostic_sentence(sentence) if sentence else "",
            )
        raise FormulationRelevanceError(category, rule)

    if not subject or not isinstance(answer, str) or not answer.strip():
        reject("empty_or_missing_input", "required_name_or_answer_missing")

    subject_terms = [term for term in re.findall(r"[a-z0-9]+", subject) if len(term) > 3]
    sentences = re.split(r"(?<=[.!?])\s+", answer)
    subject_pattern = re.compile(r"\b(?:" + "|".join(re.escape(term) for term in subject_terms) + r")\b", re.I) if subject_terms else None
    named_dish_claims = [
        sentence for sentence in sentences
        if subject_pattern and subject_pattern.search(sentence)
        and _DISH_IDENTITY_ASSERTION.search(sentence)
    ]
    if named_dish_claims:
        reject("identity_mismatch", "requested_formulation_asserted_as_ordinary_dish", named_dish_claims[0])

    # Also catch repeated culinary identity descriptions where the formulation
    # name is repeated across the response but not repeated in every sentence.
    subject_mentions = len(subject_pattern.findall(answer)) if subject_pattern else 0
    dish_mentions = len(_ORDINARY_DISH_IDENTITY.findall(answer))
    culinary_staples = len(set(_ORDINARY_RECIPE_FOODS.findall(answer)))
    if subject_mentions >= 2 and dish_mentions >= 2 and culinary_staples >= 2 and _REGIONAL_DISH_CUES.search(answer):
        trigger = next((sentence for sentence in sentences if _REGIONAL_DISH_CUES.search(sentence)), None)
        reject("identity_mismatch", "repeated_regional_culinary_identity", trigger)

    if (subject_pattern and subject_pattern.search(answer)
            and _ORDINARY_DISH_IDENTITY.search(answer)
            and _REGIONAL_DISH_CUES.search(answer)
            and culinary_staples >= 2):
        trigger = next((sentence for sentence in sentences if _REGIONAL_DISH_CUES.search(sentence)), None)
        reject("identity_mismatch", "named_formulation_in_regional_dish_context", trigger)

    cooking_methods = re.findall(
        r"\b(?:fry|sauté|saute|stir[- ]fry|cook|simmer|boil|bake|roast|serve hot)\b",
        answer,
        re.I,
    )
    ordinary_food_count = len(set(x.casefold() for x in _ORDINARY_RECIPE_FOODS.findall(answer)))
    structured_recipe = bool(_FOOD_RECIPE_METHOD.search(answer))
    if len(cooking_methods) >= 2 and ordinary_food_count >= 2 and structured_recipe:
        trigger = next((sentence for sentence in sentences if _FOOD_RECIPE_METHOD.search(sentence)), None)
        reject("unrelated_food_recipe", "recipe_structure_with_multiple_cooking_methods_and_foods", trigger)

    body = re.sub(r"(?m)^\s{0,3}#{1,6}\s+.*$", " ", answer)
    subject_in_body = not subject_terms or any(
        re.search(rf"\b{re.escape(term)}\b", body, re.I) for term in subject_terms
    )
    if not subject_in_body or not _FORMULATION_CONTEXT.search(body):
        trigger = next((sentence for sentence in sentences if sentence.strip() and not sentence.lstrip().startswith("#")), None)
        category = "missing_formulation_identity" if not subject_in_body else "missing_formulation_context"
        rule = "requested_name_absent_from_answer_body" if not subject_in_body else "no_formulation_context_anchor"
        reject(category, rule, trigger)

    if os.getenv("AYURSUTRA_ENV", "").casefold() == "development":
        LOGGER.info(
            "formulation_relevance request_id=%s formulation_name=%r outcome=accepted "
            "rejection_category=none matched_rule=identity_and_context_present triggering_sentence=''",
            request_id or "-", display_name,
        )


def build_formulation_explanation(name: str, llm, *, request_id: str | None = None) -> dict:
    """Generate a natural-language answer directly from the configured model."""
    subject = name.strip() if isinstance(name, str) else ""
    if not subject:
        raise ValueError("Enter a formulation name.")
    request_id = request_id or new_formulation_request_id()
    provider = configured_provider()
    if provider == "mock":
        raise RuntimeError("Mock mode is active; no formulation answer was generated.")
    if provider != "ollama":
        raise RuntimeError(f"Configured provider {provider!r} is not the AyurParam Ollama adapter.")

    system = (
        "You are an academic Ayurveda research assistant. Give a natural-language overview of the named "
        "formulation, focusing on its identity, ingredients, and traditional descriptions only where you "
        "have reasonable confidence. Clearly qualify traditional descriptions as traditional and not "
        "clinically established; distinguish them from modern scientific claims. State uncertainty rather "
        "than guessing, and do not invent ingredients, proportions, botanical identities, properties, or uses. "
        "This direct response has no source verification: do not name or attribute any text, author, scripture, "
        "or other source; do not give reference numbers, quotations, citations, or bibliography. Do not make "
        "clinical efficacy claims or give diagnosis, dosage, prescription, self-medication, patient-specific "
        "treatment, or preparation instructions. Respond in readable Markdown, not JSON."
    )
    prompt = (
        f"The requested Ayurvedic formulation is {subject}. Explain this formulation, not an ordinary "
        "food, regional dish, recipe, or similarly named item. Use concise Markdown sections: "
        "Identification and traditional context; Known composition (only if sufficiently confident); "
        "Traditionally described characteristics; Limitations and uncertainties. Omit sections that you "
        "cannot support from your knowledge. Do not invent ingredients, botanical identities, classical "
        "references, properties, or preparation methods. If you cannot confidently identify this specific "
        "formulation, explicitly say: 'I cannot provide a reliable explanation for this formulation.'"
    )
    # Keep the existing token budget and temperature configuration. The prompt
    # no longer asks for a target length or prescribed heading structure.
    raw = llm.generate(
        prompt, max_new_tokens=1100, system=system, format_schema=False,
        request_id=request_id, formulation_name=subject,
    )
    if not isinstance(raw, str) or not raw.strip():
        raise ResponseSchemaError("AyurParam returned an empty formulation explanation")
    answer = raw
    # Hard safety gate: unsafe actionable content is never returned to UI state.
    if _UNSAFE_INSTRUCTIONS.search(answer):
        categories = [name for name, pattern in _UNSAFE_CATEGORIES.items() if pattern.search(answer)]
        detail = ", ".join(categories) if categories else "prohibited instructions"
        raise ResponseSchemaError("AyurParam response contained prohibited instructions (" + detail + ")")

    explicitly_abstained = bool(_MODEL_ABSTENTION.search(answer))
    try:
        if explicitly_abstained:
            raise FormulationRelevanceError("model_abstention", "model_could_not_identify_formulation")
        validate_formulation_relevance(subject, answer, request_id=request_id)
        relevance = {"status": "passed", "category": None, "reason": None}
    except FormulationRelevanceError as exc:
        relevance = {"status": "failed", "category": exc.category, "reason": exc.reason}

    clinical_sentences: list[str] = []
    unqualified_sentences: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", answer):
        clinical_match = _CLINICAL_EFFICACY.search(sentence)
        if clinical_match:
            nearby_negation = re.search(
                r"\b(?:not|no|cannot|does not|isn't|is not)\b.{0,45}\b(?:proven|evidence|efficacy|effective|clinical)\b",
                sentence,
                re.I,
            )
            if not nearby_negation:
                clinical_sentences.append(_safe_diagnostic_sentence(sentence))
                if os.getenv("AYURSUTRA_ENV", "").casefold() == "development":
                    LOGGER.warning(
                        "formulation_validation request_id=%s formulation=%r category=modern_clinical_efficacy "
                        "matched_pattern=%r sentence=%r traditional_framing_detected=%s modern_clinical_efficacy_detected=true",
                        request_id, _safe_diagnostic_sentence(subject)[:120], clinical_match.group(0),
                        _safe_diagnostic_sentence(sentence), bool(_TRADITIONAL_FRAMING.search(sentence)),
                    )
        if _UNQUALIFIED_EFFICACY.search(sentence) and not _TRADITIONAL_FRAMING.search(sentence):
            unqualified_sentences.append(_safe_diagnostic_sentence(sentence))
            if os.getenv("AYURSUTRA_ENV", "").casefold() == "development":
                LOGGER.warning(
                    "formulation_validation request_id=%s formulation=%r category=unqualified_efficacy "
                    "matched_pattern=%r sentence=%r traditional_framing_detected=false modern_clinical_efficacy_detected=false",
                    request_id, _safe_diagnostic_sentence(subject)[:120],
                    _UNQUALIFIED_EFFICACY.search(sentence).group(0), _safe_diagnostic_sentence(sentence),
                )
    citation_kinds = detect_unverified_citations(answer)
    citation_warning = UNVERIFIED_CITATION_WARNING if citation_kinds or _QUOTED_TEXT.search(answer) else None
    warnings = []
    # An explicit model abstention is its own result category, not a relevance
    # warning. The UI presents the neutral status while preserving the original
    # response below it.
    if relevance["status"] == "failed" and not explicitly_abstained:
        warnings.append(FORMULATION_RELEVANCE_ERROR)
    if clinical_sentences:
        warnings.append("Unverified modern clinical-efficacy claims were detected; do not treat them as established facts.")
    if unqualified_sentences:
        warnings.append("Unqualified efficacy claims were detected; they are not verified in Direct AyurParam mode.")
    if citation_warning:
        warnings.append(citation_warning)
    if _FORMULA_PROPORTION.search(answer):
        warnings.append("Unverified ingredient proportions were detected.")
    return {
        "canonical_name": subject,
        "request_id": request_id,
        "answer": answer,
        "mode": "direct_formulation",
        "model": getattr(llm, "model_name", OLLAMA_MODEL),
        "disclaimer": FORMULATION_DISCLAIMER,
        "citation_warning": citation_warning,
        "citation_kinds": citation_kinds,
        "safety_status": "passed",
        "validation_status": "failed" if relevance["status"] == "failed" or clinical_sentences or unqualified_sentences else "passed",
        "relevance": relevance,
        "clinical_efficacy_status": "failed" if clinical_sentences else "passed",
        "result_category": (
            "model_abstention" if explicitly_abstained
            else "relevance_failure" if relevance["status"] == "failed"
            else "answer"
        ),
        "clinical_efficacy_sentences": clinical_sentences,
        "unqualified_efficacy_sentences": unqualified_sentences,
        "warnings": warnings,
    }


def build_anupana_explanation(name: str, llm, *, request_id: str | None = None) -> dict:
    """Explain an Anupana directly, sharing provider and safety validation."""
    subject = name.strip() if isinstance(name, str) else ""
    if not subject:
        raise ValueError("Enter an Anupana name.")
    provider = configured_provider()
    if provider == "mock":
        raise RuntimeError("Mock mode is active; no Anupana answer was generated.")
    if provider != "ollama":
        raise RuntimeError(f"Configured provider {provider!r} is not the AyurParam Ollama adapter.")
    system = (
        "You are an academic Ayurveda research assistant. Provide a concise, natural-language Markdown "
        "explanation of the named Anupana. When you have sufficient knowledge, organize it with these "
        "headings: Ayurvedic Identity; Traditionally Described Properties; Traditional Context and "
        "Associations; Relationship with Dravya and Formulations; Important Limitations and Uncertainty. "
        "Omit any section you cannot support; do not fill gaps with guesses or generic filler. Avoid repeating "
        "the Anupana name unnecessarily and keep the introduction brief. Distinguish traditional descriptions "
        "from modern scientific claims; do not present modern clinical efficacy as established fact. Do not "
        "invent classical references, ingredients, properties, relationships, therapeutic claims, citations, or "
        "quotations. You may clearly state that you cannot identify the concept when uncertain. Do not give "
        "dosage, administration, diagnosis, self-medication, patient-specific treatment, prescription, or "
        "hazardous preparation instructions. This is direct model output, not source-verified. Return Markdown, not JSON."
    )
    prompt = (
        f"Explain the Anupana named {subject}. Keep the response concise, academic, and useful. Use the "
        "requested headings only where you can provide relevant information, and state uncertainty plainly."
    )
    request_id = request_id or new_formulation_request_id()
    raw = llm.generate(
        prompt,
        max_new_tokens=1100,
        system=system,
        format_schema=False,
        request_id=request_id,
        formulation_name=subject,
    )
    # Validate without normalizing the model's Markdown; the original response
    # is what the researcher sees and any prohibited output still fails closed.
    validate_formulation_answer(raw, request_id=request_id, requested_formulation=subject)
    answer = raw
    citation_kinds = detect_unverified_citations(answer)
    explicitly_abstained = bool(_MODEL_ABSTENTION.search(answer))
    return {
        "canonical_name": subject,
        "request_id": request_id,
        "answer": answer,
        "mode": "direct_anupana",
        "result_category": "model_abstention" if explicitly_abstained else "answer",
        "model": getattr(llm, "model_name", OLLAMA_MODEL),
        "disclaimer": FORMULATION_DISCLAIMER,
        "citation_warning": UNVERIFIED_CITATION_WARNING if citation_kinds else None,
        "citation_kinds": citation_kinds,
    }


__all__ = [
    "FORMULATION_ABSTENTION_MESSAGE", "FORMULATION_DISCLAIMER", "FORMULATION_RELEVANCE_ERROR",
    "UNVERIFIED_CITATION_WARNING", "FormulationAbstentionError", "FormulationRelevanceError",
    "OllamaError", "ResponseSchemaError",
    "build_anupana_explanation", "build_formulation_explanation", "configured_provider", "new_formulation_request_id",
    "detect_unverified_citations", "validate_formulation_answer", "validate_formulation_relevance",
]
