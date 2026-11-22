"""Reusable global application header, page search, command palette and status panel."""
from __future__ import annotations

from html import escape
import re

import streamlit as st
from chromadb import PersistentClient

from config import CHROMA_COLLECTION, LLM_MODE, LLM_PROVIDER, VECTORSTORE_DIR
from frontend.layout import DESCRIPTIONS
from frontend.navigation import PAGE_ICONS, PAGES, knowledge_status, visible_sidebar_pages
from frontend.auth_pages import render_logout_control

SEARCH_PLACEHOLDER = "Search pages, concepts and references..."


def matching_pages(query: str, user: dict | None = None) -> list[str]:
    """Return real navigation pages matching their current title or description."""
    needle = query.strip().casefold()
    pages = list(visible_sidebar_pages(user))
    if user:
        pages.append("Profile")
    if not needle:
        return pages
    return [page for page in pages if needle in page.casefold() or needle in DESCRIPTIONS.get(page, "").casefold()]


@st.cache_data(ttl=15, show_spinner=False)
def search_indexed_passages(query: str, limit: int = 4) -> tuple[bool, list[dict]]:
    """Case-insensitive keyword search over actual Chroma documents; never synthesizes records."""
    needle = query.strip()
    if not needle:
        return False, []
    try:
        collection = PersistentClient(path=str(VECTORSTORE_DIR)).get_collection(CHROMA_COLLECTION)
        if collection.count() == 0:
            return False, []
    except Exception:
        return False, []

    terms = [needle]
    terms.extend(word for word in re.findall(r"[\w-]+", needle) if len(word) >= 3 and word.casefold() != needle.casefold())
    matches: dict[str, dict] = {}
    for term in terms:
        # Chroma's document contains filter is substring based; try lowercase and title case
        # to cover typical sentence capitalization, then score by matched query terms.
        variants = list(dict.fromkeys((term, term[:1].upper() + term[1:])))
        for variant in variants:
            try:
                rows = collection.get(
                    where_document={"$contains": variant},
                    limit=max(limit * 2, 8),
                    include=["documents", "metadatas"],
                )
            except Exception:
                continue
            for passage_id, text, metadata in zip(
                rows.get("ids", []), rows.get("documents", []), rows.get("metadatas", [])
            ):
                if not text:
                    continue
                row = matches.setdefault(passage_id, {
                    "id": passage_id, "text": text, "metadata": metadata or {}, "matched_terms": set()
                })
                row["matched_terms"].add(term.casefold())
    results = list(matches.values())
    for row in results:
        row["matched_terms"] = sorted(row["matched_terms"])
        row["score"] = len(row["matched_terms"])
    results.sort(key=lambda row: (-row["score"], row["id"]))
    return True, results[:limit]


def _navigate_to_page(page: str) -> None:
    if page in PAGES:
        st.session_state["page"] = page
        st.session_state["global_search_query"] = ""
        st.session_state.pop("global_search_selected_passage", None)


def _open_passage(passage: dict) -> None:
    st.session_state["page"] = "Classical Library"
    st.session_state["global_search_selected_passage"] = passage
    st.session_state["global_search_query"] = ""


def _clear_selected_passage() -> None:
    st.session_state.pop("global_search_selected_passage", None)


def _header_styles() -> None:
    st.html(
        """<style>
        .st-key-global_app_header{box-sizing:border-box;min-height:76px;border-bottom:1px solid #E3E9E2;padding:.35rem 0;margin:0}
        .st-key-global_app_header [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(145px,1fr) minmax(220px,2fr) 42px 42px 42px;gap:clamp(.4rem,1vw,.85rem)!important;align-items:center}
        .st-key-global_app_header [data-testid="stColumn"]{width:auto!important;min-width:0!important;flex:initial!important}
        .global-context-label{min-height:42px;display:flex;flex-direction:column;justify-content:center;color:#10372D;font:600 1.04rem/1.15 'DM Sans',sans-serif;white-space:nowrap}
        .global-context-label small{display:block;color:#64736A;font:700 .62rem/1.2 'DM Sans',sans-serif;letter-spacing:.13em;text-transform:uppercase;margin-bottom:.18rem}
        .st-key-global_search_palette [data-testid="stPopoverButton"]{width:100%;min-height:42px!important;justify-content:flex-start!important;background:#fff!important;border-color:#E3E9E2!important;color:#64736A!important;font-weight:500!important;text-align:left!important}
        .st-key-global_search_palette [data-testid="stPopoverButton"]:after{content:"Ctrl K";margin-left:auto;padding:2px 6px;border:1px solid #E3E9E2;border-radius:5px;color:#64736A;font-size:.65rem;font-weight:600;white-space:nowrap}
        .st-key-global_app_header [data-testid="stPopoverButton"]{min-height:42px!important;border-color:#E3E9E2!important;background:#fff!important;color:#174C3C!important}
        .st-key-global_search_palette [data-testid="stPopoverButton"]:hover,.st-key-global_app_header [data-testid="stPopoverButton"]:hover{border-color:#A9BFA9!important;background:#FAFCF9!important}
        .st-key-global_app_header [data-testid="stPopoverBody"]{max-height:68vh;overflow-y:auto}
        .st-key-global_help [data-testid="stPopoverButton"],.st-key-global_notifications [data-testid="stPopoverButton"],.st-key-global_account [data-testid="stPopoverButton"]{width:42px!important;min-height:42px!important;padding:.35rem!important;justify-content:center!important;gap:0!important;font-size:0!important}
        .st-key-global_help [data-testid="stPopoverButton"] [data-testid="stIconMaterial"],.st-key-global_notifications [data-testid="stPopoverButton"] [data-testid="stIconMaterial"],.st-key-global_account [data-testid="stPopoverButton"] [data-testid="stIconMaterial"]{font-size:1.15rem!important}
        .st-key-global_keyboard_listener{position:fixed!important;left:0!important;bottom:0!important;width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;pointer-events:none!important;z-index:-1!important}
        .st-key-global_keyboard_listener iframe{display:block!important;width:1px!important;height:1px!important;border:0!important}
        .header-popover-title{font:600 1.05rem 'Playfair Display',serif;color:#10372D;margin:.15rem 0 .45rem}
        .header-popover-status{display:flex;justify-content:space-between;gap:.8rem;padding:.55rem 0;border-bottom:1px solid #E3E9E2;color:#64736A;font-size:.82rem}
        .header-popover-status strong{color:#1D2E26;font-weight:600;text-align:right}
        .header-empty-state{border:1px solid #E3E9E2;border-radius:11px;background:#F8FAF7;padding:.8rem;color:#64736A;font-size:.82rem;line-height:1.5;margin-top:.6rem}
        .header-search-hint{color:#64736A;font-size:.8rem;line-height:1.45;margin:.2rem 0 .6rem}
        .header-reference{border:1px solid #E3E9E2;border-radius:11px;background:#fff;padding:.75rem .85rem;margin:.45rem 0}
        .header-reference-title{color:#10372D;font-size:.85rem;font-weight:700}
        .header-reference-meta{color:#64736A;font-size:.73rem;margin:.2rem 0 .45rem}
        .st-key-global_search_results .stButton>button{justify-content:flex-start!important;text-align:left!important;min-height:38px!important}
        .st-key-global_search_results .stButton>button:focus-visible{outline:3px solid rgba(40,117,87,.28)!important;outline-offset:1px}
        .header-help-list{color:#64736A;font-size:.82rem;line-height:1.55}
        @media(max-width:920px){
          .st-key-global_app_header{min-height:76px}
          .st-key-global_app_header [data-testid="stHorizontalBlock"]{grid-template-columns:minmax(0,1fr) 42px 42px 42px;gap:.35rem .45rem!important}
          .st-key-global_app_header [data-testid="stColumn"]:first-child{grid-column:1/-1}
          .st-key-global_app_header [data-testid="stColumn"]:nth-child(2){grid-column:1;grid-row:2}
          .st-key-global_app_header [data-testid="stColumn"]:nth-child(3){grid-column:2;grid-row:2}
          .st-key-global_app_header [data-testid="stColumn"]:nth-child(4){grid-column:3;grid-row:2}
          .st-key-global_app_header [data-testid="stColumn"]:nth-child(5){grid-column:4;grid-row:2}
        }
        @media(max-width:390px){.st-key-global_app_header{min-height:76px}.global-context-label{font-size:1rem}}
        </style>""",
    )


def _keyboard_shortcuts() -> None:
    """Bind the existing Streamlit search palette to Ctrl+K, Escape and arrow keys."""
    input_selector = f'.st-key-global_search_palette input[placeholder="{SEARCH_PLACEHOLDER}"]'
    with st.container(key="global_keyboard_listener"):
        st.iframe(
            f"""<script>
        (() => {{
          try {{
            const doc = window.parent.document;
            if (doc.__ayursutraGlobalSearchKeys) return;
            doc.__ayursutraGlobalSearchKeys = true;
            const searchButton = () => doc.querySelector('.st-key-global_search_palette button[data-testid="stPopoverButton"]');
            const searchInput = () => doc.querySelector('{input_selector}');
            const resultButtons = () => [...doc.querySelectorAll('.st-key-global_search_results button')]
              .filter(button => !button.disabled && button.getClientRects().length);
            doc.addEventListener('keydown', event => {{
              if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {{
                event.preventDefault();
                const button = searchButton();
                if (button && button.getAttribute('aria-expanded') !== 'true') button.click();
                window.setTimeout(() => searchInput()?.focus(), 120);
              }} else if (event.key === 'Escape' && (doc.activeElement === searchInput() ||
                doc.querySelector('.st-key-global_search_palette [data-testid="stPopoverBody"]')?.contains(doc.activeElement))) {{
                event.preventDefault();
                searchInput()?.blur();
                searchButton()?.click();
              }} else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {{
                const input = searchInput();
                const buttons = resultButtons();
                const current = buttons.indexOf(doc.activeElement);
                if (!buttons.length || (doc.activeElement !== input && current < 0)) return;
                event.preventDefault();
                const delta = event.key === 'ArrowDown' ? 1 : -1;
                const next = current < 0 ? (delta > 0 ? 0 : buttons.length - 1) : (current + delta + buttons.length) % buttons.length;
                buttons[next].focus();
              }} else if (event.key === 'Enter' && doc.activeElement === searchInput()) {{
                const firstResult = resultButtons()[0];
                if (firstResult) {{ event.preventDefault(); firstResult.click(); }}
              }}
            }}, true);
          }} catch (_) {{ /* Shortcut is optional if the host blocks same-origin component access. */ }}
        }})();
            </script>""",
            height=1,
            width=1,
            tab_index=-1,
            alt="Global keyboard shortcut listener",
        )


def render_app_header(page: str, user: dict | None = None) -> None:
    """Render the same compact page context, search palette, notification panel and status on every route."""
    if page not in PAGES:
        page = "Dashboard"
    previous_page = st.session_state.get("_header_current_page")
    if previous_page and previous_page != page:
        st.session_state["global_search_query"] = ""
    st.session_state["_header_current_page"] = page

    connected, passage_count = knowledge_status()
    provider = LLM_MODE or LLM_PROVIDER or "mock"
    model_label = "Mock mode" if provider == "mock" else ("Ollama configured" if provider == "ollama" else "AyurParam configured")
    _header_styles()
    with st.container(key="global_app_header"):
        context_col, search_col, help_col, notification_col, account_col = st.columns(
            [1.0, 2.0, .28, .28, .28], vertical_alignment="center"
        )
        with context_col:
            st.markdown('<div class="global-context-label"><small>AyurForm AI</small>Workspace</div>', unsafe_allow_html=True)
        with search_col:
            with st.popover(
                "Search",
                icon=":material/search:",
                help="Search workspace pages. Keyboard shortcut: Ctrl + K.",
                use_container_width=True,
                key="global_search_palette",
            ):
                st.markdown('<div class="header-popover-title">Go to a page</div>', unsafe_allow_html=True)
                query = st.text_input(
                    "Global search",
                    key="global_search_query",
                    placeholder=SEARCH_PLACEHOLDER,
                    label_visibility="collapsed",
                )
                matches = matching_pages(query, user)
                passage_available, passages = search_indexed_passages(query) if query.strip() else (False, [])
                with st.container(key="global_search_results"):
                    if matches:
                        st.caption("Pages")
                        for destination in matches:
                            st.button(
                                destination,
                                key=f"global_search_result_{destination.lower().replace(' ', '_')}",
                                icon=PAGE_ICONS[destination],
                                use_container_width=True,
                                on_click=_navigate_to_page,
                                args=(destination,),
                            )
                    if passages:
                        st.caption("Indexed classical passages")
                        for passage in passages:
                            metadata = passage.get("metadata", {}) or {}
                            title = metadata.get("source_title") or metadata.get("book_name")
                            source_line = " · ".join(str(value) for value in (
                                title,
                                f"Chapter {metadata['chapter_number']}" if metadata.get("chapter_number") else None,
                                f"Page {metadata['page_number']}" if metadata.get("page_number") else None,
                            ) if value)
                            st.markdown(
                                f'<div class="header-reference"><div class="header-reference-title">{escape(str(title or "Indexed source"))}</div>'
                                f'<div class="header-reference-meta">{escape(source_line or "Source metadata unavailable")}</div></div>',
                                unsafe_allow_html=True,
                            )
                            st.write(passage["text"][:360] + ("…" if len(passage["text"]) > 360 else ""))
                            st.button(
                                "Open passage in Classical Library",
                                key=f"global_search_passage_{passage['id']}",
                                icon=":material/menu_book:",
                                use_container_width=True,
                                on_click=_open_passage,
                                args=(passage,),
                            )
                    elif query.strip() and not matches:
                        if passage_count == 0:
                            message = "No classical passages are indexed yet. Search is limited to real workspace pages until an authorized corpus is ingested."
                        elif not passage_available:
                            message = "The classical collection is unavailable, so only workspace pages can be searched right now."
                        else:
                            message = "No matching workspace pages or indexed classical passages were found."
                        st.markdown(f'<div class="header-empty-state">{escape(message)}</div>', unsafe_allow_html=True)

        with help_col:
            with st.popover("Help", icon=":material/help_outline:", help="AyurForm AI help", key="global_help"):
                st.markdown('<div class="header-popover-title">Using AyurForm AI</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="header-help-list">Search navigates research modules and indexed source passages. AyurForm supports academic exploration of Dravya, formulations, Anupana and source evidence.</div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "About AyurForm AI",
                    key="global_help_about",
                    icon=PAGE_ICONS["About"],
                    use_container_width=True,
                    on_click=_navigate_to_page,
                    args=("About",),
                )

        with notification_col:
            with st.popover(
                "Notifications", icon=":material/notifications_none:",
                help="View current system status", key="global_notifications"
            ):
                st.markdown('<div class="header-popover-title">System status</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="header-popover-status"><span>Generation mode</span><strong>{escape(model_label)}</strong></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="header-popover-status"><span>ChromaDB</span><strong>{"Connected" if connected else "Unavailable / not initialized"}</strong></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="header-popover-status"><span>Indexed passages</span><strong>{passage_count:,}</strong></div>', unsafe_allow_html=True)
                st.markdown('<div class="header-empty-state">No new notifications. System information above reflects the current application state.</div>', unsafe_allow_html=True)

        with account_col:
            with st.popover("Account", icon=":material/person_outline:", help="Account options", key="global_account"):
                st.markdown('<div class="header-popover-title">Your account</div>', unsafe_allow_html=True)
                if user:
                    st.markdown(f'<div class="header-popover-title">{escape(str(user.get("full_name", "Your account")))}</div>', unsafe_allow_html=True)
                    if st.button("Profile", key="global_account_profile", icon=":material/account_circle:", use_container_width=True, on_click=_navigate_to_page, args=("Profile",)):
                        st.rerun()
                    render_logout_control()
                else:
                    st.caption("Sign in to access your workspace.")
                    st.markdown('<a href="/?auth=login">Log in</a> · <a href="/?auth=signup">Sign up</a>', unsafe_allow_html=True)
                st.divider()
                st.markdown('<div class="header-popover-title">Workspace</div>', unsafe_allow_html=True)
                for destination, icon in (
                    ("Dashboard", PAGE_ICONS["Dashboard"]),
                    ("Settings", PAGE_ICONS["Settings"]),
                ):
                    st.button(
                        destination,
                        key=f"global_menu_{destination.lower().replace(' ', '_')}",
                        icon=icon,
                        use_container_width=True,
                        on_click=_navigate_to_page,
                        args=(destination,),
                    )
        _keyboard_shortcuts()
