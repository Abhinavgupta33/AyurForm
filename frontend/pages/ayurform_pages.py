import os
import streamlit as st
import httpx
from auth_service import ACCESS_COOKIE

ENTITY = {"Dravya Explorer": ("dravya", "Search canonical names, Sanskrit names and verified properties."), "Formulation Explorer": ("formulations", "Explore documented formulations and ingredients."), "Anupana Explorer": ("anupana_relationships", "Browse documented Anupana relationships only."), "Classical Sources": ("sources", "Review source rights, provenance and review status.")}

REVIEW_PAGE = "Review Dashboard"
POPULAR_DRAVYAS = (
    "Turmeric", "Ginger", "Neem", "Amla", "Ashwagandha", "Tulsi",
    "Haritaki", "Brahmi", "Shatavari", "Pippali", "Guduchi", "Arjuna",
)


def apply_popular_dravya_selection(name: str, mode: str, state: dict) -> None:
    """Route a suggestion into the active mode without asserting database presence."""
    state["dravya_mode"] = mode
    state["dravya_mode_active"] = mode
    state["dravya_research_answer"] = None
    if mode == "Search approved records":
        state["search_dravya"] = name
        state["dravya_search_suggestion"] = True
    elif mode in {"Direct AyurParam", "Source-grounded RAG"}:
        state["dravya_ai_name"] = name
        state["dravya_suggestion_run"] = mode


def _select_popular_dravya(name: str, mode: str) -> None:
    apply_popular_dravya_selection(name, mode, st.session_state)


def _clear_approved_dravya_search() -> None:
    st.session_state["search_dravya"] = ""
    st.session_state["dravya_search_results"] = None
    st.session_state["dravya_search_query"] = ""
    st.session_state["dravya_search_suggestion"] = False

def content_route_for_page(page: str) -> str:
    """Keep review and explorer page dispatch explicit and disjoint."""
    if page == REVIEW_PAGE:
        return "review"
    if page == "Research Assistant":
        return "research"
    if page in ENTITY:
        return "explorer"
    return "unknown"

def render_ayurform_page(page: str):
    route = content_route_for_page(page)
    if route == "unknown":
        st.error("This AyurForm page is not registered with the content renderer.")
        return
    if page == "Classical Sources":
        st.markdown("## Classical Sources")
        st.caption("Development intake creates rights-pending review records. It does not index or publish passages.")
        try:
            access=st.context.cookies.get(ACCESS_COOKIE)
            from auth_service import AuthService, AuthSettings
            principal=AuthService(AuthSettings.from_env()).principal(access)
            allowed={x.strip().casefold() for x in os.getenv("AYURFORM_ADMIN_EMAILS","").split(",") if x.strip()}
            if principal.get("email","").casefold() not in allowed:
                st.error("Source ingestion is restricted to configured administrators."); return
        except Exception:
            st.error("An authenticated administrator session is required to ingest a source."); return
        upload=st.file_uploader("PDF source",type=["pdf"])
        title=st.text_input("Title as shown in the source")
        author=st.text_input("Author/editor (if verified)"); translator=st.text_input("Translator (if verified)")
        language=st.text_input("Language (if verified)"); edition=st.text_input("Edition (if verified)")
        publisher=st.text_input("Publisher (if verified)"); year=st.text_input("Publication year (if verified)")
        if st.button("Extract to development review",type="primary",disabled=not upload):
            try:
                from ingestion.classical_source import ingest_pdf_bytes
                metadata={"title":title,"author_editor":author or None,"translator":translator or None,"language":language or None,"edition":edition or None,"publisher":publisher or None,"publication_year":year or None}
                result=ingest_pdf_bytes(upload.getvalue(),metadata)
                st.success("Extracted to development-only, rights-pending review storage. Nothing was added to ChromaDB.")
                st.json(result["statistics"])
                st.caption(f"Extraction warnings: {len(result['quality']['warnings'])}; rights status: pending")
            except Exception as exc: st.error(f"Ingestion stopped: {exc}")
        return
    if page == "Formulation Explorer":
        from frontend.pages.formulation_explorer import render_formulation_explorer
        render_formulation_explorer()
        return
    if page == "Anupana Explorer":
        from frontend.pages.anupana_explorer import render_anupana_explorer
        render_anupana_explorer()
        return
    if page == "Dravya Explorer":
        st.markdown(
            "<div class='dravya-page-intro'><div class='dravya-eyebrow'>AYURVEDA KNOWLEDGE WORKSPACE</div>"
            "<h1>Dravya Explorer</h1><p>Explore reviewed records or research a substance with AyurParam.</p></div>",
            unsafe_allow_html=True,
        )
        st.markdown("""
        <style>
        .dravya-page-intro{padding:.2rem 0 1rem;border-bottom:1px solid #E3E9E2;margin-bottom:1rem}
        .dravya-eyebrow{font:700 .68rem 'DM Sans',sans-serif;letter-spacing:.15em;color:#287557;margin-bottom:.35rem}
        .dravya-page-intro h1{margin:0 0 .25rem!important;color:#10372D!important}
        .dravya-page-intro p{margin:0;color:#64736A;font-size:.98rem}
        .dravya-mode-caption{font-size:.8rem;color:#64736A;padding:.1rem 0 .3rem}
        @media(max-width:640px){.dravya-page-intro{padding-bottom:.75rem}.dravya-page-intro p{font-size:.9rem}}
        </style>
        """, unsafe_allow_html=True)
        from config import KNOWLEDGE_MODE
        mode = st.radio(
            "Research mode",
            ["Search approved records", "Direct AyurParam", "Source-grounded RAG"],
            horizontal=True,
            key="dravya_mode",
            label_visibility="collapsed",
        )
        previous_mode = st.session_state.get("dravya_mode_active")
        if previous_mode != mode:
            st.session_state["dravya_research_answer"] = None
            st.session_state["dravya_mode_active"] = mode
        api_url=os.getenv("AYURFORM_API_URL","http://127.0.0.1:8002").rstrip("/")
        st.markdown("### Explore Popular Dravyas")
        st.caption("Suggestions are research shortcuts only; they do not indicate that an approved record exists.")
        for start in range(0, len(POPULAR_DRAVYAS), 3):
            columns = st.columns(3)
            for column, suggestion in zip(columns, POPULAR_DRAVYAS[start:start + 3]):
                with column:
                    st.button(
                        suggestion,
                        key=f"popular_dravya_{mode}_{suggestion}",
                        use_container_width=True,
                        on_click=_select_popular_dravya,
                        args=(suggestion, mode),
                    )
        if mode=="Search approved records":
            with st.container(border=True):
                st.markdown("### Search reviewed knowledge")
                st.caption("Search canonical names, Sanskrit names and recorded synonyms. Only approved records appear here.")
                search=st.text_input("Dravya name, Sanskrit name, synonym or botanical name",key="search_dravya",placeholder="Search approved records")
                search_col, clear_col = st.columns([1, 1])
                with search_col:
                    search_clicked = st.button("Search approved records", type="primary", use_container_width=True)
                with clear_col:
                    st.button("Clear search", on_click=_clear_approved_dravya_search, use_container_width=True)
                selected_suggestion = st.session_state.pop("dravya_search_suggestion", False)
                if search_clicked or selected_suggestion:
                    st.session_state["dravya_search_results"] = None
                    st.session_state["dravya_search_error"] = None
                    st.session_state["dravya_search_query"] = search
                    if not search.strip():
                        st.session_state["dravya_search_error"] = "Enter a name or synonym to search."
                    else:
                        try:
                            with st.spinner("Searching approved Dravya records…"):
                                response=httpx.get(f"{api_url}/api/dravya",params={"search":search,"limit":50},timeout=8)
                                response.raise_for_status()
                                st.session_state["dravya_search_results"]=response.json().get("items",[])
                        except httpx.HTTPStatusError as exc:
                            st.session_state["dravya_search_error"]=f"Approved-record API returned HTTP {exc.response.status_code}."
                        except (httpx.RequestError, ValueError, AttributeError):
                            st.session_state["dravya_search_error"]="Approved-record search is unavailable or returned an invalid response."
                if st.session_state.get("dravya_search_query") == search:
                    search_error=st.session_state.get("dravya_search_error")
                    results=st.session_state.get("dravya_search_results")
                    if search_error:
                        st.error(search_error)
                    elif results is None and not search.strip():
                        st.info("Enter a Dravya name above, then select Search approved records or a popular suggestion.")
                    elif results is None:
                        st.caption("Select Search approved records to run this query.")
                    elif results is not None and not results:
                        st.info("No approved Dravya record matches this search.")
                    elif results:
                        st.caption(f"{len(results)} approved record(s)")
                        for item in results:
                            with st.container(border=True):
                                st.subheader(item.get("canonical_name","Dravya"))
                                st.caption(f"Sanskrit name: {item.get('sanskrit_name') or 'not recorded'}")
                                st.caption(f"Botanical identity: {item.get('botanical_identity') or 'not recorded'}")
                                synonyms = [row.get("synonym") for row in item.get("synonyms",[]) if row.get("synonym")]
                                if synonyms:
                                    st.caption("Recorded synonyms: " + ", ".join(synonyms))
                                attributes=item.get("attributes",[])
                                if attributes:
                                    st.markdown("**Approved source-backed attributes**")
                                    for attribute in attributes:
                                        st.markdown(f"- **{attribute['attribute_type']}:** {attribute['attribute_value']}")
                                        ref=attribute.get("source_reference") or {}
                                        st.caption(
                                            f"Source: {ref.get('source_title') or 'not recorded'} · "
                                            f"Passage: {ref.get('stable_passage_id') or 'not recorded'} · "
                                            f"Chapter: {ref.get('chapter') or ref.get('section') or 'not recorded'} · "
                                            f"Page: {ref.get('pdf_page') or 'not recorded'}"
                                        )
                                else:
                                    st.caption("No publicly eligible approved attributes are available.")
                elif not search.strip():
                    st.info("Enter a Dravya name above, then select Search approved records or a popular suggestion.")
                else:
                    st.caption("Select Search approved records to run this query.")
            return
        direct_mode = mode == "Direct AyurParam"
        with st.container(border=True):
            st.markdown("### Research a Dravya")
            st.markdown(
                "<div class='dravya-mode-caption'>Ask AyurParam for a general explanation.</div>" if direct_mode
                else "<div class='dravya-mode-caption'>Generate an explanation from eligible passages in the selected knowledge base.</div>",
                unsafe_allow_html=True,
            )
            name=st.text_input("Dravya name",key="dravya_ai_name",placeholder="Enter a name, such as Tulsi")
            st.caption("The selected mode controls whether source retrieval is used.")
            button_label = "Generate explanation" if direct_mode else "Ask AyurParam"
            run_analysis = st.button(button_label,type="primary",disabled=not name.strip(),use_container_width=True)
        from ayurform_dravya_research import model_mode
        provider=model_mode()
        if provider=="ollama":
            from config import OLLAMA_BASE_URL, OLLAMA_MODEL
            try:
                tags=httpx.get(f"{OLLAMA_BASE_URL}/api/tags",timeout=3).json()
                available=any(x.get("name")==OLLAMA_MODEL or x.get("model")==OLLAMA_MODEL for x in tags.get("models",[]))
                model_status = "Available" if available else "Not listed by Ollama"
            except httpx.HTTPError:
                model_status = "Ollama unavailable"
            st.caption(f"Configured AyurParam · {OLLAMA_MODEL} · {model_status}")
        elif provider=="mock": st.warning("Mock mode is active. Real AyurParam inference is disabled.")
        else: st.caption(f"Configured provider: {provider}; this research mode requires the configured AyurParam Ollama model.")
        if direct_mode:
            st.info("Generated directly by AyurParam. Not verified against retrieved classical sources.")
        else:
            if KNOWLEDGE_MODE == "development":
                st.warning("Development corpus selected. Source rights remain pending; these results are not production-approved evidence.")
            else:
                st.caption("Production retrieval is restricted to eligible usage scope and verified/licensed/public-domain sources.")
        suggested_mode = st.session_state.pop("dravya_suggestion_run", None)
        if run_analysis or suggested_mode == mode:
            st.session_state["dravya_research_answer"] = None
            if provider=="mock": st.warning("Mock mode is active. No model answer was generated."); return
            if provider!="ollama": st.error("Configure LLM_PROVIDER=ollama to use the selected AyurParam model."); return
            try:
                from models.llm import OllamaLLM, OllamaError
                from ayurform_dravya_research import build_direct_dravya_answer, build_dravya_answer
                with st.spinner("Asking AyurParam directly…" if direct_mode else "Retrieving eligible passages and asking AyurParam…"):
                    if direct_mode:
                        answer=build_direct_dravya_answer(name,OllamaLLM())
                    else:
                        answer=build_dravya_answer(name,OllamaLLM())
                st.session_state["dravya_research_answer"]=answer
            except OllamaError as exc: st.error(f"AyurParam inference unavailable: {exc}")
            except Exception: st.error("AyurParam returned an answer that could not be safely displayed.")
        answer=st.session_state.get("dravya_research_answer")
        if answer and ((answer.get("mode") == "direct") != direct_mode):
            answer = None
        if answer:
            st.subheader(answer["canonical_name"])
            if answer["mode"] == "direct":
                st.caption(f"{answer.get('model','unavailable')}  ·  Direct generation")
                st.markdown(answer["answer"])
                return
            st.caption(f"Model: {answer.get('model','unavailable')} · Status: {'source-grounded response' if answer['mode']=='grounded' else 'insufficient source evidence'}")
            if answer["mode"]=="grounded":
                st.markdown("#### AyurParam answer")
                st.markdown(answer["answer"])
                citation_links = ", ".join(f"[{row['citation_id']}](#source-{row['citation_id']})" for row in answer.get("evidence",[]))
                st.markdown("Retrieved evidence: " + citation_links)
            else:
                st.warning(answer.get("limitations") or "Insufficient source evidence. No explanation was generated.")
            st.markdown("#### Retrieved evidence")
            for evidence in answer.get("evidence",[]):
                citation_id = evidence.get("citation_id", "")
                if citation_id.startswith("P") and citation_id[1:].isdigit():
                    st.markdown(f'<span id="source-{citation_id}"></span>', unsafe_allow_html=True)
                with st.expander(f"{citation_id} · {evidence.get('passage_id') or 'Passage ID unavailable'} · {evidence.get('source_title') or 'Source title not recorded'} · Page {evidence.get('page') or 'not recorded'}"):
                    metadata = evidence.get("metadata") or {}
                    st.caption(f"Chapter/section: {evidence.get('chapter') or 'not recorded'} · Provenance: {metadata.get('provenance_role', 'unknown')} · Usage: {metadata.get('usage_scope', 'not recorded')} · Evidence status: retrieved text")
                    st.write(evidence["text"])
        return
    demo_mode = os.getenv("AYURFORM_DEMO_MODE", "0") == "1"
    if demo_mode:
        st.warning("Demonstration mode: any displayed demo records are synthetic and are not classical evidence.")
    if route == "review":
        st.markdown("## Expert Review Dashboard")
        st.caption("Administrative review is restricted to configured reviewer accounts. Approval requires source-backed evidence.")
        api_url = os.getenv("AYURFORM_API_URL", "http://127.0.0.1:8002").rstrip("/")
        try:
            access = st.context.cookies.get(ACCESS_COOKIE)
            headers={"Cookie": f"{ACCESS_COOKIE}={access}"} if access else {}
            health = httpx.get(f"{api_url}/api/health", timeout=5)
            response = httpx.get(f"{api_url}/api/reviews/pending", headers=headers, timeout=5)
        except httpx.RequestError as exc:
            st.error(f"Review API is unreachable at {api_url}. Start the AyurForm API and try again.")
            st.caption(f"Connection error: {type(exc).__name__}"); return
        if response.status_code == 401:
            st.error("Your session is missing or expired. Sign in again before opening the review queue."); return
        if response.status_code == 403:
            st.error("Administrator access is not configured for this account. Add the signed-in email to AYURFORM_ADMIN_EMAILS, then restart the API."); return
        if response.status_code != 200:
            st.error(f"Review API returned HTTP {response.status_code}; the queue was not loaded.")
            st.caption(response.text[:300]); return
        try: pending = response.json().get("items", [])
        except ValueError:
            st.error("Review API returned an invalid response; the queue was not loaded."); return
        if health.is_success:
            db = health.json().get("database", {})
            st.caption(f"API connected · database={db.get('backend','unknown')} · database status={'connected' if db.get('connected') else 'unavailable'}")
        from ayurform_dravya_research import DRAFT_DIR
        drafts=[]
        if DRAFT_DIR.exists():
            import json
            for draft_path in sorted(DRAFT_DIR.glob("*.json")):
                try: drafts.append(json.loads(draft_path.read_text(encoding="utf-8")))
                except (OSError,ValueError): continue
        st.markdown("#### Pending AI research drafts")
        if drafts:
            for draft in drafts:
                with st.expander(f"{draft.get('canonical_name','Dravya')} · pending research draft · {draft.get('owner_email','owner unavailable')}"):
                    st.caption("AI research draft; not an approved structured record.")
                    st.json(draft.get("claims",[])); st.json(draft.get("evidence",[]))
        else: st.info("No pending AI research drafts.")
        if not pending: st.info("No pending or rejected Dravya database records require review."); return
        labels = {str(x["id"]): f"{x.get('canonical_name','Unnamed')} · {x.get('review_status','pending')}" for x in pending}
        selected = st.selectbox("Record queue", list(labels), format_func=lambda x: labels[x])
        detail = httpx.get(f"{api_url}/api/reviews/dravya/{selected}", headers={"Cookie": f"{ACCESS_COOKIE}={access}"}, timeout=5).json()
        record = detail.get("record", {}); st.markdown(f"### {record.get('canonical_name','Unnamed')}")
        st.write({k:record.get(k) for k in ("sanskrit_name","botanical_identity","review_status")})
        st.markdown("#### Synonyms and attributes")
        st.json({"synonyms":detail.get("synonyms",[]),"attributes":detail.get("attributes",[])})
        st.markdown("#### Linked source evidence and rights")
        evidence_rows = detail.get("evidence", [])
        if not evidence_rows:
            st.info("No linked source passages are available for this record.")
        for evidence in evidence_rows:
            passage_label = evidence.get("stable_passage_id") or "Passage ID unavailable"
            with st.expander(f"{evidence.get('attribute_type','Attribute')}: {passage_label} · Page {evidence.get('pdf_page') or 'not recorded'}"):
                st.caption(
                    f"Source: {evidence.get('source_title') or 'not recorded'} · "
                    f"Chapter/section: {evidence.get('chapter') or evidence.get('section') or 'not recorded'} · "
                    f"Verse: {evidence.get('verse_reference') or 'not recorded'}"
                )
                st.caption(
                    f"Author/editor: {evidence.get('editor') or 'not recorded'} · "
                    f"Translator: {evidence.get('translator') or 'not recorded'} · "
                    f"Edition: {evidence.get('edition') or 'not recorded'} · "
                    f"Published by: {evidence.get('publisher') or 'not recorded'} · "
                    f"Year: {evidence.get('publication_year') or 'not recorded'}"
                )
                st.caption(
                    f"Attribute review: {evidence.get('attribute_review_status')} · "
                    f"Passage review: {evidence.get('passage_review_status')} · "
                    f"Source review: {evidence.get('source_review_status')} · "
                    f"Provenance: {evidence.get('passage_provenance')} · "
                    f"Rights: {evidence.get('rights_status')} · Usage: {evidence.get('usage_scope')}"
                )
                st.markdown(f"**{evidence.get('attribute_type','Attribute')}:** {evidence.get('attribute_value','')}")
                st.write(evidence.get("passage_text", ""))
        st.markdown("#### Review history")
        st.json(detail.get("history", []))
        st.warning("Evidence must be approved and source-backed before approval.")
        reason = st.text_area("Rejection reason (required only for rejection)", key=f"reject_reason_{selected}")
        c1,c2=st.columns(2)
        with c1:
            if st.button("Approve record", type="primary"):
                r=httpx.post(f"{api_url}/api/reviews/dravya/{selected}/approve",headers={"Cookie":f"{ACCESS_COOKIE}={access}"},json={"values":{}},timeout=5)
                if r.is_success: st.success("Approved. Public explorers will show this record after refresh."); st.rerun()
                else: st.error(r.json().get("detail", "Approval failed"))
        with c2:
            if st.button("Reject record"):
                if not reason.strip(): st.error("Provide a rejection reason.")
                else:
                    r=httpx.post(f"{api_url}/api/reviews/dravya/{selected}/reject",headers={"Cookie":f"{ACCESS_COOKIE}={access}"},json={"values":{"review_notes":reason}},timeout=5)
                    if r.is_success: st.success("Record rejected."); st.rerun()
                    else: st.error("Rejection failed.")
        return
    if route == "research":
        from frontend.pages.research_assistant import render_research_assistant
        render_research_assistant()
        return
    table, description = ENTITY[page]
    st.markdown(f"## {page}"); st.caption(description)
    search = st.text_input("Search", key=f"search_{table}")
    api_url = os.getenv("AYURFORM_API_URL", "http://127.0.0.1:8002").rstrip("/")
    try:
        response = httpx.get(f"{api_url}/api/{'anupana' if table == 'anupana_relationships' else 'passages' if table == 'source_passages' else table}", params={"search": search, "limit": 50}, timeout=5)
        response.raise_for_status()
        items = response.json().get("items", [])
    except httpx.HTTPError:
        st.error("The AyurForm API is unavailable. Start the FastAPI service or check AYURFORM_API_URL.")
        return
    if not items:
        st.info("No approved AyurForm records are available yet. Development-only corpus content is not presented as approved scholarly data.")
    else:
        for item in items:
            with st.expander(str(item.get("canonical_name") or item.get("title") or item.get("anupana_term"))): st.json(item)
