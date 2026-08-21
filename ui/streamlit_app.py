import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from db.database import init_db
from security.auth import is_authenticated, current_user, logout

st.set_page_config(
    page_title="Healthcare Semantic Search",
    page_icon="🏥",
    layout="wide",
)

init_db()

# ── Authentication gate ───────────────────────────────────────────────────────
if not is_authenticated():
    from ui.login_page import render as login_render
    login_render()
    st.stop()

# ── Authenticated shell ───────────────────────────────────────────────────────
user = current_user()

PAGES = {
    "Search Records": "search",
    "Upload Documents": "upload",
    "Bulk Upload": "bulk_upload",
    "Audit Log": "audit",
}

with st.sidebar:
    st.title("Healthcare Semantic Search")
    st.markdown("---")

    # User info
    st.markdown(f"**{user['display_name']}**")
    st.caption(f"Role: `{user['role']}` | Dept: `{user['department']}`")
    st.markdown("---")

    page = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    st.markdown("---")

    if st.button("Sign Out", use_container_width=True):
        logout()
        st.rerun()

    st.caption("HIPAA-aware RAG pipeline")

# ── Page routing ──────────────────────────────────────────────────────────────
if PAGES[page] == "search":
    from ui.search_page import render
    render()
elif PAGES[page] == "upload":
    from ui.upload_page import render
    render()
elif PAGES[page] == "bulk_upload":
    from ui.bulk_upload_page import render
    render()
elif PAGES[page] == "audit":
    from ui.audit_page import render
    render()
