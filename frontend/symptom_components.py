"""Presentation helpers for symptom analysis results and exports."""
from __future__ import annotations

import html
import json
from pathlib import Path

import pymupdf as fitz
import streamlit as st
import streamlit.components.v1 as components

STAGES = [
    ("understand", "Understanding symptom description"),
    ("search", "Searching classical knowledge"),
    ("retrieve", "Retrieving relevant passages"),
    ("generate", "Generating AyurParam explanation"),
    ("validate", "Validating generated references"),
]


def render_loading_steps(target, states: dict[str, str]) -> None:
    marks = {"complete": "&#10003;", "running": "&#9679;", "failed": "&#10005;", "skipped": "&#8212;", "pending": "&#9675;"}
    rows = []
    for key, label in STAGES:
        state = states.get(key, "pending")
        detail = {"complete": "Complete", "running": "In progress", "failed": "Could not complete", "skipped": "Not needed for this result", "pending": "Waiting"}[state]
        rows.append(
            f'<div class="analysis-step {state}"><span class="step-mark">{marks[state]}</span>'
            f'<span class="step-name">{html.escape(label)}</span><span class="step-state">{detail}</span></div>'
        )
    target.markdown(
        """<style>
        .analysis-steps{display:grid;gap:0}.analysis-step{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 2px;border-bottom:1px solid #E3E9E2;color:#64736A;font:500 14px 'DM Sans',sans-serif}
        .analysis-step:last-child{border-bottom:0}.analysis-step .step-mark{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;background:#F0F3EF;color:#78877D;font-size:12px}
        .analysis-step.running .step-mark{background:#EDF3EC;color:#174C3C}.analysis-step.complete .step-mark{background:#E6F1E8;color:#174C3C}.analysis-step.failed .step-mark{background:#FCEBE9;color:#A2342C}.analysis-step.skipped .step-mark{background:#F6F7F4;color:#78877D}
        .analysis-step .step-name{color:#1D2E26}.analysis-step .step-state{color:#78877D;font-size:12px}
        @media(max-width:520px){.analysis-step{grid-template-columns:22px minmax(0,1fr);gap:8px}.analysis-step .step-state{grid-column:2}}
        </style><div class="analysis-steps">""" + "".join(rows) + "</div>",
        unsafe_allow_html=True,
    )


def analysis_plain_text(result: dict, details: dict | None = None) -> str:
    details = details or {}
    lines = ["AYURFORM AI - ACADEMIC KNOWLEDGE REVIEW", "", "SOURCE-GROUNDED SUMMARY", result.get("original_description", result.get("user_query", ""))]
    extracted = result.get("extracted_symptoms") or []
    lines.append("Extracted symptom terms: " + (", ".join(extracted) if extracted else "No predefined symptom terms identified."))
    for label, key in (("Duration", "duration"), ("Severity", "severity"), ("Frequency", "frequency"), ("Age range", "age_range")):
        if details.get(key):
            lines.append(f"{label}: {details[key]}")
    lines += ["", "POSSIBLE AYURVEDIC CONCEPTS"]
    concepts = result.get("possible_concepts") or []
    if concepts:
        for concept in concepts:
            lines.append(f"{concept.get('name', 'Concept')}: {concept.get('reason', '')}")
            if concept.get("supporting_passage_ids"):
                lines.append("Supporting retrieved passages: " + ", ".join(concept["supporting_passage_ids"]))
    else:
        lines.append("No model-generated concept association is provided.")
    lines += ["", "RETRIEVED CLASSICAL REFERENCES"]
    passages = result.get("passages") or []
    if passages:
        for i, passage in enumerate(passages, 1):
            lines += [f"[{i}] {passage.get('reference', 'Source metadata unavailable')}", passage.get("text", "")]
    else:
        lines.append("No relevant passages were found in the indexed collection.")
    if result.get("mode") == "ayurparam" and result.get("evidence_summary"):
        lines += ["", "AYURPARAM EXPLANATION", result["evidence_summary"]]
    elif result.get("evidence_summary"):
        lines += ["", "RESULT STATUS", result["evidence_summary"]]
    if result.get("limitations"):
        lines += ["", "EVIDENCE LIMITATIONS", result["limitations"]]
    lines += ["", "EDUCATIONAL DISCLAIMER", result.get("disclaimer", "For education only. This is not a diagnosis or substitute for professional care.")]
    return "\n".join(lines)


def render_copy_button(text: str, key: str = "analysis-copy") -> None:
    safe_payload = json.dumps(text, ensure_ascii=False).replace("<", "\\u003c").replace("</", "<\\/")
    button_id = html.escape(key, quote=True)
    components.html(
        f"""<button id="{button_id}" type="button" aria-label="Copy answer">Copy answer</button>
        <span id="copy-feedback" role="status" aria-live="polite"></span>
        <style>
        body{{margin:0;font-family:'DM Sans',Arial,sans-serif;display:flex;align-items:center;gap:10px}}
        button{{height:42px;padding:0 16px;border:1px solid #174C3C;border-radius:10px;background:#174C3C;color:#fff;font-size:14px;font-weight:600;cursor:pointer}}
        button:hover{{background:#10372D}}#copy-feedback{{font-size:12px;color:#287557}}
        </style>
        <script>
        const answer={safe_payload};
        const button=document.getElementById("{button_id}");
        const feedback=document.getElementById("copy-feedback");
        button.addEventListener("click",async()=>{{
          try{{
            if(navigator.clipboard && window.isSecureContext){{await navigator.clipboard.writeText(answer);}}
            else{{const box=document.createElement('textarea');box.value=answer;box.style.position='fixed';box.style.opacity='0';document.body.appendChild(box);box.select();if(!document.execCommand('copy'))throw new Error('copy unavailable');box.remove();}}
            feedback.textContent="Copied";
          }}catch(e){{feedback.textContent="Copy unavailable in this browser";}}
        }});
        </script>""",
        height=48,
        scrolling=False,
    )


def build_analysis_pdf(result: dict, details: dict | None = None) -> bytes:
    text = analysis_plain_text(result, details)
    fonts = Path("C:/Windows/Fonts")
    regular_path = next((p for p in (fonts / "arial.ttf", fonts / "segoeui.ttf", fonts / "Nirmala.ttf") if p.exists()), None)
    bold_path = next((p for p in (fonts / "arialbd.ttf", fonts / "segoeuib.ttf") if p.exists()), None)
    document = fitz.open()
    regular_name = "helv"
    bold_name = "hebo"
    regular_font = fitz.Font("helv")
    bold_font = fitz.Font("hebo")
    if regular_path:
        regular_name = "AyurSutraRegular"
        regular_font = fitz.Font(fontfile=str(regular_path))
    if bold_path:
        bold_name = "AyurSutraBold"
        bold_font = fitz.Font(fontfile=str(bold_path))

    page = None
    y = 54
    width = 508
    margin = 52

    def new_page():
        nonlocal page, y
        page = document.new_page(width=612, height=792)
        if regular_path:
            page.insert_font(fontname=regular_name, fontfile=str(regular_path))
        if bold_path:
            page.insert_font(fontname=bold_name, fontfile=str(bold_path))
        page.draw_rect(fitz.Rect(0, 0, 612, 10), color=None, fill=(0.09, 0.30, 0.24))
        y = 52

    def write_line(value: str, *, size: float = 10.5, bold: bool = False, gap: float = 0) -> None:
        nonlocal y
        if page is None:
            new_page()
        font = bold_font if bold else regular_font
        fontname = bold_name if bold else regular_name
        available = width
        words = value.split()
        wrapped, current = [], ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and font.text_length(candidate, fontsize=size) > available:
                wrapped.append(current)
                current = word
            else:
                current = candidate
        if current or not wrapped:
            wrapped.append(current)
        line_height = size * 1.45
        for line in wrapped:
            if y + line_height > 746:
                new_page()
            render_line = line
            if not regular_path:
                render_line = render_line.encode("cp1252", errors="replace").decode("cp1252")
            page.insert_text((margin, y + size), render_line, fontname=fontname, fontsize=size, color=(0.12, 0.19, 0.16))
            y += line_height
        y += gap

    new_page()
    for line in text.splitlines():
        if line == "AYURFORM AI - ACADEMIC KNOWLEDGE REVIEW":
            write_line(line, size=18, bold=True, gap=8)
        elif line and line == line.upper() and len(line) < 45:
            write_line(line, size=11.5, bold=True, gap=2)
        elif not line:
            y += 4
        else:
            write_line(line)
    for index, page_item in enumerate(document, 1):
        page_item.insert_text((520, 770), f"{index}", fontname="helv", fontsize=8, color=(0.39, 0.45, 0.42))
    data = document.tobytes(deflate=True)
    document.close()
    return data

