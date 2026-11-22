"""AyurSutra design tokens and global Streamlit theme."""
import streamlit as st

TOKENS = {"forest":"#174C3C","deep":"#10372D","green":"#287557","sage":"#A9BFA9","light_sage":"#EDF3EC","background":"#F6F8F4","surface":"#FFFFFF","text":"#1D2E26","secondary":"#64736A","border":"#E3E9E2","gold":"#C3A36A"}

def apply_theme():
    st.html('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');
:root{--forest:#174C3C;--deep:#10372D;--green:#287557;--sage:#A9BFA9;--sage-light:#EDF3EC;--page:#F6F8F4;--surface:#fff;--ink:#1D2E26;--secondary:#64736A;--muted:#87928A;--line:#E3E9E2;--gold:#C3A36A;--r-sm:10px;--r-md:14px;--r-lg:18px;--shadow:0 8px 24px rgba(16,55,45,.06)}
html,body,.stApp,[data-testid=stAppViewContainer],[data-testid=stMain]{background:var(--page)!important;color:var(--ink)!important;font-family:'DM Sans',sans-serif!important}
[data-testid=stHeader]{background:transparent!important}[data-testid=stToolbar]{visibility:visible!important}[data-testid=stFooter]{display:none!important}
/* Keep Streamlit's native header/sidebar controls; remove the default oversized gap below it. */
[data-testid="stMainBlockContainer"]{padding-top:2.75rem!important}
/* Sidebar identity and navigation styling are isolated in frontend.navigation. */
h1,h2,h3,h4{color:var(--deep)!important;font-family:'Playfair Display',serif!important;font-weight:600!important;letter-spacing:-.025em!important}h1{font-size:2.15rem!important;line-height:1.2!important}p,li,label{color:var(--ink)!important;line-height:1.65}[data-testid=stCaptionContainer]{color:var(--secondary)!important}
.stButton>button{min-height:42px;border-radius:10px!important;border:1px solid #C7D3C9!important;background:#fff!important;color:var(--deep)!important;font-weight:600!important;transition:all .16s ease!important}.stButton>button[kind=primary]{background:var(--forest)!important;border-color:var(--forest)!important;color:#fff!important}[data-testid=stMain] .stButton>button[kind=primary] p{color:#fff!important}[data-testid=stSidebar] .stButton>button[kind=primary] p{color:var(--deep)!important}.stButton>button:hover{border-color:var(--green)!important;background:var(--sage-light)!important;color:var(--deep)!important}.stButton>button[kind=primary]:hover{background:var(--deep)!important;color:#fff!important}
.shell-header{padding:.25rem 0 .9rem;border-bottom:1px solid var(--line);margin-bottom:1.4rem}.shell-crumb{font-size:.75rem;color:var(--secondary)}.shell-desc{color:var(--secondary)!important;max-width:760px;margin-top:-.35rem}.shell-placeholder{border:1px solid var(--line);border-radius:var(--r-lg);background:#fff;padding:1.5rem 1.6rem;box-shadow:var(--shadow);max-width:760px}
@media(max-width:800px){h1{font-size:1.8rem!important}.block-container{padding:1rem!important}[data-testid="stMainBlockContainer"]{padding-top:2.5rem!important}}@media(max-width:520px){h1{font-size:1.55rem!important}.shell-placeholder{padding:1rem}}
</style>''')
