"""Sidebar navigation, access-aware page groups, and live system status."""
from __future__ import annotations

from html import escape
import os
import re

import httpx
import streamlit as st
from chromadb import PersistentClient

from config import (
    ACTIVE_CHROMA_COLLECTION,
    ACTIVE_VECTORSTORE_DIR,
    KNOWLEDGE_MODE,
    LLM_MODE,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

PAGES = [
    "Dashboard",
    "Dravya Explorer",
    "Formulation Explorer",
    "Anupana Explorer",
    "Research Assistant",
    "Classical Sources",
    "Review Dashboard",
    "Research Library",
    "About",
    "Settings",
    "Profile",
]

SIDEBAR_GROUPS: dict[str, tuple[str, ...]] = {
    "Workspace": ("Dashboard",),
    "Explore Knowledge": (
        "Dravya Explorer",
        "Formulation Explorer",
        "Anupana Explorer",
    ),
    "Research": ("Research Assistant", "Classical Sources", "Research Library"),
    "Management": ("Review Dashboard", "Settings", "About"),
}
SIDEBAR_PAGES = tuple(page for group in SIDEBAR_GROUPS.values() for page in group)

PAGE_ICONS = {
    "Dashboard": ":material/dashboard:",
    "Classical Library": ":material/menu_book:",
    "Terminology Explorer": ":material/translate:",
    "Research Library": ":material/bookmark:",
    "About": ":material/info:",
    "Settings": ":material/settings:",
    "Profile": ":material/account_circle:",
    "Dravya Explorer": ":material/spa:",
    "Formulation Explorer": ":material/medication:",
    "Anupana Explorer": ":material/water_drop:",
    "Research Assistant": ":material/auto_awesome:",
    "Classical Sources": ":material/menu_book:",
    "Review Dashboard": ":material/fact_check:",
}


def _configured_admin_emails() -> set[str]:
    return {
        value.strip().casefold()
        for value in os.getenv("AYURFORM_ADMIN_EMAILS", "").split(",")
        if value.strip()
    }


def is_admin_user(user: dict | None) -> bool:
    """Mirror the API/review-page allowlist when deciding whether to show review navigation."""
    email = user.get("email", "") if isinstance(user, dict) else ""
    return bool(email and str(email).strip().casefold() in _configured_admin_emails())


def visible_sidebar_pages(user: dict | None = None) -> tuple[str, ...]:
    """Return sidebar destinations visible to this signed-in user."""
    if is_admin_user(user):
        return SIDEBAR_PAGES
    return tuple(page for page in SIDEBAR_PAGES if page != "Review Dashboard")


def normalize_page(value: str | None, pages=None) -> str:
    """Return a visible registered sidebar page, falling back after stale sessions."""
    allowed = tuple(pages) if pages is not None else SIDEBAR_PAGES
    return value if value in allowed else "Dashboard"


def knowledge_status() -> tuple[bool, int]:
    """Return a live status for the configured knowledge collection."""
    try:
        client = PersistentClient(path=str(ACTIVE_VECTORSTORE_DIR))
        client.heartbeat()
        return True, client.get_collection(ACTIVE_CHROMA_COLLECTION).count()
    except Exception:
        return False, 0


@st.cache_data(ttl=20, show_spinner=False)
def model_status() -> dict[str, str | bool]:
    """Check the configured Ollama model without generating or exposing errors."""
    provider = (LLM_MODE or LLM_PROVIDER or "mock").strip().casefold()
    if provider == "mock":
        return {
            "provider": provider,
            "model": OLLAMA_MODEL,
            "state": "mock",
            "label": "Mock mode active",
            "available": False,
        }
    if provider != "ollama":
        return {
            "provider": provider,
            "model": OLLAMA_MODEL,
            "state": "unknown",
            "label": f"{provider.title()} · availability unverified",
            "available": False,
        }

    try:
        response = httpx.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=httpx.Timeout(2.0, connect=1.0, pool=1.0),
        )
        response.raise_for_status()
        payload = response.json()
        available_names = {
            str(item.get("name") or item.get("model") or "")
            for item in payload.get("models", [])
            if isinstance(item, dict)
        }
        if OLLAMA_MODEL in available_names:
            return {
                "provider": provider,
                "model": OLLAMA_MODEL,
                "state": "available",
                "label": "AyurParam available",
                "available": True,
            }
        return {
            "provider": provider,
            "model": OLLAMA_MODEL,
            "state": "missing",
            "label": "Configured model not found in Ollama",
            "available": False,
        }
    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
        return {
            "provider": provider,
            "model": OLLAMA_MODEL,
            "state": "unavailable",
            "label": "Ollama unavailable",
            "available": False,
        }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _sidebar_styles(animate_entrance: bool) -> None:
    entrance_rules = ""
    if animate_entrance:
        ordered_pages = [page for group in SIDEBAR_GROUPS.values() for page in group]
        item_rules = "\n".join(
            f".st-key-ayur_nav_item_{_slug(page)}{{animation:sidebar-nav-enter .42s cubic-bezier(.2,.75,.25,1) both;animation-delay:{.045 + index * .035:.3f}s}}"
            for index, page in enumerate(ordered_pages)
        )
        group_rules = "\n".join(
            f".st-key-ayur_nav_group_{_slug(group)} .ayur-sidebar-group{{animation:sidebar-group-enter .38s ease-out both;animation-delay:{.025 + index * .075:.3f}s}}"
            for index, group in enumerate(SIDEBAR_GROUPS)
        )
        entrance_rules = f"{group_rules}\n{item_rules}"

    icon_motion = {
        "Dashboard": "translateY(-2px)",
        "Dravya Explorer": "rotate(-8deg)",
        "Formulation Explorer": "translateY(-2px) rotate(-5deg)",
        "Anupana Explorer": "translateY(-2px)",
        "Research Assistant": "scale(1.08) rotate(4deg)",
        "Classical Sources": "translateY(-2px) rotate(-4deg)",
        "Research Library": "rotate(-9deg)",
        "Review Dashboard": "scale(1.06)",
        "Settings": "rotate(24deg)",
        "About": "translateY(-2px)",
    }
    icon_rules = "\n".join(
        f".st-key-ayur_nav_item_{_slug(page)} .stButton>button:hover [data-testid=\"stIconMaterial\"]{{transform:{transform}}}"
        for page, transform in icon_motion.items()
    )

    st.html(
        f"""<style>
@keyframes sidebar-light-breathe {{
  0%,100% {{ opacity:.48; }}
  50% {{ opacity:.78; }}
}}
@keyframes sidebar-leaf-sway {{ 0%,100% {{ transform:rotate(-3deg) }} 50% {{ transform:rotate(3deg) }} }}
@keyframes sidebar-nav-enter {{ from {{ opacity:0;transform:translateY(7px) }} to {{ opacity:1;transform:translateY(0) }} }}
@keyframes sidebar-group-enter {{ from {{ opacity:0;transform:translateX(-4px) }} to {{ opacity:1;transform:translateX(0) }} }}
@keyframes status-pulse {{ 0%,100% {{ opacity:1;transform:scale(1) }} 50% {{ opacity:.68;transform:scale(.86) }} }}
/* Keep Streamlit's native collapse control; these styles only skin the sidebar surface. */
[data-testid="stSidebar"] {{
  background:linear-gradient(180deg,#FDFCF8 0%,#FBFCF9 52%,#F7F9F5 100%)!important;
  border-right:1px solid #E8ECE6!important;
  color:#1D2E26!important;
  position:relative;isolation:isolate;transition:width .28s cubic-bezier(.2,.75,.25,1),transform .28s ease!important;
}}
[data-testid="stSidebar"]::before {{
  content:"";position:absolute;inset:0;z-index:0;pointer-events:none;
  background:radial-gradient(ellipse at 8% 0%,rgba(169,191,169,.16),transparent 42%);
  animation:sidebar-light-breathe 18s ease-in-out infinite;
}}
[data-testid="stSidebar"]>div,
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {{ background:transparent!important; }}
[data-testid="stSidebar"]>div {{ position:relative;z-index:1;padding:.95rem .85rem .8rem!important; }}
[data-testid="stSidebar"] hr {{ border-color:#E7ECE5!important;margin:.55rem .15rem!important; }}
.st-key-ayur_sidebar_root {{
  box-sizing:border-box;position:relative;isolation:isolate;min-height:calc(100vh - 2rem);
  color:#1D2E26;overflow:visible;
}}
.st-key-ayur_sidebar_root>div[data-testid="stVerticalBlock"] {{
  display:flex;flex-direction:column;min-height:inherit;gap:.2rem!important;
}}
.st-key-ayur_sidebar_root .stMarkdown {{ color:#1D2E26; }}
.st-key-ayur_sidebar_root .stMarkdown p {{ color:#64736A!important; }}
.st-key-ayur_sidebar_root .ayur-sidebar-brand {{
  display:flex;align-items:center;gap:.68rem;margin:.05rem .04rem .22rem;padding:.62rem .55rem .68rem;
  border:1px solid #E7ECE5;border-radius:13px;background:rgba(255,255,255,.78);
  box-shadow:0 2px 8px rgba(16,55,45,.035);
}}
.ayur-sidebar-mark {{ flex:0 0 42px;width:42px;height:42px;display:grid;place-items:center;border-radius:13px;
  background:#EDF3EC;border:1px solid #DFE8DD; }}
.ayur-sidebar-mark svg {{ width:31px;height:31px;overflow:visible; }}
.ayur-leaf-left {{ transform-origin:18px 19px;animation:sidebar-leaf-sway 5.4s ease-in-out infinite; }}
.ayur-leaf-right {{ transform-origin:19px 19px;animation:sidebar-leaf-sway 6.1s ease-in-out infinite reverse; }}
.ayur-sidebar-name {{ color:#174C3C;font:700 .84rem/1.2 'DM Sans',sans-serif;letter-spacing:.12em; }}
.ayur-sidebar-subtitle {{ color:#758178;font:400 .64rem/1.35 'DM Sans',sans-serif;margin-top:.25rem;letter-spacing:.005em; }}
.st-key-ayur_sidebar_root .ayur-sidebar-group {{
  margin:.36rem .52rem .2rem;color:#78877B;font:700 .6rem/1.2 'DM Sans',sans-serif;
  letter-spacing:.145em;text-transform:uppercase;
}}
.st-key-ayur_sidebar_root .st-key-ayur_nav_group_workspace {{
  border-top:1px solid #E8ECE6;margin-top:.28rem;padding-top:.18rem;
}}
.st-key-ayur_sidebar_root .st-key-ayur_nav_group_explore_knowledge,
.st-key-ayur_sidebar_root .st-key-ayur_nav_group_research,
.st-key-ayur_sidebar_root .st-key-ayur_nav_group_management {{
  border-top:1px solid #E8ECE6;margin-top:.34rem;padding-top:.2rem;
}}
.st-key-ayur_sidebar_root .stButton {{ margin:0!important; }}
.st-key-ayur_sidebar_root .stButton>button {{
  position:relative;box-sizing:border-box;width:100%;min-height:40px;justify-content:flex-start!important;
  text-align:left!important;gap:.62rem!important;padding:.3rem .68rem!important;margin:0!important;
  border:1px solid transparent!important;border-radius:10px!important;background:transparent!important;
  box-shadow:none!important;color:#405247!important;font:500 .84rem/1.2 'DM Sans',sans-serif!important;
  white-space:nowrap!important;transform:translateY(0);transition:background-color .2s ease,border-color .2s ease,color .2s ease,box-shadow .2s ease,transform .2s ease!important;
}}
.st-key-ayur_sidebar_root .stButton>button p {{ color:inherit!important;font-size:.84rem!important;white-space:nowrap!important;margin:0!important; }}
.st-key-ayur_sidebar_root .stButton>button [data-testid="stIconMaterial"] {{
  color:#718978!important;font-size:1.08rem!important;transition:transform .22s cubic-bezier(.2,.75,.25,1),color .2s ease!important;
}}
.st-key-ayur_sidebar_root .stButton>button:hover {{
  background:#EDF3EC!important;border-color:#E1EAE0!important;
  color:#10372D!important;box-shadow:0 2px 7px rgba(16,55,45,.045)!important;transform:translateY(-1px);
}}
.st-key-ayur_sidebar_root .stButton>button:hover [data-testid="stIconMaterial"] {{ color:#287557!important; }}
{icon_rules}
.st-key-ayur_sidebar_root .stButton>button:active {{ transform:translateY(0) scale(.99);background:#E3EDE2!important; }}
.st-key-ayur_sidebar_root .stButton>button:focus-visible {{ outline:2px solid #91AA94!important;outline-offset:2px!important; }}
.st-key-ayur_sidebar_root .stButton>button::before {{
  content:"";position:absolute;left:0;top:23%;bottom:23%;width:3px;border-radius:0 3px 3px 0;
  background:#287557;opacity:0;transform:scaleY(.45);transition:opacity .2s ease,transform .2s ease;
}}
.st-key-ayur_sidebar_root .stButton>button:hover::before {{ opacity:.62;transform:scaleY(.8); }}
.st-key-ayur_sidebar_root .stButton>button[kind="primary"] {{
  background:#EAF2E9!important;border-color:#DCE7DB!important;color:#174C3C!important;font-weight:650!important;
  box-shadow:inset 3px 0 #287557,0 2px 7px rgba(16,55,45,.045)!important;
}}
.st-key-ayur_sidebar_root .stButton>button[kind="primary"] p,
.st-key-ayur_sidebar_root .stButton>button[kind="primary"] [data-testid="stIconMaterial"] {{ color:#287557!important; }}
.st-key-ayur_sidebar_root .stButton>button[kind="primary"]::before {{ opacity:1;transform:scaleY(1); }}
.st-key-ayur_sidebar_root .stButton>button[kind="primary"]:hover {{ background:#E5EFE4!important;border-color:#D4E1D3!important; }}
.st-key-ayur_sidebar_root .st-key-ayur_sidebar_footer {{ margin-top:auto!important;padding-top:.75rem; }}
.st-key-ayur_sidebar_root .ayur-status-card {{
  display:grid;gap:.34rem;padding:.64rem .68rem .58rem;border:1px solid #E6EBE4;border-radius:12px;
  background:rgba(255,255,255,.78);box-shadow:0 2px 7px rgba(16,55,45,.035);
  color:#64736A;font:400 .66rem/1.35 'DM Sans',sans-serif;
}}
.ayur-status-heading {{ display:flex;align-items:center;gap:.45rem;color:#355544;font:700 .61rem/1.2 'DM Sans',sans-serif;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.04rem; }}
.ayur-status-row {{ display:flex;align-items:flex-start;justify-content:space-between;gap:.55rem; }}
.ayur-status-row span {{ color:#78847B;white-space:nowrap; }}
.ayur-status-row b {{ color:#355544;font-size:.66rem;font-weight:600;text-align:right;overflow-wrap:anywhere; }}
.ayur-status-model {{ display:block!important;color:#89938B!important;font-size:.57rem!important;line-height:1.35;margin:-.2rem 0 .04rem .85rem;overflow-wrap:anywhere; }}
.ayur-status-dot {{ display:inline-block;vertical-align:middle;flex:0 0 6px;width:6px;height:6px;border-radius:50%;background:#3D9560; }}
.ayur-status-dot.is-live {{ animation:status-pulse 2.6s ease-in-out infinite; }}
.ayur-status-dot.is-warning {{ background:#B49A59; }}
.ayur-status-dot.is-offline {{ background:#B96F66; }}
.ayur-sidebar-footer {{ display:flex;justify-content:space-between;gap:.4rem;padding:.52rem .12rem .04rem;color:#858F87;font:400 .58rem/1.35 'DM Sans',sans-serif; }}
.ayur-sidebar-footer strong {{ color:#45624F;font-weight:650;letter-spacing:.04em; }}
@media(max-height:820px) {{
  [data-testid="stSidebar"]>div {{ padding:.7rem .72rem .6rem!important; }}
  .st-key-ayur_sidebar_root {{ min-height:calc(100vh - 1.4rem); }}
  .st-key-ayur_sidebar_root .stButton>button {{ min-height:35px;padding:.2rem .55rem!important; }}
  .st-key-ayur_sidebar_root .ayur-sidebar-group {{ margin-top:.36rem;margin-bottom:.16rem; }}
  .st-key-ayur_sidebar_root .ayur-status-card {{ gap:.32rem;padding:.58rem .62rem; }}
}}
@media(max-width:520px) {{
  [data-testid="stSidebar"] {{ width:min(88vw,320px)!important;max-width:88vw!important; }}
  [data-testid="stSidebar"]>div {{ padding:.68rem .64rem!important; }}
  .st-key-ayur_sidebar_root .ayur-sidebar-brand {{ padding:.62rem .52rem; }}
}}
@media(prefers-reduced-motion:reduce) {{
  .ayur-leaf-left,.ayur-leaf-right {{ animation:none!important; }}
  .ayur-status-dot.is-live {{ animation:none!important; }}
  .st-key-ayur_sidebar_root *,[data-testid="stSidebar"] {{ scroll-behavior:auto!important;transition:none!important;animation:none!important; }}
}}
{entrance_rules}
</style>"""
    )


def _render_status_panel() -> None:
    connected, count = knowledge_status()
    model = model_status()
    provider = str(model["provider"])
    state = str(model["state"])
    dot_class = "is-live" if state == "available" else "is-offline" if state in {"unavailable", "missing"} else "is-warning"
    model_label = escape(str(model["label"]))
    model_name = escape(str(model["model"]))
    chroma_label = "Connected" if connected else "Unavailable"
    chroma_dot = "is-live" if connected else "is-offline"
    scope = "Development-only" if KNOWLEDGE_MODE == "development" else "Production"
    scope_suffix = " · rights pending" if KNOWLEDGE_MODE == "development" else ""
    st.markdown(
        '<div class="ayur-status-card" role="status" aria-label="Application system status">'
        f'<div class="ayur-status-heading"><span class="ayur-status-dot {dot_class}"></span>System status</div>'
        f'<div class="ayur-status-row"><span>AyurParam</span><b>{model_label}</b></div>'
        f'<small class="ayur-status-model">{model_name} · {escape(provider)}</small>'
        f'<div class="ayur-status-row"><span>ChromaDB</span><b><i class="ayur-status-dot {chroma_dot}"></i> {chroma_label}</b></div>'
        f'<div class="ayur-status-row"><span>Indexed passages</span><b>{count:,}</b></div>'
        f'<div class="ayur-status-row"><span>Knowledge scope</span><b>{scope}{scope_suffix}</b></div>'
        '</div>'
        '<div class="ayur-sidebar-footer"><strong>AYURFORM AI</strong><span>Academic research platform</span></div>',
        unsafe_allow_html=True,
    )


def render_sidebar(user: dict | None = None) -> str:
    """Render grouped sidebar navigation while retaining Streamlit page state."""
    pages = visible_sidebar_pages(user)
    # Profile is reached through the existing account menu rather than a sidebar
    # item, but must remain a valid selected route during that transition.
    routable_pages = (*pages, "Profile")
    st.session_state.page = normalize_page(st.session_state.get("page"), routable_pages)
    animate_entrance = not st.session_state.get("_ayur_sidebar_entrance_played", False)

    with st.sidebar:
        _sidebar_styles(animate_entrance)
        with st.container(key="ayur_sidebar_root"):
            logo = '''<div class="ayur-sidebar-brand">
              <div class="ayur-sidebar-mark" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none">
                <path d="M20 31V16" stroke="#D8C58E" stroke-width="1.55" stroke-linecap="round"/>
                <path class="ayur-leaf-left" d="M19.2 21.7C9.1 21.4 8.7 13.1 9.1 9.6c6.8.2 11.2 3.8 10.1 12.1Z" fill="#A9C8AA" stroke="#D6E5D3" stroke-width=".85"/>
                <path class="ayur-leaf-right" d="M20.1 18.7c.2-8.2 6.4-11.1 11-11.3.1 6.9-3.8 11.2-11 11.3Z" fill="#6FA47A" stroke="#C5DCC7" stroke-width=".85"/>
                <path d="M14 15.3c2.2 1.2 3.8 2.8 5 5.2M26.6 11.2c-2.1 1.6-4 3.7-5.5 6.4" stroke="#E8F0E4" stroke-width=".72" stroke-linecap="round" opacity=".82"/>
                <circle cx="20" cy="32" r="1.3" fill="#D8C58E"/>
              </svg></div>
              <div><div class="ayur-sidebar-name">AYURFORM AI</div><div class="ayur-sidebar-subtitle">Dravya · Formulation · Anupana<br>Intelligence</div></div>
            </div>'''
            st.markdown(logo, unsafe_allow_html=True)

            for group, group_pages in SIDEBAR_GROUPS.items():
                visible_group = [page for page in group_pages if page in pages]
                if not visible_group:
                    continue
                with st.container(key=f"ayur_nav_group_{_slug(group)}"):
                    st.markdown(f'<div class="ayur-sidebar-group">{escape(group)}</div>', unsafe_allow_html=True)
                    for title in visible_group:
                        active = st.session_state.page == title
                        with st.container(key=f"ayur_nav_item_{_slug(title)}"):
                            if st.button(
                                title,
                                key=f"nav_{title}",
                                type="primary" if active else "secondary",
                                use_container_width=True,
                                icon=PAGE_ICONS[title],
                                help=f"Open {title}",
                            ):
                                st.session_state.page = title
                                st.rerun()
            with st.container(key="ayur_sidebar_footer"):
                _render_status_panel()

    st.session_state["_ayur_sidebar_entrance_played"] = True
    return st.session_state.page
