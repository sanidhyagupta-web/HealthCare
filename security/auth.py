"""Session-based authentication for the Streamlit app."""
from __future__ import annotations
import hashlib
import streamlit as st

# Prototype user store — replace with a real DB in production
_USERS: dict[str, dict] = {
    "admin": {
        "password_hash": hashlib.sha256(b"admin123").hexdigest(),
        "role": "admin",
        "department": "general",
        "display_name": "Admin User",
    },
    "dr_smith": {
        "password_hash": hashlib.sha256(b"doctor123").hexdigest(),
        "role": "doctor",
        "department": "cardiology",
        "display_name": "Dr. Smith",
    },
    "nurse_jones": {
        "password_hash": hashlib.sha256(b"nurse123").hexdigest(),
        "role": "nurse",
        "department": "general",
        "display_name": "Nurse Jones",
    },
    "radiologist_lee": {
        "password_hash": hashlib.sha256(b"radio123").hexdigest(),
        "role": "radiologist",
        "department": "radiology",
        "display_name": "Dr. Lee (Radiology)",
    },
    "billing_dept": {
        "password_hash": hashlib.sha256(b"billing123").hexdigest(),
        "role": "billing",
        "department": "billing",
        "display_name": "Billing Department",
    },
}


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def login(username: str, password: str) -> bool:
    user = _USERS.get(username.strip())
    if not user or user["password_hash"] != _hash(password):
        return False
    st.session_state.update({
        "authenticated": True,
        "username": username.strip(),
        "role": user["role"],
        "department": user["department"],
        "display_name": user["display_name"],
    })
    return True


def logout() -> None:
    for key in ["authenticated", "username", "role", "department", "display_name"]:
        st.session_state.pop(key, None)


def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def current_user() -> dict | None:
    if not is_authenticated():
        return None
    return {
        "username": st.session_state["username"],
        "role": st.session_state["role"],
        "department": st.session_state["department"],
        "display_name": st.session_state["display_name"],
    }
