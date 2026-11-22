"""Phase 2 dashboard, backed by local application data."""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from chromadb import PersistentClient

from config import ACTIVE_CHROMA_COLLECTION, ACTIVE_VECTORSTORE_DIR, CHROMA_COLLECTION, EMBEDDING_MODEL_NAME, LLM_MODE, LLM_MODEL_NAME, LLM_PROVIDER, METADATA_DIR, VECTORSTORE_DIR, KNOWLEDGE_MODE


@st.cache_data(ttl=30, show_spinner=False)
def _snapshot() -> dict:
    result = {"connected": False, "passages": 0, "sources": [], "chapters": 0, "error": None}
    try:
        client = PersistentClient(path=str(ACTIVE_VECTORSTORE_DIR))
        client.heartbeat()
        collection = client.get_collection(ACTIVE_CHROMA_COLLECTION)
        result["connected"] = True
        result["passages"] = collection.count()
        if result["passages"]:
            records = collection.get(include=["metadatas"])
            grouped = {}
            for metadata in records.get("metadatas", []):
                metadata = metadata or {}
                source_id = metadata.get("source_id") or metadata.get("source_title") or metadata.get("book_name") or "Source details unavailable"
                item = grouped.setdefault(source_id, {"passages": 0, "chapters": set(), "title": metadata.get("source_title") or metadata.get("book_name") or "Classical source", "edition": metadata.get("edition") or "Edition not recorded", "translator": metadata.get("translator") or "Translator not recorded"})
                item["passages"] += 1
                chapter = metadata.get("chapter_title") or metadata.get("chapter_number")
                if chapter:
                    item["chapters"].add(str(chapter))
            result["sources"] = [{**v, "chapters": sorted(v["chapters"])} for v in grouped.values()]
            result["chapters"] = len({ch for source in result["sources"] for ch in source["chapters"]})
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _embedding_status() -> tuple[str, str]:
    cache_root = Path(os.getenv("HF_HUB_CACHE", Path.home() / ".cache" / "huggingface" / "hub"))
    repo_dir = cache_root / ("models--" + EMBEDDING_MODEL_NAME.replace("/", "--"))
    return ("Available", "Embedding weights found in local cache") if repo_dir.exists() else ("Configured", "Weights download on first retrieval")


def _model_status() -> tuple[str, str]:
    provider = LLM_MODE or LLM_PROVIDER or "mock"
    if provider == "mock":
        return "Mock mode", "AyurParam generation is disabled in development settings"
    if provider == "ollama":
        return "Ollama connected", "Local Ollama provider configured"
    cache_root = Path(os.getenv("HF_HUB_CACHE", Path.home() / ".cache" / "huggingface" / "hub"))
    repo_dir = cache_root / ("models--" + LLM_MODEL_NAME.replace("/", "--"))
    return ("Weights cached", "Official model configured") if repo_dir.exists() else ("Configured", "Official checkpoint will load when evidence is available")


def _source_records(snapshot: dict) -> list[dict]:
    records = snapshot["sources"]
    if records or not METADATA_DIR.exists():
        return records
    # Provenance can exist before a corpus has been embedded; do not imply it is searchable.
    return []


def _go(page: str) -> None:
    st.session_state["page"] = page
    st.rerun()


def _stat_card(icon: str, label: str, value: str | int, detail: str, tone: str) -> None:
    st.markdown(f"""<div class="dash-stat {tone}"><div class="dash-stat-top"><span class="dash-icon">{icon}</span><span>{label}</span></div><div class="dash-value">{value}</div><div class="dash-detail">{detail}</div></div>""", unsafe_allow_html=True)


def render_dashboard() -> None:
    st.html("""<style>
[data-testid="stMainBlockContainer"]{width:100%!important;max-width:none!important;padding-left:clamp(1rem,2.3vw,2rem)!important;padding-right:clamp(1rem,2.3vw,2rem)!important}
.dash-top{display:flex;justify-content:space-between;align-items:flex-end;gap:1.25rem;margin-bottom:1.35rem}.dash-top>div:first-child{min-width:0;flex:1}.dash-top .shell-desc{max-width:none}.dash-date{flex:0 0 auto;color:#64736A;font-size:.84rem;text-align:right}.dash-model-pill{display:inline-flex;align-items:center;gap:.45rem;background:#EDF3EC;border:1px solid #E3E9E2;padding:.42rem .7rem;border-radius:999px;color:#174C3C;font-size:.78rem;font-weight:600;margin-top:.4rem}
.st-key-dashboard_hero{border-radius:20px!important;padding:clamp(1rem,2vw,1.55rem)!important;margin-bottom:1.25rem;background:linear-gradient(115deg,#fff 0%,#fff 58%,#F5F8F2 100%)!important;box-shadow:0 8px 24px rgba(16,55,45,.055)}
.st-key-dashboard_hero_grid [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1.42fr) minmax(280px,.98fr);align-items:center;gap:clamp(1rem,2.4vw,2rem)!important}
.st-key-dashboard_hero_grid [data-testid="stColumn"]{width:auto!important;min-width:0!important;flex:initial!important}
.st-key-dashboard_hero h2{font-size:clamp(2rem,3.2vw,2.75rem)!important;line-height:1.08!important;font-family:'Playfair Display',serif!important;font-weight:600!important;color:#10372D!important;max-width:none!important;margin:.65rem 0 .8rem!important;overflow-wrap:normal}
.st-key-dashboard_hero h2 [data-testid="stHeaderActionElements"]{display:none!important}
.st-key-dashboard_hero p{max-width:none!important;color:#64736A!important;font-size:1rem!important;line-height:1.6!important;margin:.35rem 0 1rem!important}
.dash-art{width:108%!important;max-width:560px!important;max-height:400px;height:auto;object-fit:contain;display:block;margin:auto}
.st-key-dashboard_hero_actions [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px!important;align-items:stretch}
.st-key-dashboard_hero_actions [data-testid="stColumn"]{flex:initial!important;min-width:0!important;width:auto!important}
.st-key-dashboard_hero_actions .stButton,.st-key-dashboard_hero_actions .stButton>button{width:100%!important;min-width:0!important}
.st-key-dashboard_hero_actions .stButton>button{min-height:48px!important;padding:.65rem .95rem!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
.st-key-dashboard_hero_actions .stButton>button p{max-width:none!important;margin:0!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.3!important}
.dash-stat{height:100%;min-height:142px;border:1px solid #E3E9E2;border-radius:15px;background:#fff;padding:1.05rem 1.1rem;box-shadow:0 4px 14px rgba(16,55,45,.035)}
.dash-stat-top{display:flex;align-items:center;gap:.6rem;color:#64736A;font-size:.8rem;font-weight:600;white-space:nowrap}.dash-icon{flex:0 0 30px;height:30px;width:30px;border-radius:9px;background:#EDF3EC;display:grid;place-items:center;color:#174C3C;font-size:1rem}.dash-value{font-size:1.6rem;font-weight:700;letter-spacing:-.04em;color:#10372D;margin:.58rem 0 .08rem}.dash-detail{font-size:.75rem;color:#64736A;line-height:1.45}
.st-key-dashboard_stats [data-testid="stHorizontalBlock"],.st-key-dashboard_actions [data-testid="stHorizontalBlock"],.st-key-dashboard_process [data-testid="stHorizontalBlock"],.st-key-dashboard_health [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px!important}
.st-key-dashboard_actions [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(3,minmax(0,1fr))}.st-key-dashboard_process [data-testid="stHorizontalBlock"]{gap:12px!important}
.st-key-dashboard_stats [data-testid="stColumn"],.st-key-dashboard_actions [data-testid="stColumn"],.st-key-dashboard_process [data-testid="stColumn"],.st-key-dashboard_health [data-testid="stColumn"],.st-key-dashboard_activity [data-testid="stColumn"]{width:auto!important;min-width:0!important;flex:initial!important}
.dash-section{font:600 1.3rem 'Playfair Display',serif;color:#10372D;margin:.4rem 0 .8rem}.dash-action{height:100%;background:#fff;border:1px solid #E3E9E2;border-radius:15px;padding:1rem;transition:transform .16s,border-color .16s,box-shadow .16s}.dash-action:hover{transform:translateY(-2px);border-color:#A9BFA9;box-shadow:0 8px 20px rgba(16,55,45,.07)}.dash-action-kicker{font-size:.72rem;color:#287557;font-weight:700;letter-spacing:.08em;text-transform:uppercase}.dash-action h3{font:600 1.08rem 'DM Sans',sans-serif!important;margin:.45rem 0 .25rem;color:#10372D!important}.dash-action p{font-size:.82rem;color:#64736A!important;min-height:42px}.dash-process{height:100%;border-top:2px solid #A9BFA9;border-radius:2px 2px 14px 14px;background:#fff;padding:.85rem .9rem;border-left:1px solid #E3E9E2;border-right:1px solid #E3E9E2;border-bottom:1px solid #E3E9E2}.dash-process-num{color:#287557;font-size:.74rem;font-weight:700;letter-spacing:.08em}.dash-process h3{font:600 1rem 'DM Sans',sans-serif!important;color:#10372D!important;margin:.4rem 0}.dash-process p{font-size:.78rem;color:#64736A!important;margin-bottom:0}.dash-source{border:1px solid #E3E9E2;border-radius:14px;background:#fff;padding:1rem;margin:.45rem 0}.dash-activity{border-bottom:1px solid #E3E9E2;padding:.8rem 0}.dash-health{border:1px solid #E3E9E2;border-radius:13px;background:#fff;padding:.8rem .9rem;height:100%}.dash-health strong{color:#1D2E26}.dash-health small{color:#64736A;line-height:1.45}.dash-disclaimer{border-top:1px solid #E3E9E2;padding:1rem 0;color:#64736A;font-size:.78rem;margin-top:1rem}
@media(max-width:1100px){.st-key-dashboard_stats [data-testid="stHorizontalBlock"],.st-key-dashboard_process [data-testid="stHorizontalBlock"],.st-key-dashboard_health [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(2,minmax(0,1fr))}.st-key-dashboard_actions [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(2,minmax(0,1fr))}.dash-stat{min-height:128px}}
@media(max-width:900px){.st-key-dashboard_hero_grid [data-testid="stHorizontalBlock"]{grid-template-columns:minmax(0,1fr)}.st-key-dashboard_hero_grid .dash-art{width:100%!important;max-width:460px!important;max-height:300px}.st-key-dashboard_hero_grid [data-testid="stColumn"]:last-child{display:flex;justify-content:center}.dash-date{text-align:left}}
@media(max-width:640px){[data-testid="stMainBlockContainer"]{padding-left:1rem!important;padding-right:1rem!important}.dash-top{align-items:flex-start;flex-direction:column;gap:.45rem}.dash-date{text-align:left}.st-key-dashboard_hero{padding:1rem!important}.st-key-dashboard_hero h2{font-size:clamp(1.9rem,8vw,2.2rem)!important;line-height:1.08!important}.st-key-dashboard_hero_actions [data-testid="stHorizontalBlock"]{grid-template-columns:minmax(0,1fr)!important}.st-key-dashboard_stats [data-testid="stHorizontalBlock"],.st-key-dashboard_actions [data-testid="stHorizontalBlock"],.st-key-dashboard_process [data-testid="stHorizontalBlock"],.st-key-dashboard_health [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px!important}.dash-stat{min-height:120px;padding:.8rem}.dash-stat-top{font-size:.72rem;gap:.4rem}.dash-icon{flex-basis:26px;width:26px;height:26px}.dash-value{font-size:1.35rem}.dash-art{max-width:100%!important;max-height:260px!important}.dash-action{padding:.8rem}.dash-action p{min-height:0}.st-key-dashboard_activity [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:0!important}}
@media(max-width:370px){.st-key-dashboard_stats [data-testid="stHorizontalBlock"],.st-key-dashboard_health [data-testid="stHorizontalBlock"]{grid-template-columns:minmax(0,1fr)}.st-key-dashboard_stats .dash-stat-top{font-size:.8rem}}
</style>""")

    snapshot = _snapshot()
    model_state, model_detail = _model_status()
    embedding_state, embedding_detail = _embedding_status()
    today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%A, %d %B %Y")

    st.markdown(f"""<div class="dash-top"><div><h1 style="margin:.25rem 0">Welcome to AyurForm AI</h1><div class="shell-desc">Explore source-grounded Ayurvedic knowledge about Dravya, formulations and documented relationships.</div></div><div class="dash-date">{today}<br><span class="dash-model-pill">● {model_state}</span></div></div>""", unsafe_allow_html=True)

    art_path = Path(__file__).resolve().parents[1] / "assets" / "dashboard_illustration.svg"
    art_data = base64.b64encode(art_path.read_bytes()).decode("ascii") if art_path.exists() else ""
    with st.container(border=True, key="dashboard_hero"):
        with st.container(key="dashboard_hero_grid"):
            left, right = st.columns([1.42, .98], gap="medium", vertical_alignment="center")
            with left:
                st.markdown("<div style='color:#174C3C;font-size:.7rem;font-weight:700;letter-spacing:.14em'>AYURVEDIC KNOWLEDGE · SOURCE GROUNDED RESEARCH</div><h2>Explore the knowledge of Ayurveda.</h2><p>Research classical substances, formulations and documented relationships through traceable source evidence.</p>", unsafe_allow_html=True)
                with st.container(key="dashboard_hero_actions"):
                    cta_a, cta_b = st.columns([1.05, 1])
                    with cta_a:
                        if st.button("Open Research Assistant", type="primary", use_container_width=True, key="dash_start_analysis"):
                            _go("Research Assistant")
                    with cta_b:
                        if st.button("Explore Classical Library", use_container_width=True, key="dash_open_library"):
                            _go("Classical Library")
            with right:
                if art_data:
                    st.markdown(f'<img class="dash-art" src="data:image/svg+xml;base64,{art_data}" alt="Illustration combining a botanical branch, an open classical manuscript and connected knowledge nodes">', unsafe_allow_html=True)
    st.markdown('<div class="dash-section">System overview</div>', unsafe_allow_html=True)
    source_count = len(snapshot["sources"])
    with st.container(key="dashboard_stats"):
        stats = st.columns(4, gap="medium")
        with stats[0]: _stat_card("▤", "Indexed passages", f"{snapshot['passages']:,}", "ChromaDB collection", "tone-sage")
        with stats[1]: _stat_card("◫", "Classical sources", source_count, "Sources in indexed collection", "tone-paper")
        with stats[2]: _stat_card("✦", "AI model", model_state, model_detail, "tone-green")
        with stats[3]: _stat_card("◷", "Analyses", "—", "History available after data isolation", "tone-gold")

    st.markdown('<div class="dash-section" style="margin-top:1.15rem">Explore AyurForm</div>', unsafe_allow_html=True)
    with st.container(key="dashboard_actions"):
        actions = st.columns(3, gap="medium")
        for col, number, title, description, target in [
            (actions[0], "01", "Research Assistant", "Ask source-grounded academic questions.", "Research Assistant"),
            (actions[1], "02", "Classical Library", "Explore indexed classical passages.", "Classical Library"),
            (actions[2], "03", "Terminology Explorer", "Discover verified Ayurvedic terminology.", "Terminology Explorer"),
        ]:
            with col:
                st.markdown(f'<div class="dash-action"><div class="dash-action-kicker">Quick action · {number}</div><h3>{title}</h3><p>{description}</p></div>', unsafe_allow_html=True)
                if st.button(f"Open {title}", key=f"dash_action_{number}", use_container_width=True):
                    _go(target)

    st.markdown('<div class="dash-section" style="margin-top:1.2rem">How AyurForm research works</div>', unsafe_allow_html=True)
    with st.container(key="dashboard_process"):
        process = st.columns(4, gap="small")
        for col, num, title, text in zip(process, ["01", "02", "03", "04"], ["Describe", "Understand", "Retrieve", "Explain"], ["Share symptoms naturally.", "Identify relevant symptom concepts.", "Find supporting passages through RAG.", "Generate context-grounded explanations." ]):
            with col: st.markdown(f'<div class="dash-process"><div class="dash-process-num">{num} — PROCESS</div><h3>{title}</h3><p>{text}</p></div>', unsafe_allow_html=True)

    with st.container(key="dashboard_activity"):
        left, right = st.columns([1.05, .95], gap="large")
        with left:
            st.markdown('<div class="dash-section" style="margin-top:1.2rem">Recent activity</div>', unsafe_allow_html=True)
            st.markdown('<div class="dash-source"><b>History is temporarily private</b><p class="muted">Saved analysis history will return after records are assigned to individual accounts.</p></div>', unsafe_allow_html=True)
            if st.button("Start an analysis", key="dash_empty_start", type="primary"):
                _go("Research Assistant")

        with right:
            st.markdown('<div class="dash-section" style="margin-top:1.2rem">Featured classical knowledge</div>', unsafe_allow_html=True)
            if snapshot["sources"]:
                for source in snapshot["sources"][:3]:
                    chapters = ", ".join(source["chapters"][:4]) if source["chapters"] else "Chapter details unavailable"
                    st.markdown(f'<div class="dash-source"><b>{source["title"]}</b><br><small>{source["edition"]} · {source["translator"]}</small><p class="muted">{source["passages"]:,} indexed passages · {chapters}</p></div>', unsafe_allow_html=True)
                    if st.button("Explore source", key=f"source_{source['title']}"):
                        _go("Classical Library")
            else:
                st.markdown('<div class="dash-source"><b>Knowledge base not populated</b><p class="muted">No classical passages are currently indexed. Add an authorized source PDF and complete ingestion to feature its verified source details here.</p></div>', unsafe_allow_html=True)

    st.markdown('<div class="dash-section" style="margin-top:1.2rem">System status</div>', unsafe_allow_html=True)
    statuses = [
        ("AyurParam", model_state, model_detail),
        ("Embedding model", embedding_state, embedding_detail),
        ("ChromaDB", "Connected" if snapshot["connected"] else "Unavailable", "Local persistent vector store"),
        ("Knowledge base", "Populated" if snapshot["passages"] else "Empty", f"{snapshot['passages']:,} passages indexed"),
    ]
    with st.container(key="dashboard_health"):
        health = st.columns(4)
        for col, (label, status, detail) in zip(health, statuses):
            with col: st.markdown(f'<div class="dash-health"><strong>{label}</strong><br><small>{status}<br>{detail}</small></div>', unsafe_allow_html=True)

    st.markdown('<div class="dash-disclaimer">AyurForm AI supports academic exploration of source-backed Ayurvedic knowledge. It does not provide diagnosis, prescriptions or dosage advice.</div>', unsafe_allow_html=True)
