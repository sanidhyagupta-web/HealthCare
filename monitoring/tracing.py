"""
LangSmith tracing setup.
Call configure_tracing() once at process startup (run.py, streamlit_app.py).
After that, @traceable decorators activate automatically.
"""
from __future__ import annotations
import os
import logging

logger = logging.getLogger(__name__)

_active = False


def configure_tracing() -> bool:
    """Enable LangSmith if LANGSMITH_API_KEY is set. Returns True when active."""
    global _active
    from app.config import settings

    if not settings.langsmith_api_key:
        logger.info("LangSmith disabled — set LANGSMITH_API_KEY in .env to enable")
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

    _active = True
    logger.info("LangSmith tracing active → project=%s", settings.langsmith_project)
    return True


def is_active() -> bool:
    return _active


def _add_metadata(metadata: dict) -> None:
    """Add metadata to the current LangSmith run (no-op if tracing is off)."""
    if not _active:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree
        rt = get_current_run_tree()
        if rt is not None:
            rt.add_metadata(metadata)
    except Exception:
        pass
