"""Temporary local-development browser cookie integration test UI."""
from __future__ import annotations

import os
from html import escape

import streamlit as st

from auth_api import COOKIE_NAME


def _enabled() -> bool:
    return (
        os.getenv("AYURSUTRA_ENV", "").casefold() == "development"
        and os.getenv("AYURSUTRA_ENABLE_DEV_COOKIE_TEST") == "1"
        and os.getenv("AYURSUTRA_DEV_COOKIE_SECURE") == "0"
    )


def render_dev_cookie_test() -> None:
    if not _enabled():
        return

    try:
        cookie_present = COOKIE_NAME in st.context.cookies
    except Exception:
        cookie_present = False

    st.markdown("### Local browser cookie integration test")
    st.caption("Development only. This marker is random and is not an authentication token.")
    st.markdown(
        f"**Streamlit handshake cookie:** {'Detected' if cookie_present else 'Not detected'}"
    )
    st.info(
        "After setting or clearing the marker, reload this page in the browser. "
        "Streamlit reads cookies from the WebSocket handshake; st.rerun() does not refresh that snapshot."
    )

    api_url = "http://localhost:8000"
    name = escape(COOKIE_NAME, quote=True)
    url = escape(api_url, quote=True)
    st.html(
        f"""<section style="border:1px solid #E3E9E2;border-radius:14px;background:#fff;padding:18px;color:#1D2E26">
          <p style="margin:0 0 12px;color:#64736A">FastAPI endpoint: <code>{url}/auth/dev-cookie-test</code></p>
          <div style="display:flex;flex-wrap:wrap;gap:8px">
            <button type="button" id="ayur-cookie-set">Set test cookie</button>
            <button type="button" id="ayur-cookie-check">Check browser request</button>
            <button type="button" id="ayur-cookie-clear">Clear test cookie</button>
            <button type="button" id="ayur-cookie-reload">Reload this page</button>
          </div>
          <p id="ayur-cookie-result" role="status" aria-live="polite" style="margin:12px 0 0;color:#174C3C">Ready.</p>
        </section>
        <script>
        (() => {{
          const api = "{url}";
          const marker = "{name}";
          const result = document.getElementById("ayur-cookie-result");
          const say = value => {{ if (result) result.textContent = value; }};
          const request = async (path, method) => {{
            const response = await fetch(api + path, {{method, credentials: "include", headers: {{"Content-Type": "application/json"}}}});
            let body = {{}};
            try {{ body = await response.json(); }} catch (_) {{}}
            if (!response.ok) throw new Error("FastAPI returned HTTP " + response.status);
            return body;
          }};
          document.getElementById("ayur-cookie-set").addEventListener("click", async () => {{
            try {{
              await request("/auth/dev-cookie-test", "POST");
              const readable = document.cookie.split(";").some(part => part.trim().startsWith(marker + "="));
              say("FastAPI set the marker. Browser JavaScript can read it: " + (readable ? "yes (unexpected)" : "no (HttpOnly behavior)") + ". Reload the page to check Streamlit's handshake cookie.");
            }} catch (error) {{ say("Cookie set failed: " + error.message + ". Confirm both local services are running at localhost."); }}
          }});
          document.getElementById("ayur-cookie-check").addEventListener("click", async () => {{
            try {{
              const body = await request("/auth/dev-cookie-test", "GET");
              say("FastAPI received the marker cookie: " + (body.cookie_received ? "yes" : "no") + ".");
            }} catch (error) {{ say("Cookie check failed: " + error.message); }}
          }});
          document.getElementById("ayur-cookie-clear").addEventListener("click", async () => {{
            try {{
              await request("/auth/dev-cookie-test/clear", "POST");
              say("FastAPI cleared the marker. Reload the page to confirm Streamlit no longer sees it.");
            }} catch (error) {{ say("Cookie clear failed: " + error.message); }}
          }});
          document.getElementById("ayur-cookie-reload").addEventListener("click", () => window.location.reload());
        }})();
        </script>
        <style>
        #ayur-cookie-set,#ayur-cookie-check,#ayur-cookie-clear,#ayur-cookie-reload{{border:1px solid #C7D3C9;border-radius:9px;background:#fff;color:#10372D;padding:9px 13px;font:600 14px 'DM Sans',sans-serif;cursor:pointer}}
        #ayur-cookie-set{{background:#174C3C;border-color:#174C3C;color:#fff}}
        #ayur-cookie-set:hover{{background:#10372D}}#ayur-cookie-check:hover,#ayur-cookie-clear:hover,#ayur-cookie-reload:hover{{background:#EDF3EC;border-color:#A9BFA9}}
        </style>""",
        unsafe_allow_javascript=True,
    )
