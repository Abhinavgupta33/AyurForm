"""AyurForm AI application shell."""
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from deployment_validate import validate_or_raise
from utils.diagnostics import configure_file_logging

validate_or_raise()
configure_file_logging()

from frontend.theme import apply_theme
from frontend.navigation import render_sidebar
from frontend.layout import render_page_header, render_phase_placeholder
from frontend.header import render_app_header
from frontend.pages.ayurform_dashboard import render_dashboard
from frontend.pages.ayurform_pages import render_ayurform_page
from frontend.dev_cookie_test import render_dev_cookie_test
from frontend.auth import current_authenticated_user
from frontend.auth_pages import render_login, render_signup, render_profile

st.set_page_config(
    page_title="AyurForm AI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()
auth_route = st.query_params.get("auth", "")
session = current_authenticated_user()
if not session.user:
    if auth_route == "signup":
        render_signup(session.unavailable)
    else:
        render_login(session.unavailable)
else:
    page = render_sidebar(session.user)
    if page == "Profile":
        render_app_header(page, session.user)
        render_profile(session.user)
    else:
        render_app_header(page, session.user)
        if page == "Dashboard":
            render_dashboard(session.user)
        elif page in {"Dravya Explorer", "Formulation Explorer", "Anupana Explorer", "Research Assistant", "Classical Sources", "Review Dashboard"}:
            render_ayurform_page(page)
        else:
            render_page_header(page)
            render_phase_placeholder(page)
            if page == "Settings":
                render_dev_cookie_test()
