"""Reusable presentation components shared across AyurSutra pages."""
import streamlit as st

def page_header(title, description, crumb="Workspace"):
    st.caption(f"{crumb}  /  {title}")
    st.title(title)
    st.markdown(f"<p class='ay-muted'>{description}</p>",unsafe_allow_html=True)

def metric_card(icon,label,value,detail):
    st.markdown(f"<div class='ay-card'><div style='display:flex;gap:.8rem;align-items:center'><span style='font-size:1.25rem;color:#287557'>{icon}</span><span class='ay-label'>{label}</span></div><div class='ay-metric'>{value}</div><div class='ay-label'>{detail}</div></div>",unsafe_allow_html=True)

def empty_state(title,description,icon='⌕'):
    st.markdown(f"<div class='ay-card' style='text-align:center;padding:2rem'><div style='font-size:1.5rem;color:#287557'>{icon}</div><b>{title}</b><p class='ay-muted'>{description}</p></div>",unsafe_allow_html=True)
