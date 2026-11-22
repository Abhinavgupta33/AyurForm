"""Shared page header and phase placeholder layout."""
import streamlit as st

DESCRIPTIONS={"Dashboard":"Your AyurForm academic research workspace.","Research Library":"Return to saved scholarly references.","About":"Learn about AyurForm as an academic Ayurveda knowledge platform.","Settings":"Review application and model settings.","Profile":"Manage your account details."}

def render_page_header(page):
    st.markdown(f'<div class="shell-header"><h1>{page}</h1><p class="shell-desc">{DESCRIPTIONS.get(page,"AyurForm academic knowledge workspace.")}</p></div>',unsafe_allow_html=True)

def render_phase_placeholder(page=None):
    selected = st.session_state.get("global_search_selected_passage") if page == "Classical Library" else None
    if selected:
        metadata = selected.get("metadata", {}) or {}
        title = metadata.get("source_title") or metadata.get("book_name")
        details = [value for value in (
            metadata.get("sthana"),
            f"Chapter {metadata['chapter_number']}" if metadata.get("chapter_number") else None,
            f"Verse {metadata['verse_number']}" if metadata.get("verse_number") else None,
            f"PDF page {metadata['page_number']}" if metadata.get("page_number") else None,
        ) if value]
        st.markdown("### Passage found in indexed source")
        if title:
            st.markdown(f"**{title}**")
        if details:
            st.caption(" · ".join(str(value) for value in details))
        st.write(selected.get("text", ""))
        st.caption("Displayed from the indexed passage returned by global search.")
        if st.button("Clear selected passage", key="clear_global_search_passage"):
            st.session_state.pop("global_search_selected_passage", None)
            st.rerun()
        return
    st.markdown('<div class="shell-placeholder"><strong>Coming in the next development phase</strong><p>This page is part of the AyurForm academic knowledge workspace. Its features will be implemented in a later phase.</p></div>',unsafe_allow_html=True)
