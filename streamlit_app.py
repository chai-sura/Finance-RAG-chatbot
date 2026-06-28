"""
streamlit_app.py — VaultDesk, single-file deployable version.

This calls the RAG/SQL engine and auth functions DIRECTLY (in-process)
instead of going through the FastAPI backend over HTTP. That lets it deploy
as one service on Streamlit Community Cloud. The FastAPI code still exists
in the repo (app/main.py) as the "real API" architecture.
"""

import html
import streamlit as st

from app.utils.auth import verify_user
from app.services.rag import answer_question

ROLE_THEME = {
    "c-level":     ("Executive",   "#C9A227", "all company data across every department"),
    "finance":     ("Finance",     "#2D7D6E", "financial reports, expenses, and reimbursements"),
    "hr":          ("HR",          "#7C5CBF", "employee records, payroll, and attendance"),
    "marketing":   ("Marketing",   "#D9695A", "campaign performance and customer feedback"),
    "engineering": ("Engineering", "#3A6EA5", "architecture, processes, and operational guidelines"),
    "employee":    ("Employee",    "#5B6B7F", "general company policies, events, and FAQs"),
}

st.set_page_config(page_title="VaultDesk", page_icon="🔐", layout="wide")


def inject_css(accent="#2D7D6E"):
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family:'Inter',-apple-system,sans-serif; }}
    .stApp {{ background:#F7F8FA; color:#0F1729; }}
    .block-container {{ padding-top:1rem; max-width:980px; }}

    .vd-topbar {{ display:flex; align-items:center; justify-content:space-between;
        background:linear-gradient(135deg,{accent},#1B2A4A); border-radius:14px;
        padding:14px 22px; margin-bottom:18px; box-shadow:0 4px 18px rgba(15,23,41,0.10); }}
    .vd-brand {{ font-size:21px; font-weight:800; color:#fff; letter-spacing:-0.4px; }}
    .vd-user {{ color:#fff; font-size:14px; font-weight:600; opacity:0.95; }}

    .vd-hero {{ background:#fff; border:1px solid #E4E8EE; border-radius:16px;
        padding:26px 30px; margin-bottom:16px; box-shadow:0 4px 16px rgba(15,23,41,0.05); }}
    .vd-hero h1 {{ font-size:26px; font-weight:800; letter-spacing:-0.5px; margin:0 0 8px 0; color:#0F1729; }}
    .vd-hero p {{ color:#5B6B7F; font-size:15px; line-height:1.55; margin:0; max-width:660px; }}
    .vd-accent {{ color:{accent}; font-weight:600; }}

    .vd-cap {{ background:#fff; border:1px solid #E4E8EE; border-top:3px solid {accent};
        border-radius:13px; padding:16px 18px; height:100%; }}
    .vd-cap .ic {{ font-size:22px; }}
    .vd-cap h4 {{ margin:8px 0 5px 0; font-size:15px; font-weight:700; color:#0F1729; }}
    .vd-cap p {{ margin:0; color:#5B6B7F; font-size:13px; line-height:1.5; }}

    .vd-login-head {{ text-align:center; margin:4vh 0 2px 0; }}
    .vd-login-head h3 {{ font-size:22px; font-weight:700; color:#0F1729; margin:0 0 4px 0; }}
    .vd-login-head p {{ color:#5B6B7F; font-size:13.5px; margin:0; }}

    .stTextInput label, [data-testid="stWidgetLabel"] {{ color:#0F1729 !important; font-weight:600 !important; font-size:13px !important; }}
    .stTextInput input, .stTextInput input[type="password"] {{
        background:#fff !important; color:#0F1729 !important; -webkit-text-fill-color:#0F1729 !important;
        caret-color:#0F1729 !important; border:1px solid #D9DEE6 !important; border-radius:9px !important; }}
    .stButton button {{ background:{accent} !important; color:#fff !important; border:none !important;
        border-radius:9px !important; font-weight:600 !important; padding:7px 18px !important; }}
    .stButton button:hover {{ filter:brightness(1.07); }}

    .vd-chip {{ display:inline-block; background:{accent}14; color:{accent}; border:1px solid {accent};
        border-radius:999px; padding:5px 13px; font-size:13px; font-weight:600; margin:2px 0 12px 0; }}

    .vd-row {{ display:flex; align-items:flex-start; gap:10px; margin:10px 0; }}
    .vd-row.user {{ flex-direction:row-reverse; }}
    .vd-av {{ width:30px; height:30px; border-radius:50%; flex:0 0 30px;
        display:flex; align-items:center; justify-content:center; font-size:16px; }}
    .vd-av.bot {{ background:{accent}1f; border:1px solid {accent}55; }}
    .vd-av.user {{ background:#E7ECF3; border:1px solid #D9DEE6; }}
    .vd-bubble {{ max-width:74%; padding:12px 15px; border-radius:14px; font-size:14.5px;
        line-height:1.55; word-wrap:break-word; white-space:pre-wrap; }}
    .vd-bubble.bot {{ background:#FFFFFF; color:#0F1729; border:1px solid #E4E8EE;
        border-left:3px solid {accent}; border-radius:4px 14px 14px 14px;
        box-shadow:0 2px 10px rgba(15,23,41,0.04); }}
    .vd-bubble.user {{ background:{accent}; color:#FFFFFF; border-radius:14px 14px 4px 14px; }}
    .vd-src {{ margin-top:9px; padding-top:9px; border-top:1px solid #EEF1F5;
        font-size:11.5px; color:#6B7A8D; }}
    .vd-src b {{ color:#5B6B7F; font-weight:600; }}
    .vd-src span {{ display:block; margin:2px 0; }}

    [data-testid="stChatInput"], div[data-baseweb="textarea"], .stChatInput, .stChatInput > div {{
        background:#fff !important; border-radius:12px !important; }}
    [data-testid="stChatInput"] textarea, .stChatInput textarea, div[data-baseweb="textarea"] textarea {{
        background:#fff !important; color:#0F1729 !important; -webkit-text-fill-color:#0F1729 !important;
        caret-color:#0F1729 !important; }}
    [data-testid="stChatInput"] textarea::placeholder, .stChatInput textarea::placeholder {{ color:#9AA6B5 !important; }}

    #MainMenu, footer, header {{ visibility:hidden; }}
    .stTabs [data-baseweb="tab-list"] {{ gap:4px; background:#fff; border:1px solid #E4E8EE;
        border-radius:11px; padding:4px; margin-bottom:16px; }}
    .stTabs [data-baseweb="tab"] {{ font-weight:600; font-size:14px; color:#5B6B7F;
        border-radius:8px; padding:6px 18px; }}
    .stTabs [aria-selected="true"] {{ background:{accent}; color:#fff !important; }}
    </style>""", unsafe_allow_html=True)


if "role" not in st.session_state:
    st.session_state.role = None
    st.session_state.username = None
    st.session_state.messages = []


def do_signout():
    st.session_state.role = None
    st.session_state.username = None
    st.session_state.messages = []
    st.rerun()


def topbar(accent, username=None, show_signout=False, key_suffix=""):
    if show_signout:
        col1, col2 = st.columns([5, 1])
        with col1:
            right = f'<span class="vd-user">Hi, {html.escape(username)}</span>' if username else '<span class="vd-user">Secure internal assistant</span>'
            st.markdown(f'<div class="vd-topbar"><div class="vd-brand">🔐 VaultDesk</div>'
                        f'<div class="vd-right">{right}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.button("Sign out", key=f"signout_{key_suffix}"):
                do_signout()
    else:
        right = f'<span class="vd-user">Hi, {html.escape(username)}</span>' if username else '<span class="vd-user">Secure internal assistant</span>'
        st.markdown(f'<div class="vd-topbar"><div class="vd-brand">🔐 VaultDesk</div>'
                    f'<div class="vd-right">{right}</div></div>', unsafe_allow_html=True)


def bubble(m, accent):
    text = html.escape(m["content"])
    if m["role"] == "user":
        st.markdown(f'<div class="vd-row user"><div class="vd-av user">🧑</div>'
                    f'<div class="vd-bubble user">{text}</div></div>', unsafe_allow_html=True)
    else:
        src = ""
        if m.get("sources"):
            items = "".join(f"<span>• {html.escape(s)}</span>" for s in m["sources"])
            src = f'<div class="vd-src"><b>Sources</b>{items}</div>'
        st.markdown(f'<div class="vd-row bot"><div class="vd-av bot">🔐</div>'
                    f'<div class="vd-bubble bot">{text}{src}</div></div>', unsafe_allow_html=True)


def render_login():
    st.markdown('<div class="vd-login-head"><h3>Welcome to VaultDesk</h3>'
                '<p>Sign in to ask questions about company knowledge — scoped to your clearance.</p></div>',
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Sign in"):
            if not username or not password:
                st.warning("Enter both username and password.")
            else:
                # DIRECT call to the auth function (no HTTP / FastAPI).
                try:
                    user = verify_user(username, password)
                except Exception:
                    user = None
                if user:
                    st.session_state.role = user["role"]
                    st.session_state.username = username
                    label, _, scope = ROLE_THEME.get(user["role"], ("", "", "general information"))
                    st.session_state.messages = [{
                        "role": "assistant",
                        "content": f"Hi {username}! I'm VaultDesk. Ask me anything about {scope} — I'll only answer from documents your {label} clearance allows.",
                        "sources": []}]
                    st.rerun()
                else:
                    st.error("Invalid username or password.")


def render_home():
    role = st.session_state.role
    label, accent, scope = ROLE_THEME.get(role, ("", "#2D7D6E", "general information"))

    st.markdown(f'<div class="vd-hero"><h1>Welcome back, {html.escape(st.session_state.username)}.</h1>'
                f'<p>VaultDesk answers your questions from company documents and shows you only what '
                f'your role permits. You\'re signed in with <span class="vd-accent">{label} clearance</span> '
                f'— covering {scope}.</p></div>', unsafe_allow_html=True)

    caps = [("🔐", "Role-based access", "Every answer is filtered to your clearance, with an independent guard before generation."),
            ("💬", "Natural language", "Ask in plain English. VaultDesk understands intent and finds the relevant material."),
            ("📑", "Cited answers", "Responses come only from real company documents, each with its source.")]
    for col, (ic, h, p) in zip(st.columns(3), caps):
        with col:
            st.markdown(f'<div class="vd-cap"><div class="ic">{ic}</div><h4>{h}</h4><p>{p}</p></div>',
                        unsafe_allow_html=True)

    st.markdown(f'<div style="height:14px"></div><span class="vd-chip">● {label} Clearance</span>',
                unsafe_allow_html=True)

    for m in st.session_state.messages:
        bubble(m, accent)

    if prompt := st.chat_input("Ask about company knowledge..."):
        st.session_state.messages.append({"role": "user", "content": prompt, "sources": []})
        # Build recent history (exclude the message we just appended).
        hist = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
            if m["role"] in ("user", "assistant")
        ][-6:]
        # DIRECT call to the engine (no HTTP / FastAPI).
        try:
            result = answer_question(prompt, role=role, history=hist)
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "sources": result.get("sources", []),
            })
        except Exception:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Something went wrong answering that. Please try again.",
                "sources": []})
        st.rerun()


def render_about():
    st.markdown('<div class="vd-hero"><h1>About VaultDesk</h1>'
                '<p>VaultDesk is an internal assistant that answers questions from company documents '
                'while respecting role-based access — each person sees only what their clearance permits. '
                'It pairs retrieval-augmented generation with structured-query routing and secure, '
                'role-aware access control.</p></div>', unsafe_allow_html=True)
    caps = [("🔐", "Role-based access control", "Document chunks are tagged by department; retrieval is filtered to your role and re-checked by a guard. Access holds across both the document and database paths."),
            ("🗄️", "Structured-query routing", "Precise questions about employee data are answered with exact database queries, not fuzzy search."),
            ("📑", "Grounded, cited answers", "Generated only from retrieved documents, with sources — no hallucination."),
            ("📊", "Measured quality", "An evaluation framework scores faithfulness, relevance, and conciseness to validate the system.")]
    cols = st.columns(2)
    for i, (ic, h, p) in enumerate(caps):
        with cols[i % 2]:
            st.markdown(f'<div class="vd-cap"><div class="ic">{ic}</div><h4>{h}</h4><p>{p}</p></div>',
                        unsafe_allow_html=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


# route
accent = "#2D7D6E"
if st.session_state.role:
    _, accent, _ = ROLE_THEME.get(st.session_state.role, ("", "#2D7D6E", ""))
inject_css(accent)

topbar(accent,
       st.session_state.username if st.session_state.role else None,
       show_signout=bool(st.session_state.role),
       key_suffix="top")
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

tab_home, tab_about = st.tabs(["Home", "About"])
with tab_home:
    if st.session_state.role:
        render_home()
    else:
        render_login()
with tab_about:
    render_about()