"""Browser-side authentication forms and profile view."""
from __future__ import annotations

import json
import os
from html import escape

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from auth_service import CSRF_COOKIE

AUTH_API_URL = os.getenv("AYURSUTRA_AUTH_API_URL", "http://localhost:8000").rstrip("/")


def _auth_styles() -> None:
    st.html("""<style>.auth-shell{min-height:calc(100vh - 7rem);display:grid;place-items:center;padding:1.2rem}.auth-card{width:min(100%,460px);background:#fff;border:1px solid #E3E9E2;border-radius:18px;padding:clamp(1.3rem,4vw,2rem);box-shadow:0 12px 30px rgba(16,55,45,.08)}.auth-mark{color:#174C3C;font:700 .75rem 'DM Sans',sans-serif;letter-spacing:.13em}.auth-card h1{font:600 2rem/1.12 'Playfair Display',serif;color:#10372D;margin:.5rem 0}.auth-card p{color:#64736A;line-height:1.55}.auth-card label{display:block;color:#1D2E26;font:600 .82rem 'DM Sans',sans-serif;margin:.95rem 0 .38rem}.auth-card input{box-sizing:border-box;width:100%;border:1px solid #C7D3C9;border-radius:9px;padding:.72rem .8rem;font:400 .95rem 'DM Sans',sans-serif;color:#1D2E26;background:#fff}.auth-password-row{display:flex;gap:.55rem}.auth-password-row input{min-width:0}.auth-toggle{border:1px solid #C7D3C9;border-radius:9px;background:#fff;color:#174C3C;padding:.5rem .65rem;font:600 .75rem 'DM Sans',sans-serif;cursor:pointer}.auth-submit{width:100%;margin-top:1.3rem;border:1px solid #174C3C;border-radius:10px;background:#174C3C;color:#fff;padding:.78rem 1rem;font:600 .92rem 'DM Sans',sans-serif;cursor:pointer}.auth-submit:disabled{opacity:.65;cursor:wait}.auth-status{min-height:1.2rem;margin:.8rem 0 0;color:#64736A;font:.82rem/1.45 'DM Sans',sans-serif}.auth-status.error{color:#A13B3B}.auth-switch{font-size:.83rem;color:#64736A;margin-top:1.05rem}.auth-switch a{color:#174C3C;font-weight:700}.profile-card{max-width:640px;border:1px solid #E3E9E2;border-radius:16px;background:#fff;padding:1.35rem;box-shadow:0 5px 16px rgba(16,55,45,.04)}</style>""")


def _form_script(mode: str) -> str:
    endpoint = "/auth/login" if mode == "login" else "/auth/signup"
    body = "{email:data.email,password:data.password}" if mode == "login" else "{full_name:data.full_name,email:data.email,password:data.password}"
    status_text = "Signing you in…" if mode == "login" else "Creating your account…"
    script = """<script>(()=>{const form=document.getElementById('ayur-__MODE__-form');if(!form||form.dataset.bound)return;form.dataset.bound='1';const status=document.getElementById('ayur-__MODE__-status'),submit=form.querySelector('button[type=submit]');const say=(text,error=false)=>{status.textContent=text;status.className='auth-status'+(error?' error':'')};const toggle=form.querySelector('[data-password-toggle]'),password=form.querySelector('[name=password]');toggle?.addEventListener('click',()=>{const show=password.type==='password';password.type=show?'text':'password';toggle.textContent=show?'Hide':'Show'});form.addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));if(!data.email||!data.password)return say('Enter your email and password.',true);if('confirm_password'in data&&data.password!==data.confirm_password)return say('Passwords do not match.',true);if('full_name'in data&&!data.full_name.trim())return say('Enter your full name.',true);submit.disabled=true;say('__STATUS__');const body=__BODY__;try{const response=await fetch('__API____ENDPOINT__',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload?.detail?.message||'Unable to complete this request.');say('Success. Reloading…');window.location.replace('/')}catch(error){say(error.message||'Unable to complete this request.',true);submit.disabled=false}})})();</script>"""
    return script.replace("__MODE__", mode).replace("__STATUS__", status_text).replace("__BODY__", body).replace("__API__", escape(AUTH_API_URL, quote=True)).replace("__ENDPOINT__", endpoint)


def _auth_form(mode: str, unavailable: bool) -> str:
    status = "The authentication service is unavailable. Please try again shortly." if unavailable else ""
    cls = "auth-status error" if unavailable else "auth-status"
    if mode == "login":
        form = '<label>Email<input name="email" type="email" autocomplete="email" required></label><label>Password</label><div class="auth-password-row"><input name="password" type="password" autocomplete="current-password" required><button class="auth-toggle" type="button" data-password-toggle>Show</button></div><button class="auth-submit" type="submit">Log in</button>'
        title, copy, switch = "Welcome back", "Sign in to continue to your AyurForm research workspace.", 'New to AyurForm? <a href="?auth=signup">Create an account</a>'
    else:
        form = '<label>Full name<input name="full_name" type="text" autocomplete="name" maxlength="120" required></label><label>Email<input name="email" type="email" autocomplete="email" required></label><label>Password</label><div class="auth-password-row"><input name="password" type="password" autocomplete="new-password" required><button class="auth-toggle" type="button" data-password-toggle>Show</button></div><label>Confirm password<input name="confirm_password" type="password" autocomplete="new-password" required></label><button class="auth-submit" type="submit">Create account</button>'
        title, copy, switch = "Create your account", "Save your workspace identity before personalised records are enabled.", 'Already have an account? <a href="?auth=login">Log in</a>'
    return '<main class="auth-shell"><section class="auth-card"><div class="auth-mark">◈ AYURFORM AI</div><h1>'+title+'</h1><p>'+copy+'</p><form id="ayur-'+mode+'-form" novalidate>'+form+'<div id="ayur-'+mode+'-status" class="'+cls+'">'+escape(status)+'</div></form><div class="auth-switch">'+switch+'</div></section></main>'+_form_script(mode)


def render_login(unavailable: bool = False) -> None:
    _auth_styles()
    st.html(_auth_form("login", unavailable), unsafe_allow_javascript=True)


def render_signup(unavailable: bool = False) -> None:
    _auth_styles()
    st.html(_auth_form("signup", unavailable), unsafe_allow_javascript=True)


def render_profile(user: dict) -> None:
    _auth_styles()
    email = escape(str(user.get("email", "")))
    created = escape(str(user.get("created_at", "Not available")))
    initial = escape(json.dumps(str(user.get("full_name", ""))), quote=True)
    api, csrf = escape(AUTH_API_URL, quote=True), escape(CSRF_COOKIE, quote=True)
    html = """<section class="profile-card"><p><b>Email</b><br>__EMAIL__</p><p><b>Account created</b><br>__CREATED__</p><form id="ayur-profile-form"><label>Full name<input name="full_name" value=__INITIAL__ maxlength="120" required></label><button class="auth-submit" type="submit">Save name</button><div id="ayur-profile-status" class="auth-status"></div></form></section><script>(()=>{const form=document.getElementById('ayur-profile-form');if(!form||form.dataset.bound)return;form.dataset.bound='1';const status=document.getElementById('ayur-profile-status'),csrf=()=>document.cookie.split('; ').find(row=>row.startsWith('__CSRF__='))?.split('=').slice(1).join('');form.addEventListener('submit',async event=>{event.preventDefault();const fullName=new FormData(form).get('full_name').trim();if(!fullName){status.textContent='Enter your full name.';status.className='auth-status error';return}try{const token=csrf();if(!token)throw new Error('Your session needs a browser reload.');const response=await fetch('__API__/auth/me',{method:'PATCH',credentials:'include',headers:{'Content-Type':'application/json','X-CSRF-Token':token},body:JSON.stringify({full_name:fullName})}),payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload?.detail?.message||'Unable to update your profile.');status.textContent='Saved. Reloading…';window.location.reload()}catch(error){status.textContent=error.message||'Unable to update your profile.';status.className='auth-status error'}})})();</script>"""
    st.html(html.replace("__EMAIL__", email).replace("__CREATED__", created).replace("__INITIAL__", initial).replace("__API__", api).replace("__CSRF__", csrf), unsafe_allow_javascript=True)


def render_logout_control() -> None:
    api, csrf = escape(AUTH_API_URL, quote=True), escape(CSRF_COOKIE, quote=True)
    html = """<button id="ayur-logout" style="width:100%;min-height:42px;border:1px solid #C7D3C9;border-radius:10px;background:#fff;color:#10372D;font-weight:600;cursor:pointer">Log out</button><script>(()=>{const button=document.getElementById('ayur-logout');if(!button||button.dataset.bound)return;button.dataset.bound='1';const csrf=()=>document.cookie.split('; ').find(row=>row.startsWith('__CSRF__='))?.split('=').slice(1).join('');button.addEventListener('click',async()=>{button.disabled=true;try{const token=csrf();await fetch('__API__/auth/logout',{method:'POST',credentials:'include',headers:{'X-CSRF-Token':token||''}})}finally{window.location.replace('/?auth=login')}})})();</script>"""
    st.html(html.replace("__API__", api).replace("__CSRF__", csrf), unsafe_allow_javascript=True)
