"""Streamlit login page."""
from __future__ import annotations
import streamlit as st
from security.auth import login


def render() -> None:
    st.title("Healthcare Semantic Search")
    st.subheader("Sign in to continue")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                elif login(username, password):
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        with st.expander("Demo credentials"):
            st.code(
                "admin            / admin123\n"
                "dr_smith         / doctor123\n"
                "nurse_jones      / nurse123\n"
                "radiologist_lee  / radio123\n"
                "billing_dept     / billing123"
            )
