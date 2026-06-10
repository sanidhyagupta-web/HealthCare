from __future__ import annotations

import streamlit as st

from security.audit_logger import get_audit_trail
from queues import dlq


def render():
    st.header("Audit Log")

    tab1, tab2 = st.tabs(["Access & Events", "Dead Letter Queue"])

    with tab1:
        col1, col2 = st.columns([2, 1])
        with col1:
            doc_filter = st.text_input("Filter by Doc ID (optional)")
        with col2:
            limit = st.number_input("Max rows", min_value=10, max_value=500, value=50, step=10)

        if st.button("Refresh", key="refresh_audit"):
            st.rerun()

        events = get_audit_trail(doc_id=doc_filter or None, limit=int(limit))

        if not events:
            st.info("No audit events found.")
        else:
            st.caption(f"Showing {len(events)} events (newest first)")

            rows = []
            for e in events:
                rows.append({
                    "Timestamp": e.get("timestamp", "—"),
                    "Event": e.get("event_type", "—"),
                    "User": e.get("user_id", "—"),
                    "Doc ID": (e.get("doc_id") or "—")[:14] + ("…" if e.get("doc_id") and len(e.get("doc_id", "")) > 14 else ""),
                    "Query": (e.get("query") or "—")[:60],
                    "Details": str(e.get("details") or ""),
                })

            st.dataframe(rows, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Dead Letter Queue")
        st.caption("Documents that failed after all retries are recorded here.")

        if st.button("Refresh DLQ", key="refresh_dlq"):
            st.rerun()

        messages = dlq.list_messages()

        if not messages:
            st.success("DLQ is empty — no failed documents.")
        else:
            st.warning(f"{len(messages)} message(s) in DLQ")
            for msg in messages:
                with st.expander(
                    f"doc_id={msg.get('doc_id', '—')[:12]}… "
                    f"| source={msg.get('dlq_source', '—')} "
                    f"| {msg.get('dlq_timestamp', '')[:19]}",
                    expanded=False,
                ):
                    st.write("**Reason:**", msg.get("dlq_reason", "unknown"))
                    st.write("**Source queue:**", msg.get("dlq_source", "—"))
                    st.json({k: v for k, v in msg.items()
                             if k not in ("dlq_reason", "dlq_source", "dlq_timestamp")})
