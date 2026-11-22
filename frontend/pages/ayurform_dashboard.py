"""Premium editorial research dashboard for AyurForm AI."""
from __future__ import annotations

import html
import os

import streamlit as st

from config import (
    ACTIVE_CHROMA_COLLECTION,
    EMBEDDING_MODEL_NAME,
    KNOWLEDGE_MODE,
    LLM_MODE,
    LLM_PROVIDER,
    OLLAMA_MODEL,
)
from frontend.pages.dashboard import _embedding_status, _go, _snapshot


RESEARCH_SUGGESTIONS = (
    "Explore the traditional properties of Tulsi",
    "Investigate the ingredients of Chyawanprash",
    "Understand the concept of Anupana",
    "Explore classical references for Ashwagandha",
)

_PRODUCTION_RIGHTS = {"verified", "licensed", "public_domain"}

_DOMAINS = (
    (
        "dravya",
        "Dravya Explorer",
        "Explore medicinal substances, botanical identities, properties and documented classical attributes.",
        "Dravya Explorer",
        "Explore Dravya",
    ),
    (
        "formulation",
        "Formulation Explorer",
        "Explore Ayurvedic formulations, ingredients and documented traditional context.",
        "Formulation Explorer",
        "Explore formulations",
    ),
    (
        "anupana",
        "Anupana Explorer",
        "Explore documented Anupana relationships and their traditional context.",
        "Anupana Explorer",
        "Explore Anupana",
    ),
)


def _count(table: str) -> int | None:
    """Count records returned by the existing public-readable store."""
    try:
        from ayurform_store import rows

        records = rows(table, limit=100000)
        if table == "sources":
            return sum(
                1
                for record in records
                if record.get("usage_scope") == "production"
                and record.get("rights_status") in _PRODUCTION_RIGHTS
            )
        return len(records)
    except Exception:
        return None


def is_admin_email(email: str | None, *, configured: str | None = None) -> bool:
    """Match the existing reviewer email allowlist."""
    configured = os.getenv("AYURFORM_ADMIN_EMAILS", "") if configured is None else configured
    allowed = {item.strip().casefold() for item in configured.split(",") if item.strip()}
    return bool(email and email.strip().casefold() in allowed)


def _model_status() -> str:
    """Use the Research Assistant's live Ollama availability check."""
    try:
        from frontend.pages.research_assistant import _model_status as check_model

        return check_model()
    except Exception:
        return "Status unavailable"


def _database_status() -> tuple[str, str]:
    try:
        from ayurform_store import db_health

        health = db_health()
        backend = str(health.get("backend", "unknown")).replace("_", " ").title()
        if health.get("connected"):
            return "Connected", f"{backend} · health check passed"
        return "Unavailable", f"{backend} · connection check failed"
    except Exception:
        return "Unavailable", "Structured database health check failed"


def queue_research_query(query: str, state: dict) -> bool:
    """Queue a non-empty question for the existing Research Assistant route."""
    cleaned = query.strip()
    if not cleaned:
        return False
    state["research_prefill"] = cleaned
    state["page"] = "Research Assistant"
    return True


def _set_research_query(query: str) -> bool:
    """Queue a query and rerun into Research Assistant when it is non-empty."""
    if not queue_research_query(query, st.session_state):
        return False
    st.rerun()
    return True


def _tone(status: str) -> str:
    value = status.casefold()
    if value in {"available", "connected"}:
        return "good"
    if value in {"development-only", "configured", "weights cached", "status unavailable"}:
        return "caution"
    return "unavailable"


def _format_metric(value: int | None) -> str:
    return "Unavailable" if value is None else f"{value:,}"


def _domain_art(kind: str) -> str:
    """Small inline illustrations; kept local and dependency-free."""
    if kind == "dravya":
        return """<svg class="af-card-illustration af-card-illustration--dravya" viewBox="0 0 150 112" role="img" aria-label="Botanical leaf illustration">
        <path d="M32 99C43 77 55 55 81 25M54 67C31 67 20 52 22 35c19 0 34 10 35 26M68 48c-1-20 12-34 31-37 2 19-7 34-27 40M43 83c-16-1-28-12-30-27 16-1 29 7 35 21" fill="none" stroke="#245641" stroke-width="2.4" stroke-linecap="round"/>
        <path d="M23 36c15 2 26 11 34 25M99 12C90 26 80 37 68 47M13 58c13 4 24 12 31 24" fill="none" stroke="#78947A" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="117" cy="26" r="3" fill="#C3A36A"/><circle cx="126" cy="38" r="1.7" fill="#C3A36A"/>
        </svg>"""
    if kind == "formulation":
        return """<svg class="af-card-illustration af-card-illustration--formulation" viewBox="0 0 150 112" role="img" aria-label="Traditional vessel illustration">
        <path d="M39 35h72l-7 12c-2 4-3 8-3 12v22c0 9-7 16-16 16H65c-9 0-16-7-16-16V59c0-4-1-8-3-12l-7-12Z" fill="#E8DDC7" stroke="#765F3A" stroke-width="2"/>
        <path d="M40 35c0-8 13-14 35-14s35 6 35 14M49 56h51M53 72h43M58 87h33" fill="none" stroke="#765F3A" stroke-width="2" stroke-linecap="round"/>
        <path d="M66 21c2-8 7-12 9-18 5 6 8 11 7 18" fill="none" stroke="#C3A36A" stroke-width="2" stroke-linecap="round"/>
        <circle cx="118" cy="34" r="3" fill="#C3A36A"/>
        </svg>"""
    return """<svg class="af-card-illustration af-card-illustration--anupana" viewBox="0 0 150 112" role="img" aria-label="Water drop and ripple illustration">
        <path d="M75 14C63 34 43 53 43 70a32 32 0 0 0 64 0c0-17-20-36-32-56Z" fill="#DCEAE3" stroke="#245641" stroke-width="2.2"/>
        <path d="M61 68c3-8 8-14 14-22M59 83c9 7 23 7 32 0M25 95c14-7 28-7 42 0M83 95c14-7 28-7 42 0" fill="none" stroke="#78947A" stroke-width="1.7" stroke-linecap="round"/>
        <circle cx="115" cy="27" r="3" fill="#C3A36A"/><circle cx="125" cy="42" r="1.8" fill="#C3A36A"/>
        </svg>"""


def _hero_art() -> str:
    return """<svg class="af-hero-art" viewBox="0 0 500 390" role="img" aria-label="Botanical branch, manuscript and connected research nodes">
    <g class="af-art-orbit af-art-orbit--outer"><circle cx="260" cy="193" r="154" fill="none" stroke="#C3A36A" stroke-opacity=".32" stroke-width="1.2"/></g>
    <g class="af-art-orbit af-art-orbit--inner"><circle cx="260" cy="193" r="129" fill="none" stroke="#A9BFA9" stroke-opacity=".24" stroke-width="1"/></g>
    <path d="M126 319c45-56 72-113 95-203M176 233c-39 1-61-23-61-58 33 1 57 18 67 48M198 185c-4-39 18-68 53-78 8 35-7 64-45 81M146 284c-31-5-48-25-45-54 30 2 50 18 58 45M211 147c-5-26 9-48 32-57" fill="none" stroke="#A9BFA9" stroke-width="3" stroke-linecap="round"/>
    <g class="af-leaf-sway af-leaf-sway--one"><path d="M115 175c33 1 57 18 67 48-39 1-61-23-61-58Z" fill="#A9BFA9" fill-opacity=".18" stroke="#A9BFA9" stroke-width="2"/><path d="M119 170c24 4 45 21 63 53" fill="none" stroke="#D8E1D2" stroke-width="1.5"/></g>
    <g class="af-leaf-sway af-leaf-sway--two"><path d="M198 185c-4-39 18-68 53-78 8 35-7 64-45 81Z" fill="#A9BFA9" fill-opacity=".16" stroke="#A9BFA9" stroke-width="2"/><path d="M201 184c17-25 33-49 50-77" fill="none" stroke="#D8E1D2" stroke-width="1.4"/></g>
    <g class="af-leaf-sway af-leaf-sway--three"><path d="M103 230c30 2 50 18 58 45-31-5-48-25-45-54Z" fill="#A9BFA9" fill-opacity=".14" stroke="#A9BFA9" stroke-width="1.8"/></g>
    <g class="af-leaf-sway af-leaf-sway--four"><path d="M211 147c-5-26 9-48 32-57 5 24-6 44-30 59Z" fill="#A9BFA9" fill-opacity=".14" stroke="#A9BFA9" stroke-width="1.7"/></g>
    <path d="M245 204h48m0 0 28-31m-28 31 31 31m-79 0h48" fill="none" stroke="#C3A36A" stroke-opacity=".85" stroke-width="1.5" stroke-dasharray="5 7" class="af-art-connections"/>
    <circle cx="245" cy="204" r="5" fill="#C3A36A" class="af-art-node af-art-node--one"/><circle cx="293" cy="204" r="4" fill="#E7D8B5" class="af-art-node af-art-node--two"/><circle cx="321" cy="173" r="4" fill="#C3A36A" class="af-art-node af-art-node--three"/><circle cx="324" cy="235" r="4" fill="#C3A36A" class="af-art-node af-art-node--four"/>
    <path d="M293 204c0-16 13-29 29-29M293 204c0 17 14 31 31 31" fill="none" stroke="#A9BFA9" stroke-width="1.2"/>
    <path d="M258 250c0-21 17-38 38-38s38 17 38 38v18h-76v-18Z" fill="#F6F3E9" fill-opacity=".11" stroke="#E4D6B2" stroke-width="1.7"/>
    <path d="M258 250c13 8 26 8 38 0 13 8 25 8 38 0M267 259h57M267 267h57" fill="none" stroke="#E4D6B2" stroke-opacity=".88" stroke-width="1.2"/>
    <circle cx="352" cy="108" r="2.5" fill="#C3A36A" class="af-art-particle af-art-particle--one"/><circle cx="379" cy="137" r="1.8" fill="#C3A36A" class="af-art-particle af-art-particle--two"/><circle cx="361" cy="294" r="2" fill="#C3A36A" class="af-art-particle af-art-particle--three"/>
    </svg>"""


def _research_art() -> str:
    """Quiet, decorative network motif; it does not imply active model work."""
    return """<div class="af-ai-visual" aria-hidden="true"><svg viewBox="0 0 240 180">
    <g class="af-ai-orbit"><ellipse cx="120" cy="90" rx="82" ry="37" fill="none" stroke="#287557" stroke-opacity=".25" stroke-width="1" transform="rotate(-28 120 90)"/></g>
    <g class="af-ai-orbit af-ai-orbit--reverse"><ellipse cx="120" cy="90" rx="78" ry="31" fill="none" stroke="#C3A36A" stroke-opacity=".35" stroke-width="1" transform="rotate(34 120 90)"/></g>
    <path class="af-ai-link" d="M43 104 88 67l48 12 54-34M88 67l18 65 30-53 31 53M43 104l63 28 78-53" fill="none" stroke="#287557" stroke-opacity=".45" stroke-width="1.2" stroke-dasharray="4 6"/>
    <circle class="af-ai-node af-ai-node--one" cx="43" cy="104" r="5" fill="#287557"/><circle class="af-ai-node af-ai-node--two" cx="88" cy="67" r="5" fill="#C3A36A"/><circle class="af-ai-node af-ai-node--three" cx="136" cy="79" r="6" fill="#174C3C"/><circle class="af-ai-node af-ai-node--four" cx="190" cy="45" r="4" fill="#C3A36A"/><circle class="af-ai-node af-ai-node--five" cx="106" cy="132" r="4" fill="#287557"/><circle class="af-ai-node af-ai-node--six" cx="167" cy="132" r="5" fill="#174C3C"/>
    <circle cx="120" cy="90" r="102" fill="none" stroke="#287557" stroke-opacity=".08" stroke-width="1"/>
    </svg></div>"""


def _styles() -> None:
    st.html(
        """<style>
        .st-key-ayurform_dashboard{width:100%;max-width:1480px;margin:0 auto;padding-bottom:1.2rem}
        .st-key-ayurform_dashboard .af-hero{position:relative;isolation:isolate;overflow:hidden;display:grid;grid-template-columns:minmax(0,1.14fr) minmax(280px,.86fr);gap:1.5rem;align-items:center;min-height:350px;padding:clamp(1.5rem,4vw,3.25rem);border-radius:5px 26px 5px 26px;background:#10372D;color:#fff}
        .st-key-ayurform_dashboard .af-hero:before{content:"";position:absolute;z-index:-1;inset:0;background:radial-gradient(ellipse at 76% 45%,rgba(40,117,87,.25),transparent 48%);pointer-events:none}
        .st-key-ayurform_dashboard .af-hero-copy{position:relative;z-index:1;max-width:740px}
        .st-key-ayurform_dashboard .af-eyebrow{display:flex;align-items:center;gap:.65rem;color:#E1D2A9;font:700 .72rem 'DM Sans',sans-serif;letter-spacing:.16em;text-transform:uppercase}
        .st-key-ayurform_dashboard .af-eyebrow:before{content:"";width:22px;height:1px;background:#C3A36A}
        .st-key-ayurform_dashboard .af-hero h1{max-width:700px;margin:1rem 0 .7rem;color:#fff!important;font:600 clamp(2.55rem,5.2vw,4.45rem)/1.02 'Playfair Display',serif!important;letter-spacing:-.035em!important}
        .st-key-ayurform_dashboard .af-hero p{max-width:640px;margin:.5rem 0 1.35rem;color:#E1E9E1!important;font:400 clamp(.95rem,1.2vw,1.08rem)/1.65 'DM Sans',sans-serif!important}
        .st-key-ayurform_dashboard .af-hero-art{display:block;width:min(100%,480px);height:auto;justify-self:center;filter:drop-shadow(0 14px 28px rgba(0,0,0,.12))}
        .st-key-ayurform_dashboard .af-hero-search-label{margin:0 0 .42rem;color:#F2E9D5;font-size:.77rem;font-weight:700;letter-spacing:.025em}
        .st-key-ayurform_dashboard .st-key-dashboard_hero{position:relative!important;isolation:isolate;min-height:350px;padding:clamp(1.5rem,4vw,3.25rem)!important;overflow:hidden;border-radius:5px 26px 5px 26px;background:radial-gradient(ellipse at 76% 43%,rgba(40,117,87,.38),transparent 47%),#10372D;color:#fff}
        .st-key-ayurform_dashboard .st-key-dashboard_hero [data-testid="stVerticalBlock"]{position:relative;z-index:1;justify-content:center}
        .st-key-ayurform_dashboard .st-key-dashboard_hero h1{max-width:700px;margin:1rem 0 .7rem;color:#fff!important;font:600 clamp(2.55rem,5.2vw,4.45rem)/1.02 'Playfair Display',serif!important;letter-spacing:-.035em!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero .af-hero-copy p{max-width:640px;margin:.5rem 0 1.35rem;color:#E1E9E1!important;font:400 clamp(.95rem,1.2vw,1.08rem)/1.65 'DM Sans',sans-serif!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero .af-hero-art{display:block;width:min(100%,480px);height:auto;justify-self:center;filter:drop-shadow(0 14px 28px rgba(0,0,0,.12))}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stForm"]{padding:.62rem!important;border:1px solid rgba(255,255,255,.72)!important;border-radius:14px!important;background:#FBFAF5!important;box-shadow:0 8px 22px rgba(0,0,0,.12)!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stHorizontalBlock"]{align-items:center;gap:.45rem!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stColumn"]{min-width:0!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search .stTextInput label{color:#53665B!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search .stTextInput input{min-height:50px;border:0!important;border-radius:8px!important;background:transparent!important;color:#1D2E26!important;box-shadow:none!important;font-size:.95rem!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search .stTextInput input::placeholder{color:#718077!important;opacity:1}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stForm"] [data-testid="stColumn"]:first-child{flex:0 0 40px!important;width:40px!important}
        .st-key-ayurform_dashboard .af-search-icon{display:grid;place-items:center;height:48px;color:#287557;font:400 1.65rem 'DM Sans',sans-serif}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search .stButton>button{min-height:48px!important;border-radius:9px!important;white-space:nowrap!important;background:#174C3C!important;border-color:#174C3C!important;color:#fff!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search .stButton>button p{margin:0!important;color:#fff!important;font-size:.83rem!important;font-weight:700!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stFormSubmitButton"] button,.st-key-ayurform_dashboard .st-key-dashboard_hero_search button[kind="primary"]{min-height:48px!important;border-radius:9px!important;background:#174C3C!important;border:1px solid #174C3C!important;color:#fff!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stFormSubmitButton"] button p,.st-key-ayurform_dashboard .st-key-dashboard_hero_search button[kind="primary"] p{color:#fff!important;font-size:.83rem!important;font-weight:700!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search .stButton>button:hover{background:#287557!important;border-color:#287557!important}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stAlert"]{margin-top:.65rem}
        .st-key-ayurform_dashboard .af-section-head{display:flex;align-items:end;justify-content:space-between;gap:1rem;margin:2rem 0 .8rem}
        .st-key-ayurform_dashboard .af-section-head h2{margin:0;color:#10372D!important;font:600 clamp(1.45rem,2.1vw,1.9rem)/1.2 'Playfair Display',serif!important;letter-spacing:-.02em!important}
        .st-key-ayurform_dashboard .af-section-head p{margin:0;color:#64736A;font-size:.82rem;line-height:1.5}
        .st-key-ayurform_dashboard .af-kpi-band{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);align-items:stretch;margin:.65rem 0 1.1rem;padding:1.05rem 0;border-top:1px solid #D8DFD5;border-bottom:1px solid #D8DFD5}
        .st-key-ayurform_dashboard .af-kpi-group{display:grid;align-items:stretch}
        .st-key-ayurform_dashboard .af-kpi-structured{grid-template-columns:repeat(3,minmax(0,1fr))}
        .st-key-ayurform_dashboard .af-kpi-corpus{grid-template-columns:repeat(2,minmax(0,1fr));border-left:1px solid #D8DFD5}
        .st-key-ayurform_dashboard .af-kpi{min-width:0;padding:.35rem 1.05rem}
        .st-key-ayurform_dashboard .af-kpi+.af-kpi{border-left:1px solid #E1E5DD}
        .st-key-ayurform_dashboard .af-kpi-group.af-kpi-corpus .af-kpi:first-child{border-left:0}
        .st-key-ayurform_dashboard .af-kpi-label{display:flex;align-items:center;gap:.42rem;color:#53665B;font-size:.69rem;font-weight:700;line-height:1.3;letter-spacing:.09em;text-transform:uppercase}
        .st-key-ayurform_dashboard .af-kpi-icon{color:#9A7C43;font-size:.92rem}
        .st-key-ayurform_dashboard .af-kpi-value{margin:.48rem 0 .2rem;color:#10372D;font:600 clamp(1.7rem,2.5vw,2.35rem)/1 'DM Sans',sans-serif;letter-spacing:-.055em}
        .st-key-ayurform_dashboard .af-kpi-detail{color:#64736A;font-size:.76rem;line-height:1.45}
        .st-key-ayurform_dashboard .af-dev-tag{display:inline-flex;align-items:center;gap:.3rem;margin:.38rem 0 0;padding:.2rem .48rem;border:1px solid #E4D6B2;border-radius:2px;background:#F8F3E7;color:#715A2F;font-size:.65rem;font-weight:700;letter-spacing:.035em}
        .st-key-ayurform_dashboard .af-domain-grid [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px!important;align-items:stretch}
        .st-key-ayurform_dashboard .af-domain-grid [data-testid="stColumn"]{width:auto!important;min-width:0!important;flex:initial!important}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya,.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation,.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana{position:relative!important;height:100%;overflow:visible}
        .st-key-ayurform_dashboard .af-domain-card{position:relative;display:flex;flex-direction:column;min-height:268px;height:100%;overflow:hidden;padding:1.1rem 1.2rem 1.05rem;border:1px solid rgba(30,65,48,.14);border-radius:3px 18px 3px 18px;color:#1D2E26;transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease}
        .st-key-ayurform_dashboard .af-domain-card:after{content:"";position:absolute;width:130px;height:130px;right:-52px;top:-58px;border:1px solid rgba(195,163,106,.35);border-radius:50%;pointer-events:none}
        .st-key-ayurform_dashboard .af-domain-card.dravya{background:#E9F0E7}
        .st-key-ayurform_dashboard .af-domain-card.formulation{background:#F1EBDD}
        .st-key-ayurform_dashboard .af-domain-card.anupana{background:#E4EFEB}
        .st-key-ayurform_dashboard .af-domain-card svg{width:118px;height:88px;margin:0 0 .45rem;align-self:flex-end}
        .st-key-ayurform_dashboard .af-card-illustration--dravya path:nth-of-type(2){transform-box:fill-box;transform-origin:70% 70%;animation:af-leaf-sway 6.8s ease-in-out infinite alternate}
        .st-key-ayurform_dashboard .af-card-illustration--formulation path:nth-of-type(3){transform-box:fill-box;transform-origin:50% 100%;animation:af-vessel-glow 3.8s ease-in-out infinite}
        .st-key-ayurform_dashboard .af-card-illustration--anupana path:nth-of-type(2){animation:af-ripple-drift 5.6s ease-in-out infinite alternate}
        .st-key-ayurform_dashboard .af-domain-card h3{max-width:95%;margin:.12rem 0 .42rem;color:#10372D!important;font:600 1.42rem/1.18 'Playfair Display',serif!important}
        .st-key-ayurform_dashboard .af-domain-card p{max-width:370px;margin:0;color:#40574A;font-size:.86rem;line-height:1.55}
        .st-key-ayurform_dashboard .af-domain-action{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-top:auto;padding-top:1rem;color:#174C3C;font-size:.78rem;font-weight:700}
        .st-key-ayurform_dashboard .af-domain-action span:last-child{font-size:1.1rem;color:#9A7C43;transition:transform .2s ease}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya [data-testid="stButton"],.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation [data-testid="stButton"],.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana [data-testid="stButton"]{position:absolute;inset:0;z-index:3;margin:0}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya .stButton>button,.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation .stButton>button,.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana .stButton>button{position:absolute;inset:0;width:100%!important;height:100%!important;min-height:100%!important;padding:0!important;border:0!important;border-radius:3px 18px 3px 18px!important;background:transparent!important;box-shadow:none!important;color:transparent!important;opacity:0}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya:has(button:focus-visible) .af-domain-card,.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation:has(button:focus-visible) .af-domain-card,.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana:has(button:focus-visible) .af-domain-card{outline:3px solid #C3A36A;outline-offset:3px}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya.af-card-hover .af-domain-action span:last-child,.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation.af-card-hover .af-domain-action span:last-child,.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana.af-card-hover .af-domain-action span:last-child{transform:translateX(4px)}
        .st-key-ayurform_dashboard .af-ai-panel{display:grid;grid-template-columns:minmax(0,.95fr) minmax(0,1.05fr);gap:clamp(1.1rem,3vw,2.25rem);align-items:center;margin-top:.75rem;padding:clamp(1.15rem,2.6vw,2rem);border-top:3px solid #C3A36A;border-bottom:1px solid #D8DFD5;background:#E8EEE5}
        .st-key-ayurform_dashboard .af-ai-panel h2{margin:.35rem 0 .45rem;color:#10372D!important;font:600 clamp(1.8rem,3vw,2.5rem)/1.1 'Playfair Display',serif!important}
        .st-key-ayurform_dashboard .af-ai-panel p{max-width:560px;margin:.2rem 0 .85rem;color:#40574A;font-size:.9rem;line-height:1.6}
        .st-key-ayurform_dashboard .af-ai-kicker{color:#287557;font-size:.68rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase}
        .st-key-ayurform_dashboard .af-ai-statuses{display:flex;flex-wrap:wrap;gap:.45rem .7rem;margin:.85rem 0 1rem}
        .st-key-ayurform_dashboard .af-ai-status{display:inline-flex;align-items:center;gap:.4rem;color:#34483D;font-size:.75rem;font-weight:600}
        .st-key-ayurform_dashboard .af-ai-status i{width:7px;height:7px;border-radius:50%;background:#718077}
        .st-key-ayurform_dashboard .af-ai-status.good i{background:#287557}
        .st-key-ayurform_dashboard .af-ai-status.caution i{background:#A17B38}
        .st-key-ayurform_dashboard .af-ai-status.unavailable i{background:#A6493B}
        .st-key-ayurform_dashboard .af-ai-panel .stButton>button{min-height:46px!important;padding:.65rem 1rem!important;border-radius:3px 12px 3px 12px!important}
        .st-key-ayurform_dashboard .af-question-heading{margin:0 0 .65rem;color:#53665B;font-size:.72rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase}
        .st-key-ayurform_dashboard .af-question-grid [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px!important}
        .st-key-ayurform_dashboard .af-question-grid [data-testid="stColumn"]{width:auto!important;min-width:0!important;flex:initial!important}
        .st-key-ayurform_dashboard .af-question-grid .stButton>button{height:auto!important;min-height:44px!important;padding:.55rem .7rem!important;border:1px solid #C7D4C6!important;border-radius:3px 10px 3px 10px!important;background:#F7F8F2!important;color:#34483D!important;text-align:left!important;white-space:normal!important}
        .st-key-ayurform_dashboard .af-question-grid .stButton>button p{margin:0!important;color:#34483D!important;font-size:.75rem!important;line-height:1.35!important;text-align:left!important;white-space:normal!important}
        .st-key-ayurform_dashboard .af-tools-grid [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px!important}
        .st-key-ayurform_dashboard .af-tools-grid [data-testid="stColumn"]{width:auto!important;min-width:0!important;flex:initial!important}
        .st-key-ayurform_dashboard .af-tool{min-height:82px;padding:.85rem 1rem;border-left:2px solid #C3A36A;background:rgba(255,255,255,.46)}
        .st-key-ayurform_dashboard .af-tool h3{margin:0 0 .2rem;color:#10372D!important;font:600 1rem 'DM Sans',sans-serif!important}
        .st-key-ayurform_dashboard .af-tool p{margin:0;color:#64736A;font-size:.75rem;line-height:1.4}
        .st-key-ayurform_dashboard .af-tools-grid .stButton>button{width:100%;margin-top:.35rem;min-height:38px;border-radius:3px 9px 3px 9px!important}
        .st-key-ayurform_dashboard .af-status-band{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));margin-top:.65rem;border-top:1px solid #D8DFD5;border-bottom:1px solid #D8DFD5}
        .st-key-ayurform_dashboard .af-status-cell{min-width:0;padding:.82rem .9rem}
        .st-key-ayurform_dashboard .af-status-cell+.af-status-cell{border-left:1px solid #D8DFD5}
        .st-key-ayurform_dashboard .af-status-top{display:flex;align-items:center;gap:.42rem;color:#34483D;font-size:.76rem;font-weight:700}
        .st-key-ayurform_dashboard .af-status-dot{width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:#7B887F}
        .st-key-ayurform_dashboard .af-status-dot.good{background:#287557}
        .st-key-ayurform_dashboard .af-status-dot.caution{background:#A17B38}
        .st-key-ayurform_dashboard .af-status-dot.unavailable{background:#A6493B}
        .st-key-ayurform_dashboard .af-status-detail{margin:.32rem 0 0;color:#64736A;font-size:.7rem;line-height:1.4;overflow-wrap:anywhere}
        .st-key-ayurform_dashboard .af-footer{margin-top:1rem;padding:.8rem 0 .2rem;color:#64736A;font-size:.76rem;line-height:1.5}
        @media(max-width:1050px){.st-key-ayurform_dashboard .af-status-band{grid-template-columns:repeat(3,minmax(0,1fr))}.st-key-ayurform_dashboard .af-status-cell:nth-child(4){border-left:0;border-top:1px solid #D8DFD5}.st-key-ayurform_dashboard .af-status-cell:nth-child(5){border-top:1px solid #D8DFD5}}
        @media(max-width:800px){.st-key-ayurform_dashboard .st-key-dashboard_hero{min-height:unset}.st-key-ayurform_dashboard .st-key-dashboard_hero [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:1rem!important}.st-key-ayurform_dashboard .st-key-dashboard_hero [data-testid="stColumn"]{width:auto!important;min-width:0!important;flex:initial!important}.st-key-ayurform_dashboard .st-key-dashboard_hero .af-hero-art{width:min(72%,330px);max-height:220px}.st-key-ayurform_dashboard .af-domain-grid [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(2,minmax(0,1fr))}.st-key-ayurform_dashboard .af-domain-grid .st-key-dashboard_domain_anupana{grid-column:1/-1}.st-key-ayurform_dashboard .af-domain-grid .st-key-dashboard_domain_anupana .af-domain-card{min-height:220px}.st-key-ayurform_dashboard .af-ai-panel{grid-template-columns:minmax(0,1fr)}}
        @media(max-width:600px){.st-key-ayurform_dashboard .st-key-dashboard_hero{padding:1.35rem 1.1rem!important;border-radius:4px 18px 4px 18px}.st-key-ayurform_dashboard .st-key-dashboard_hero h1{font-size:clamp(2.35rem,10vw,3.1rem)!important}.st-key-ayurform_dashboard .st-key-dashboard_hero .af-hero-art{width:min(68%,250px);max-height:170px}.st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stForm"]{padding:.5rem!important}.st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stForm"] [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:.25rem!important}.st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stForm"] [data-testid="stColumn"]:first-child{display:none!important}.st-key-ayurform_dashboard .st-key-dashboard_hero_search .stButton>button{width:100%!important}.st-key-ayurform_dashboard .af-section-head{align-items:flex-start;flex-direction:column;gap:.18rem;margin-top:1.55rem}.st-key-ayurform_dashboard .af-kpi-band{grid-template-columns:minmax(0,1fr);padding:.45rem 0}.st-key-ayurform_dashboard .af-kpi-group{grid-template-columns:repeat(2,minmax(0,1fr))}.st-key-ayurform_dashboard .af-kpi{padding:.72rem .55rem}.st-key-ayurform_dashboard .af-kpi:nth-child(odd){border-left:0}.st-key-ayurform_dashboard .af-kpi-structured{border-bottom:1px solid #D8DFD5;padding-bottom:.8rem}.st-key-ayurform_dashboard .af-kpi-corpus{border-left:0;padding-top:.55rem}.st-key-ayurform_dashboard .af-kpi-value{font-size:1.8rem}.st-key-ayurform_dashboard .af-kpi-label{font-size:.62rem}.st-key-ayurform_dashboard .af-kpi-detail{font-size:.7rem}.st-key-ayurform_dashboard .af-domain-grid [data-testid="stHorizontalBlock"],.st-key-ayurform_dashboard .af-tools-grid [data-testid="stHorizontalBlock"]{grid-template-columns:minmax(0,1fr)}.st-key-ayurform_dashboard .af-domain-grid .st-key-dashboard_domain_anupana{grid-column:auto}.st-key-ayurform_dashboard .af-domain-card,.st-key-ayurform_dashboard .af-domain-grid .st-key-dashboard_domain_anupana .af-domain-card{min-height:240px}.st-key-ayurform_dashboard .af-question-grid [data-testid="stHorizontalBlock"]{grid-template-columns:minmax(0,1fr)}.st-key-ayurform_dashboard .af-status-band{grid-template-columns:repeat(2,minmax(0,1fr))}.st-key-ayurform_dashboard .af-status-cell:nth-child(3),.st-key-ayurform_dashboard .af-status-cell:nth-child(5){border-left:0}.st-key-ayurform_dashboard .af-status-cell:nth-child(3){border-top:1px solid #D8DFD5}.st-key-ayurform_dashboard .af-status-cell:nth-child(4){border-top:1px solid #D8DFD5}.st-key-ayurform_dashboard .af-status-cell:nth-child(5){border-top:1px solid #D8DFD5}}
        /* Motion is confined to this dashboard; movement uses compositor-friendly transforms and opacity. */
        .st-key-ayurform_dashboard .st-key-dashboard_hero:before{content:"";position:absolute;z-index:0;inset:-18%;pointer-events:none;background:radial-gradient(ellipse at 74% 44%,rgba(61,151,111,.34),transparent 43%),radial-gradient(ellipse at 17% 85%,rgba(195,163,106,.13),transparent 38%);animation:af-light-drift 19s ease-in-out infinite alternate}
        .st-key-ayurform_dashboard .st-key-dashboard_hero:after{content:"";position:absolute;z-index:0;inset:-10%;pointer-events:none;background:radial-gradient(ellipse at 74% 42%,rgba(112,187,145,.18),transparent 34%);transform:translate3d(var(--af-light-x,0),var(--af-light-y,0),0);transition:transform 520ms cubic-bezier(.2,.72,.25,1)}
        .st-key-ayurform_dashboard .st-key-dashboard_hero .af-hero-art{position:relative;transform:translate3d(var(--af-art-x,0),var(--af-art-y,0),0);transition:transform 360ms cubic-bezier(.2,.72,.25,1);filter:drop-shadow(0 12px 20px rgba(0,0,0,.1))}
        .st-key-ayurform_dashboard .af-art-orbit{transform-box:view-box;transform-origin:260px 193px;animation:af-orbit 44s linear infinite}
        .st-key-ayurform_dashboard .af-art-orbit--inner{animation-duration:32s;animation-direction:reverse}
        .st-key-ayurform_dashboard .af-leaf-sway{transform-box:view-box;transform-origin:center;animation:af-leaf-sway 7.4s ease-in-out infinite alternate}
        .st-key-ayurform_dashboard .af-leaf-sway--two{animation-duration:8.2s;animation-direction:alternate-reverse}
        .st-key-ayurform_dashboard .af-leaf-sway--three{animation-duration:6.8s;animation-delay:-2.6s}
        .st-key-ayurform_dashboard .af-leaf-sway--four{animation-duration:9.1s;animation-delay:-4s}
        .st-key-ayurform_dashboard .af-art-connections{animation:af-dash-flow 13s linear infinite}
        .st-key-ayurform_dashboard .af-art-node,.st-key-ayurform_dashboard .af-ai-node{transform-box:fill-box;transform-origin:center;animation:af-node-pulse 4.2s ease-in-out infinite}
        .st-key-ayurform_dashboard .af-art-node--two,.st-key-ayurform_dashboard .af-ai-node--two,.st-key-ayurform_dashboard .af-ai-node--five{animation-delay:-1.1s}
        .st-key-ayurform_dashboard .af-art-node--three,.st-key-ayurform_dashboard .af-ai-node--three,.st-key-ayurform_dashboard .af-ai-node--six{animation-delay:-2.2s}
        .st-key-ayurform_dashboard .af-art-node--four,.st-key-ayurform_dashboard .af-ai-node--four{animation-delay:-3.1s}
        .st-key-ayurform_dashboard .af-art-particle{transform-box:fill-box;transform-origin:center;animation:af-particle-drift 6.5s ease-in-out infinite}
        .st-key-ayurform_dashboard .af-art-particle--two{animation-delay:-2.2s;animation-duration:7.6s}.st-key-ayurform_dashboard .af-art-particle--three{animation-delay:-4.1s;animation-duration:8s}
        .st-key-ayurform_dashboard .af-domain-card{transform-style:preserve-3d;transition:transform 260ms cubic-bezier(.2,.72,.25,1),box-shadow 260ms ease,border-color 260ms ease,background-color 260ms ease}
        .st-key-ayurform_dashboard .af-domain-card svg{transform-origin:75% 45%;transition:transform 420ms cubic-bezier(.2,.72,.25,1)}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya.af-card-hover .af-domain-card,.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation.af-card-hover .af-domain-card,.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana.af-card-hover .af-domain-card{transform:perspective(1100px) rotateX(var(--af-tilt-x,0deg)) rotateY(var(--af-tilt-y,0deg)) translateY(-3px);border-color:rgba(40,117,87,.58);box-shadow:0 18px 34px rgba(16,55,45,.13),0 0 0 1px rgba(195,163,106,.17)}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya.af-card-hover .af-domain-card svg{transform:translateY(-4px) rotate(-2deg)}.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation.af-card-hover .af-domain-card svg{transform:translateY(-4px) rotate(1.5deg)}.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana.af-card-hover .af-domain-card svg{transform:translateY(-4px) rotate(-1.5deg)}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya .stButton>button,.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation .stButton>button,.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana .stButton>button{transition:background-color 180ms ease,transform 180ms ease}
        .st-key-ayurform_dashboard .af-domain-action span:last-child{transition:transform 240ms cubic-bezier(.2,.72,.25,1)}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stForm"]{transition:border-color 220ms ease,box-shadow 220ms ease,transform 220ms ease}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stForm"]:focus-within{border-color:#8DB19A!important;box-shadow:0 0 0 3px rgba(169,191,169,.3),0 12px 28px rgba(0,0,0,.17)!important;transform:translateY(-1px)}
        .st-key-ayurform_dashboard .st-key-dashboard_hero_search [data-testid="stForm"]:focus-within .af-search-icon{color:#174C3C;transform:scale(1.08)}
        .st-key-ayurform_dashboard .af-search-icon{transition:color 220ms ease,transform 220ms cubic-bezier(.2,.72,.25,1)}
        .st-key-ayurform_dashboard .stButton>button{transition:transform 180ms cubic-bezier(.2,.72,.25,1),box-shadow 180ms ease,border-color 180ms ease,background-color 180ms ease}
        .st-key-ayurform_dashboard .stButton>button:hover{transform:translateY(-1px);box-shadow:0 6px 14px rgba(16,55,45,.09)}
        .st-key-ayurform_dashboard .stButton>button:active{transform:translateY(1px);box-shadow:0 1px 4px rgba(16,55,45,.1)}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya .stButton>button,.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation .stButton>button,.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana .stButton>button{box-shadow:none!important;transform:none!important}
        .st-key-ayurform_dashboard .st-key-dashboard_question_grid .stButton>button:hover{border-color:#78947A!important;background:#EDF3EC!important}
        .st-key-ayurform_dashboard .st-key-dashboard_ai_panel{position:relative;isolation:isolate}
        .st-key-ayurform_dashboard .st-key-dashboard_ai_panel [data-testid="stHorizontalBlock"]{position:relative;z-index:1}
        .st-key-ayurform_dashboard .st-key-dashboard_ai_panel .af-ai-visual{position:absolute;z-index:0;top:0;right:4%;width:min(235px,25%);opacity:.4;pointer-events:none}
        .st-key-ayurform_dashboard .af-ai-visual svg{display:block;width:100%;height:auto;overflow:visible}
        .st-key-ayurform_dashboard .af-ai-orbit{transform-box:view-box;transform-origin:120px 90px;animation:af-orbit 38s linear infinite}
        .st-key-ayurform_dashboard .af-ai-orbit--reverse{animation-duration:53s;animation-direction:reverse}
        .st-key-ayurform_dashboard .af-ai-link{animation:af-dash-flow 16s linear infinite}
        .st-key-ayurform_dashboard .af-kpi-icon{display:inline-block;transform-origin:center;transition:transform 240ms cubic-bezier(.2,.72,.25,1),color 240ms ease}
        .st-key-ayurform_dashboard .af-kpi:hover .af-kpi-icon{transform:translateY(-2px) rotate(-7deg);color:#287557}
        .st-key-ayurform_dashboard .af-status-dot.good,.st-key-ayurform_dashboard .af-ai-status.good i{box-shadow:0 0 0 0 rgba(40,117,87,.2);animation:af-status-breathe 3.4s ease-out infinite}
        .st-key-ayurform_dashboard .af-motion-ready .af-motion-reveal:not(.af-in-view),.st-key-ayurform_dashboard .af-motion-ready .af-motion-reveal-child:not(.af-in-view){opacity:0;transform:translate3d(0,16px,0)}
        .st-key-ayurform_dashboard .af-motion-reveal,.st-key-ayurform_dashboard .af-motion-reveal-child{transition:opacity 700ms cubic-bezier(.2,.72,.25,1),transform 700ms cubic-bezier(.2,.72,.25,1)}
        .st-key-ayurform_dashboard .af-initial-entrance .af-eyebrow{animation:af-entrance 620ms cubic-bezier(.2,.72,.25,1) both;animation-delay:70ms}
        .st-key-ayurform_dashboard .af-initial-entrance .af-hero-copy h1{animation:af-entrance 760ms cubic-bezier(.2,.72,.25,1) both;animation-delay:160ms}
        .st-key-ayurform_dashboard .af-initial-entrance .af-hero-copy p{animation:af-entrance 700ms cubic-bezier(.2,.72,.25,1) both;animation-delay:290ms}
        .st-key-ayurform_dashboard .af-initial-entrance .af-hero-search-label{animation:af-entrance 660ms cubic-bezier(.2,.72,.25,1) both;animation-delay:390ms}
        .st-key-ayurform_dashboard .af-initial-entrance .st-key-dashboard_hero_search{animation:af-entrance 700ms cubic-bezier(.2,.72,.25,1) both;animation-delay:470ms}
        .st-key-ayurform_dashboard .af-initial-entrance .af-hero-art-wrap{animation:af-art-arrive 900ms cubic-bezier(.2,.72,.25,1) both;animation-delay:210ms}
        .st-key-ayurform_dashboard .af-motion-ready .af-domain-card{transition:transform 260ms cubic-bezier(.2,.72,.25,1),box-shadow 260ms ease,border-color 260ms ease,opacity 700ms ease}
        .st-key-ayurform_dashboard.af-motion-managed .af-art-orbit,.st-key-ayurform_dashboard.af-motion-managed .af-leaf-sway,.st-key-ayurform_dashboard.af-motion-managed .af-art-connections,.st-key-ayurform_dashboard.af-motion-managed .af-art-node,.st-key-ayurform_dashboard.af-motion-managed .af-art-particle,.st-key-ayurform_dashboard.af-motion-managed .af-ai-orbit,.st-key-ayurform_dashboard.af-motion-managed .af-ai-link,.st-key-ayurform_dashboard.af-motion-managed .af-ai-node,.st-key-ayurform_dashboard.af-motion-managed .af-card-illustration path,.st-key-ayurform_dashboard.af-motion-managed .af-status-dot.good,.st-key-ayurform_dashboard.af-motion-managed .af-ai-status.good i{animation-play-state:paused}
        .st-key-ayurform_dashboard .st-key-dashboard_hero.af-motion-active .af-art-orbit,.st-key-ayurform_dashboard .st-key-dashboard_hero.af-motion-active .af-leaf-sway,.st-key-ayurform_dashboard .st-key-dashboard_hero.af-motion-active .af-art-connections,.st-key-ayurform_dashboard .st-key-dashboard_hero.af-motion-active .af-art-node,.st-key-ayurform_dashboard .st-key-dashboard_hero.af-motion-active .af-art-particle{animation-play-state:running}
        .st-key-ayurform_dashboard .st-key-dashboard_domain_dravya.af-motion-active .af-card-illustration--dravya path,.st-key-ayurform_dashboard .st-key-dashboard_domain_formulation.af-motion-active .af-card-illustration--formulation path,.st-key-ayurform_dashboard .st-key-dashboard_domain_anupana.af-motion-active .af-card-illustration--anupana path{animation-play-state:running}
        .st-key-ayurform_dashboard .st-key-dashboard_ai_panel.af-motion-active .af-ai-orbit,.st-key-ayurform_dashboard .st-key-dashboard_ai_panel.af-motion-active .af-ai-link,.st-key-ayurform_dashboard .st-key-dashboard_ai_panel.af-motion-active .af-ai-node,.st-key-ayurform_dashboard .st-key-dashboard_ai_panel.af-motion-active .af-ai-status.good i{animation-play-state:running}
        .st-key-ayurform_dashboard .af-status-band.af-motion-active .af-status-dot.good,.st-key-ayurform_dashboard .af-status-band.af-motion-active .af-ai-status.good i{animation-play-state:running}
        @keyframes af-entrance{from{opacity:0;transform:translate3d(0,15px,0);filter:blur(4px)}to{opacity:1;transform:translate3d(0,0,0);filter:blur(0)}}
        @keyframes af-art-arrive{from{opacity:0;transform:translate3d(0,13px,0) scale(.985);filter:blur(3px)}to{opacity:1;transform:translate3d(0,0,0) scale(1);filter:blur(0)}}
        @keyframes af-light-drift{from{transform:translate3d(-1.2%,0,0)}to{transform:translate3d(1.5%,1.2%,0)}}
        @keyframes af-orbit{to{transform:rotate(360deg)}}
        @keyframes af-leaf-sway{from{transform:rotate(-1.8deg) translateY(0)}to{transform:rotate(2.2deg) translateY(-2px)}}
        @keyframes af-vessel-glow{0%,100%{opacity:.78}50%{opacity:1}}
        @keyframes af-ripple-drift{from{opacity:.72}to{opacity:1}}
        @keyframes af-dash-flow{to{stroke-dashoffset:-42}}
        @keyframes af-node-pulse{0%,100%{opacity:.72;transform:scale(.92)}50%{opacity:1;transform:scale(1.13)}}
        @keyframes af-particle-drift{0%,100%{opacity:.35;transform:translate3d(0,2px,0)}50%{opacity:.9;transform:translate3d(0,-8px,0)}}
        @keyframes af-status-breathe{0%{box-shadow:0 0 0 0 rgba(40,117,87,.18)}65%{box-shadow:0 0 0 5px rgba(40,117,87,0)}100%{box-shadow:0 0 0 0 rgba(40,117,87,0)}}
        @media(max-width:800px){.st-key-ayurform_dashboard .st-key-dashboard_ai_panel .af-ai-visual{right:2%;width:min(175px,28%);opacity:.23}}
        @media(max-width:600px){.st-key-ayurform_dashboard .st-key-dashboard_ai_panel .af-ai-visual{top:auto;bottom:5%;right:1%;width:36%;opacity:.19}.st-key-ayurform_dashboard .af-domain-card svg{width:102px;height:78px}}
        @media(hover:none){.st-key-ayurform_dashboard .af-domain-card,.st-key-ayurform_dashboard .stButton>button{transition-duration:140ms}.st-key-ayurform_dashboard .stButton>button:hover{transform:none;box-shadow:none}}
        @media(prefers-reduced-motion:reduce){.st-key-ayurform_dashboard *, .st-key-ayurform_dashboard *:before,.st-key-ayurform_dashboard *:after{scroll-behavior:auto!important;animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important;filter:none!important}.st-key-ayurform_dashboard .af-motion-ready .af-motion-reveal:not(.af-in-view),.st-key-ayurform_dashboard .af-motion-ready .af-motion-reveal-child:not(.af-in-view){opacity:1;transform:none}}
        </style>"""
    )


def _motion_script() -> str:
    """Static, dashboard-scoped enhancements; no user or model text is embedded."""
    return """<script>
    (() => {
      const root = document.querySelector('.st-key-ayurform_dashboard');
      if (!root || root.dataset.afMotionInitialized === 'true') return;
      root.dataset.afMotionInitialized = 'true';

      const prefix = 'ayurform-dashboard-motion-v1:';
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const storageGet = (key) => { try { return window.sessionStorage.getItem(prefix + key); } catch (_) { return null; } };
      const storageSet = (key) => { try { window.sessionStorage.setItem(prefix + key, '1'); } catch (_) {} };
      let firstVisit = false;
      if (!window.__ayurformDashboardEntranceSeen) {
        firstVisit = storageGet('entrance') !== '1';
        storageSet('entrance');
        window.__ayurformDashboardEntranceSeen = true;
      }
      if (firstVisit && !reduced) {
        root.classList.add('af-initial-entrance');
        window.setTimeout(() => root.classList.remove('af-initial-entrance'), 1800);
      }
      if (reduced || !('IntersectionObserver' in window)) return;

      let revealObserver;
      let countObserver;
      const observed = new WeakSet();
      const counted = new WeakSet();
      const ambientObserved = new WeakSet();
      const revealItems = [
        ['.af-section-head', 'section-heading'],
        ['.af-kpi-band', 'knowledge-statistics'],
        ['.st-key-dashboard_domain_dravya .af-domain-card', 'domain-dravya'],
        ['.st-key-dashboard_domain_formulation .af-domain-card', 'domain-formulation'],
        ['.st-key-dashboard_domain_anupana .af-domain-card', 'domain-anupana'],
        ['.st-key-dashboard_ai_panel', 'research-assistant'],
        ['.st-key-dashboard_tools_grid', 'research-tools'],
        ['.af-status-band', 'system-status']
      ];

      const markReveal = (element, key, delay = 0) => {
        if (element.dataset.afRevealKey) return;
        element.dataset.afRevealKey = key;
        element.classList.add('af-motion-reveal');
        if (delay) element.style.transitionDelay = `${delay}ms`;
        if (storageGet(`seen:${key}`) === '1') {
          element.classList.add('af-in-view');
          return;
        }
        if (!observed.has(element)) {
          observed.add(element);
          revealObserver.observe(element);
        }
      };

      revealObserver = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add('af-in-view');
          storageSet(`seen:${entry.target.dataset.afRevealKey}`);
          revealObserver.unobserve(entry.target);
        }
      }, { threshold: 0.12, rootMargin: '0px 0px -32px 0px' });

      const countUp = (element) => {
        const target = Number(element.dataset.afCountTarget);
        const key = `count:${element.dataset.afCountKey}:${target}`;
        const finalText = Number.isFinite(target) ? target.toLocaleString() : element.textContent;
        if (!Number.isFinite(target) || storageGet(key) === '1' || target <= 0) {
          if (Number.isFinite(target)) element.textContent = finalText;
          storageSet(key);
          return;
        }
        storageSet(key); // Mark before animating so a Streamlit rerun cannot restart it.
        const started = performance.now();
        const duration = 680;
        const tick = (now) => {
          const progress = Math.min(1, (now - started) / duration);
          const eased = 1 - Math.pow(1 - progress, 3);
          element.textContent = Math.round(target * eased).toLocaleString();
          if (progress < 1) window.requestAnimationFrame(tick);
          else element.textContent = finalText;
        };
        window.requestAnimationFrame(tick);
      };

      countObserver = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          countUp(entry.target);
          countObserver.unobserve(entry.target);
        }
      }, { threshold: 0.35 });

      const ambientObserver = new IntersectionObserver((entries) => {
        for (const entry of entries) entry.target.classList.toggle('af-motion-active', entry.isIntersecting);
      }, { threshold: 0.01, rootMargin: '48px 0px' });

      const setAnimationPhase = (element) => {
        if (element.dataset.afPhaseSet === 'true') return;
        const duration = Number.parseFloat(window.getComputedStyle(element).animationDuration) * 1000;
        if (!Number.isFinite(duration) || duration <= 0) return;
        element.style.animationDelay = `-${(Date.now() % duration) / 1000}s`;
        element.dataset.afPhaseSet = 'true';
      };

      const scan = () => {
        if (!root.isConnected) return;
        root.classList.add('af-motion-ready');
        for (const [selector, key] of revealItems) {
          root.querySelectorAll(selector).forEach((element, index) => markReveal(element, `${key}:${index}`, index * 62));
        }
        root.querySelectorAll('.st-key-dashboard_question_grid [data-testid="stColumn"]').forEach((element, index) => markReveal(element, `question:${index}`, index * 68));
        root.querySelectorAll('.af-status-cell').forEach((element, index) => markReveal(element, `status-cell:${index}`, index * 48));
        root.querySelectorAll('.st-key-dashboard_hero,.st-key-dashboard_domain_dravya,.st-key-dashboard_domain_formulation,.st-key-dashboard_domain_anupana,.st-key-dashboard_ai_panel,.af-status-band').forEach((element) => {
          if (!ambientObserved.has(element)) {
            ambientObserved.add(element);
            ambientObserver.observe(element);
          }
        });
        root.querySelectorAll('.af-kpi-value[data-af-count-target]').forEach((element) => {
          if (!counted.has(element)) {
            counted.add(element);
            countObserver.observe(element);
          }
        });
        root.querySelectorAll('.af-art-orbit,.af-leaf-sway,.af-art-connections,.af-art-node,.af-art-particle,.af-ai-orbit,.af-ai-link,.af-ai-node,.af-card-illustration--dravya path:nth-of-type(2),.af-card-illustration--formulation path:nth-of-type(3),.af-card-illustration--anupana path:nth-of-type(2)').forEach(setAnimationPhase);
      };

      root.classList.add('af-motion-ready');
      root.classList.add('af-motion-managed');
      scan();
      let scanQueued = false;
      const mutationObserver = new MutationObserver(() => {
        if (scanQueued) return;
        scanQueued = true;
        window.requestAnimationFrame(() => { scanQueued = false; scan(); });
      });
      mutationObserver.observe(root, { childList: true, subtree: true });

      if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
        let activeCard = null;
        const resetCard = () => {
          if (!activeCard) return;
          activeCard.classList.remove('af-card-hover');
          const card = activeCard.querySelector('.af-domain-card');
          if (card) {
            card.style.removeProperty('--af-tilt-x');
            card.style.removeProperty('--af-tilt-y');
          }
          activeCard = null;
        };
        root.addEventListener('pointermove', (event) => {
          const hero = event.target.closest('.st-key-dashboard_hero');
          if (hero && root.contains(hero)) {
            const rect = hero.getBoundingClientRect();
            const x = Math.max(-1, Math.min(1, ((event.clientX - rect.left) / rect.width - 0.5) * 2));
            const y = Math.max(-1, Math.min(1, ((event.clientY - rect.top) / rect.height - 0.5) * 2));
            hero.style.setProperty('--af-light-x', `${x * 1.6}%`);
            hero.style.setProperty('--af-light-y', `${y * 1.4}%`);
            const art = hero.querySelector('.af-hero-art');
            if (art) {
              art.style.setProperty('--af-art-x', `${x * 6}px`);
              art.style.setProperty('--af-art-y', `${y * 5}px`);
            }
          } else {
            root.querySelectorAll('.st-key-dashboard_hero').forEach((element) => {
              element.style.removeProperty('--af-light-x');
              element.style.removeProperty('--af-light-y');
              const art = element.querySelector('.af-hero-art');
              if (art) { art.style.removeProperty('--af-art-x'); art.style.removeProperty('--af-art-y'); }
            });
          }

          const wrapper = event.target.closest('.st-key-dashboard_domain_dravya,.st-key-dashboard_domain_formulation,.st-key-dashboard_domain_anupana');
          if (!wrapper || !root.contains(wrapper)) { resetCard(); return; }
          if (activeCard !== wrapper) { resetCard(); activeCard = wrapper; }
          activeCard.classList.add('af-card-hover');
          const card = activeCard.querySelector('.af-domain-card');
          if (!card) return;
          const rect = card.getBoundingClientRect();
          const nx = Math.max(-1, Math.min(1, ((event.clientX - rect.left) / rect.width - 0.5) * 2));
          const ny = Math.max(-1, Math.min(1, ((event.clientY - rect.top) / rect.height - 0.5) * 2));
          card.style.setProperty('--af-tilt-x', `${-ny * 2.6}deg`);
          card.style.setProperty('--af-tilt-y', `${nx * 3.1}deg`);
        }, { passive: true });
        root.addEventListener('pointerleave', () => {
          resetCard();
          root.querySelectorAll('.st-key-dashboard_hero').forEach((element) => {
            element.style.removeProperty('--af-light-x');
            element.style.removeProperty('--af-light-y');
            const art = element.querySelector('.af-hero-art');
            if (art) { art.style.removeProperty('--af-art-x'); art.style.removeProperty('--af-art-y'); }
          });
        });
      }
    })();
    </script>"""


def _render_kpis(counts: dict[str, int | None]) -> None:
    structured = (
        ("◈", "Dravya records", counts["dravya"], "No approved records yet" if counts["dravya"] == 0 else "Approved records"),
        ("▦", "Formulations", counts["formulations"], "No approved records yet" if counts["formulations"] == 0 else "Approved records"),
        ("◌", "Anupana relationships", counts["anupana"], "No approved relationships yet" if counts["anupana"] == 0 else "Explicit approved links"),
    )
    corpus_detail = (
        "Collection unavailable"
        if counts["passages"] is None
        else ("Development-only corpus" if KNOWLEDGE_MODE == "development" else "Production collection")
    )
    corpus = (
        ("▤", "Indexed passages", counts["passages"], corpus_detail, KNOWLEDGE_MODE == "development"),
        ("⌂", "Registered sources", counts["sources"], "No production-cleared sources yet" if counts["sources"] == 0 else "Production-cleared sources", False),
    )

    def item(icon: str, label: str, value: int | None, detail: str, development: bool = False) -> str:
        tag = '<div class="af-dev-tag">Development-only · not production-approved</div>' if development else ""
        count_attributes = (
            f' data-af-count-target="{value}" data-af-count-key="{html.escape(label.casefold().replace(" ", "-"))}"'
            if value is not None
            else ""
        )
        return (
            '<article class="af-kpi">'
            f'<div class="af-kpi-label"><span class="af-kpi-icon" aria-hidden="true">{html.escape(icon)}</span>{html.escape(label)}</div>'
            f'<div class="af-kpi-value"{count_attributes}>{html.escape(_format_metric(value))}</div>'
            f'<div class="af-kpi-detail">{html.escape(detail)}</div>{tag}</article>'
        )

    markup = (
        '<section class="af-kpi-band" aria-label="Knowledge statistics">'
        '<div class="af-kpi-group af-kpi-structured">'
        + "".join(item(icon, label, value, detail) for icon, label, value, detail in structured)
        + '</div><div class="af-kpi-group af-kpi-corpus">'
        + "".join(item(icon, label, value, detail, dev) for icon, label, value, detail, dev in corpus)
        + "</div></section>"
    )
    st.markdown(markup, unsafe_allow_html=True)


def _render_status_band(
    *,
    model_state: str,
    model_detail: str,
    embedding_state: str,
    embedding_detail: str,
    snapshot: dict,
    passage_count: int | None,
    database_state: str,
    database_detail: str,
) -> None:
    scope = "Development-only" if KNOWLEDGE_MODE == "development" else "Production"
    scope_detail = (
        f"{ACTIVE_CHROMA_COLLECTION} · not production-approved"
        if KNOWLEDGE_MODE == "development"
        else f"{ACTIVE_CHROMA_COLLECTION} · production scope"
    )
    collection_state = "Connected" if snapshot.get("connected") else "Unavailable"
    collection_detail = (
        f"{passage_count:,} passages"
        if passage_count is not None
        else "Connection not confirmed"
    )
    entries = (
        ("AyurParam", model_state, model_detail, _tone(model_state)),
        ("BGE embeddings", embedding_state, f"{EMBEDDING_MODEL_NAME} · {embedding_detail}", _tone(embedding_state)),
        ("ChromaDB", collection_state, collection_detail, _tone(collection_state)),
        ("Knowledge scope", scope, scope_detail, "caution" if KNOWLEDGE_MODE == "development" else "good"),
        ("Structured database", database_state, database_detail, _tone(database_state)),
    )
    cells = "".join(
        '<div class="af-status-cell">'
        f'<div class="af-status-top"><span class="af-status-dot {tone}" aria-hidden="true"></span>{html.escape(title)} · {html.escape(status)}</div>'
        f'<div class="af-status-detail">{html.escape(detail)}</div></div>'
        for title, status, detail, tone in entries
    )
    st.markdown(f'<section class="af-status-band" aria-label="Live system status">{cells}</section>', unsafe_allow_html=True)


def render_dashboard(user: dict | None = None) -> None:
    snapshot = _snapshot()
    model_state = _model_status()
    embedding_state, embedding_detail = _embedding_status()
    database_state, database_detail = _database_status()
    counts: dict[str, int | None] = {
        "dravya": _count("dravya"),
        "formulations": _count("formulations"),
        "anupana": _count("anupana_relationships"),
        "passages": int(snapshot.get("passages", 0)) if snapshot.get("connected") else None,
        "sources": _count("sources"),
    }
    admin = is_admin_email((user or {}).get("email"))
    status_model_detail = f"{OLLAMA_MODEL} · Ollama" if (LLM_MODE or LLM_PROVIDER or "mock") == "ollama" else f"Provider: {LLM_MODE or LLM_PROVIDER or 'mock'} · AyurParam not available"
    embedding_detail = f"{embedding_detail}"

    with st.container(key="ayurform_dashboard"):
        _styles()
        with st.container(key="dashboard_hero"):
            left, right = st.columns([1.2, .8], gap="large")
            with left:
                st.markdown(
                    '<div class="af-hero-copy"><div class="af-eyebrow">AYURFORM AI · RESEARCH WORKSPACE</div>'
                    '<h1>Ancient Wisdom.<br>Evidence-Led Discovery.</h1>'
                    '<p>Explore classical Dravya, formulations and documented Anupana through a research workspace designed around traceable evidence.</p></div>',
                    unsafe_allow_html=True,
                )
                st.markdown('<div class="af-hero-search-label">What would you like to explore today?</div>', unsafe_allow_html=True)
                with st.container(key="dashboard_hero_search"):
                    with st.form("dashboard_research_form", clear_on_submit=False):
                        icon_col, input_col, action_col = st.columns([.35, 4.5, 1.45], gap="small")
                        with icon_col:
                            st.markdown('<div class="af-search-icon" aria-hidden="true">⌕</div>', unsafe_allow_html=True)
                        with input_col:
                            query = st.text_input(
                                "What would you like to explore today?",
                                key="dashboard_research_query",
                                placeholder="What would you like to explore today?",
                                label_visibility="collapsed",
                            )
                        with action_col:
                            submitted = st.form_submit_button("Start Research →", type="primary", use_container_width=True)
                if submitted:
                    if not query.strip():
                        st.error("Enter a research question to continue.")
                    else:
                        _set_research_query(query)
            with right:
                st.markdown(f'<div class="af-hero-art-wrap">{_hero_art()}</div>', unsafe_allow_html=True)

        st.markdown(
            '<div class="af-section-head"><h2>Knowledge at a glance</h2><p>Approved records and the active passage collection</p></div>',
            unsafe_allow_html=True,
        )
        _render_kpis(counts)

        st.markdown(
            '<div class="af-section-head"><h2>Explore the knowledge domains</h2><p>Open a focused research workspace</p></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="dashboard_domain_grid",):
            columns = st.columns(3, gap="medium")
            for column, (kind, title, description, page, action) in zip(columns, _DOMAINS):
                with column:
                    with st.container(key=f"dashboard_domain_{kind}"):
                        st.markdown(
                            f'<article class="af-domain-card {kind}">{_domain_art(kind)}'
                            f'<h3>{html.escape(title)}</h3><p>{html.escape(description)}</p>'
                            f'<div class="af-domain-action"><span>{html.escape(action)}</span><span aria-hidden="true">→</span></div></article>',
                            unsafe_allow_html=True,
                        )
                        if st.button(f"Open {title}", key=f"dashboard_domain_open_{kind}", use_container_width=True):
                            _go(page)

        st.markdown(
            '<div class="af-section-head"><h2>Research deeper with AI</h2><p>Classical literature exploration with retrieval-augmented generation</p></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="dashboard_ai_panel"):
            st.markdown(_research_art(), unsafe_allow_html=True)
            ai_left, ai_right = st.columns([1, 1], gap="large")
            with ai_left:
                st.markdown(
                    '<div class="af-ai-kicker">AYURPARAM RESEARCH ASSISTANT</div>'
                    '<h2>Ask a careful question.<br>Follow the evidence.</h2>'
                    '<p>Explore classical literature through retrieval-augmented generation and AyurParam. Answers depend on eligible retrieved passages and may abstain when evidence is limited.</p>',
                    unsafe_allow_html=True,
                )
                model_tone = _tone(model_state)
                embedding_tone = _tone(embedding_state)
                st.markdown(
                    f'<div class="af-ai-statuses"><span class="af-ai-status {model_tone}"><i></i>AyurParam · {html.escape(model_state)}</span>'
                    f'<span class="af-ai-status {embedding_tone}"><i></i>BGE · {html.escape(embedding_state)}</span></div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"{OLLAMA_MODEL if (LLM_MODE or LLM_PROVIDER or 'mock') == 'ollama' else 'Configured model'} · {EMBEDDING_MODEL_NAME}")
                if st.button("Open Research Assistant", key="dashboard_open_research_assistant", type="primary", use_container_width=True):
                    _go("Research Assistant")
            with ai_right:
                st.markdown('<div class="af-question-heading">Suggested questions · corpus coverage is not implied</div>', unsafe_allow_html=True)
                with st.container(key="dashboard_question_grid"):
                    for row_start in range(0, len(RESEARCH_SUGGESTIONS), 2):
                        question_columns = st.columns(2, gap="small")
                        for col, suggestion in zip(question_columns, RESEARCH_SUGGESTIONS[row_start : row_start + 2]):
                            with col:
                                if st.button(suggestion, key=f"dashboard_suggestion_{RESEARCH_SUGGESTIONS.index(suggestion)}", use_container_width=True):
                                    _set_research_query(suggestion)

        st.markdown(
            '<div class="af-section-head"><h2>Classical sources &amp; research tools</h2><p>Browse, save and review knowledge records</p></div>',
            unsafe_allow_html=True,
        )
        tools = [
            ("Classical Sources", "Inspect source records, rights status and passage provenance.", "Browse sources"),
            ("Research Library", "Return to saved research references and materials.", "Open library"),
        ]
        if admin:
            tools.append(("Review Dashboard", "Review evidence-backed submissions and record decisions.", "Open review queue"))
        with st.container(key="dashboard_tools_grid"):
            tool_columns = st.columns(len(tools), gap="small")
            for col, (title, description, action) in zip(tool_columns, tools):
                with col:
                    st.markdown(
                        f'<article class="af-tool"><h3>{html.escape(title)}</h3><p>{html.escape(description)}</p></article>',
                        unsafe_allow_html=True,
                    )
                    if st.button(action, key=f"dashboard_tool_{title}", use_container_width=True):
                        _go(title)

        st.markdown(
            '<div class="af-section-head"><h2>System status</h2><p>Current model, data and rights scope</p></div>',
            unsafe_allow_html=True,
        )
        _render_status_band(
            model_state=model_state,
            model_detail=status_model_detail,
            embedding_state=embedding_state,
            embedding_detail=embedding_detail,
            snapshot=snapshot,
            passage_count=counts["passages"],
            database_state=database_state,
            database_detail=database_detail,
        )
        st.html(_motion_script(), unsafe_allow_javascript=True)
        st.markdown(
            '<div class="af-footer">Academic research and knowledge exploration only. AI-generated material is not automatically verified. This platform does not provide diagnosis, prescriptions or dosage advice.</div>',
            unsafe_allow_html=True,
        )
