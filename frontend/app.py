"""Operational dashboard and knowledge-base chat application."""

import os
from datetime import datetime
from typing import Any

import streamlit as st

from client import APIClient, APIError

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MCP_HEALTH_URL = os.getenv("MCP_HEALTH_URL", "http://localhost:8001/health")


def format_bytes(value: int) -> str:
    """Render byte counts for operators."""
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def authenticate() -> None:
    """Render login and registration until an access token is available."""
    st.title("Agentic RAG Knowledge Assistant")
    st.caption("Secure, owner-scoped document intelligence backed by PostgreSQL and pgvector.")
    
    client = APIClient(BACKEND_URL)
    
    # Switchable tabs for login and registration
    login_tab, register_tab = st.tabs(["Sign in", "Create account"])
    
    # render Login Layout
    with login_tab, st.form("login"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.form_submit_button("Sign in", type="primary", use_container_width=True):
            try:
                st.session_state.token = client.login(email, password)
                st.rerun()
            except APIError as exc:
                st.error(str(exc))
    
    # render Registration Layout
    with register_tab, st.form("register"):
        username = st.text_input("Username")
        email = st.text_input("Email", key="register_email")
        password = st.text_input("Password", type="password", key="register_password")
        if st.form_submit_button("Create account", use_container_width=True):
            try:
                client.register(username, email, password)
                st.success("Account created. Sign in to continue.")
            except APIError as exc:
                st.error(str(exc))


def render_overview(client: APIClient) -> None:
    """
        Render current knowledge-base and conversation totals.
        The metrics include:
        - Indexed documents
        - Vector chunks
        - Storage
        - Conversations
        - Messages
        - Processing documents
        - Failed documents
        - Active ingestion jobs
        - Failed ingestion jobs
        Which indicate:
        - How much knowledge is indexed?
        - How many chunks exist?
        - Are documents processing?
        - Have jobs failed?
        - How active is the system?
    """
    st.subheader("Overview")
    metrics = client.metrics()
    knowledge = metrics["knowledge_base"]
    activity = metrics["activity"]
    columns = st.columns(4)
    columns[0].metric("Indexed documents", knowledge["indexed_documents"])
    columns[1].metric("Vector chunks", knowledge["indexed_chunks"])
    columns[2].metric("Storage", format_bytes(knowledge["stored_bytes"]))
    columns[3].metric("Conversations", activity["threads"])
    st.divider()
    second = st.columns(5)
    second[0].metric("Messages", activity["messages"])
    second[1].metric("Processing", knowledge["processing_documents"])
    second[2].metric("Failed documents", knowledge["failed_documents"])
    second[3].metric("Active ingestion jobs", activity["active_ingestion_jobs"])
    second[4].metric("Failed ingestion jobs", activity["failed_ingestion_jobs"])
    # Get the last indexed timestamp and format it for display
    last_indexed = knowledge.get("last_indexed_at")
    formatted_last_indexed = (
        datetime.fromisoformat(last_indexed).astimezone().strftime("%d %b %Y, %H:%M")
        if last_indexed
        else None
    )
    st.caption(
        f"Last indexed: {formatted_last_indexed}"
        if formatted_last_indexed
        else "No documents have been indexed yet."
    )


def render_health(client: APIClient) -> None:
    """Render live process and PostgreSQL readiness probes."""
    st.subheader("System health")
    live, live_ms = client.health("/health/live")
    ready, ready_ms = client.health("/health/ready")
    mcp, mcp_ms = client.service_health(MCP_HEALTH_URL)
    left, middle, right = st.columns(3)
    left.metric("API process", "Healthy" if live else "Unavailable", f"{live_ms:.0f} ms")
    middle.metric(
        "PostgreSQL + pgvector",
        "Ready" if ready else "Unavailable",
        f"{ready_ms:.0f} ms",
    )
    right.metric("MCP server", "Ready" if mcp else "Unavailable", f"{mcp_ms:.0f} ms")
    if live and ready and mcp:
        st.success("The API, database, and MCP server are accepting requests.")
    else:
        st.error("One or more required services are unavailable.")


def render_knowledge_base(client: APIClient, threads: list[dict[str, Any]]) -> None:
    """Manage uploads and inspect owner-scoped PostgreSQL document state."""
    st.subheader("Knowledge base")
    st.caption("Uploads are validated, chunked, embedded, and stored in PostgreSQL with pgvector.")
    with st.container(border=True):
        heading, action = st.columns([4, 1])
        heading.markdown("#### Google Drive folder")
        heading.caption(
            "Synchronize supported business documents from the folder configured by the server. "
            "Unchanged files are skipped and duplicate content reuses the existing index."
        )
        if action.button("Sync now", type="primary", use_container_width=True):
            try:
                with st.spinner("Discovering, parsing, and embedding Drive documents..."):
                    st.session_state.drive_sync_summary = client.sync_google_drive()
                st.rerun()
            except APIError as exc:
                st.error(str(exc))
        if summary := st.session_state.get("drive_sync_summary"):
            columns = st.columns(6)
            for column, label, key in zip(
                columns,
                ("Discovered", "Indexed", "Unchanged", "Duplicates", "Skipped", "Failed"),
                ("discovered", "indexed", "unchanged", "duplicates", "skipped", "failed"),
                strict=True,
            ):
                column.metric(label, int(summary[key]))

    st.markdown("#### Upload a document")
    thread_options = {"All conversations": ""} | {
        f"{thread['title']} · {str(thread['id'])[:8]}": str(thread["id"]) for thread in threads
    }
    with st.form("upload_document"):
        uploaded = st.file_uploader("Document", type=["pdf", "docx", "txt"])
        scope = st.selectbox("Conversation scope", options=list(thread_options))
        submitted = st.form_submit_button("Upload and index", type="primary")
        if submitted and uploaded is not None:
            try:
                result = client.upload(
                    uploaded.name,
                    uploaded.getvalue(),
                    uploaded.type or "application/octet-stream",
                    thread_options[scope],
                )
                if result["duplicate"]:
                    st.info("This document is already indexed for your account.")
                else:
                    st.success(f"Indexed {result['chunks_created']} chunks from {uploaded.name}.")
                    st.rerun()
            except APIError as exc:
                st.error(str(exc))
    documents = client.documents()
    if not documents:
        st.info("No documents are indexed yet.")
        return
    st.markdown("#### Indexed documents")
    for document in documents:
        name, status, size, action = st.columns([4, 2, 2, 1])
        name.write(document["display_name"])
        status.write(str(document["status"]).title())
        size.write(format_bytes(int(document["file_size"])))
        if action.button("Delete", key=f"delete-{document['id']}"):
            try:
                client.delete_document(str(document["id"]))
                st.rerun()
            except APIError as exc:
                st.error(str(exc))


def render_sources(sources: list[dict[str, Any]]) -> None:
    """Render server-validated citations under an assistant response."""
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})"):
        for source in sources:
            page = f", page {source['page_number']}" if source.get("page_number") else ""
            st.markdown(f"**{source['document_name']}**{page} · similarity {source['score']:.2f}")
            st.caption(str(source["excerpt"]))


def render_agent(client: APIClient, threads: list[dict[str, Any]]) -> None:
    """Render persisted thread selection and grounded chat."""
    st.subheader("AI agent")
    if not threads:
        st.info("Create a conversation to start chatting with your knowledge base.")
        if st.button("Create conversation", type="primary"):
            client.create_thread("Knowledge base conversation")
            st.rerun()
        return
    labels = {
        str(thread["id"]): f"{thread['title']} · {str(thread['id'])[:8]}" for thread in threads
    }
    selector, creator = st.columns([3, 2])
    thread_id = selector.selectbox(
        "Conversation",
        options=list(labels),
        format_func=lambda option: labels[option],
        label_visibility="collapsed",
    )
    with creator.popover("New conversation", use_container_width=True):
        title = st.text_input("Title", value="Knowledge base conversation")
        if st.button("Create", type="primary"):
            try:
                client.create_thread(title)
                st.rerun()
            except APIError as exc:
                st.error(str(exc))
    for message in client.history(thread_id):
        with st.chat_message(str(message["role"])):
            st.write(message["content"])
            if message["role"] == "assistant":
                render_sources(list(message.get("sources", [])))
    if question := st.chat_input("Ask about your indexed documents"):
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"), st.spinner("Searching the knowledge base..."):
            try:
                placeholder = st.empty()
                answer = ""
                completed: dict[str, Any] | None = None
                for event, payload in client.stream_chat(thread_id, question):
                    if event == "token":
                        answer += str(payload)
                        placeholder.markdown(f"{answer}▌")
                    elif event == "complete" and isinstance(payload, dict):
                        completed = payload
                    elif event == "error" and isinstance(payload, dict):
                        raise APIError(str(payload.get("message", "Agent request failed")))
                placeholder.markdown(answer)
                if completed is not None:
                    render_sources(list(completed["sources"]))
            except APIError as exc:
                st.error(str(exc))


def main() -> None:
    """Run the authenticated dashboard."""
    st.set_page_config(page_title="Agentic RAG", page_icon="◈", layout="wide")
    if not st.session_state.get("token"):
        authenticate()
        return
    client = APIClient(BACKEND_URL, str(st.session_state.token))
    
    # 
    try:
        user = client.current_user()
        print(user)
    except APIError:
        st.session_state.pop("token", None)
        st.rerun()
        return
    
    with st.sidebar:
        st.title("Agentic RAG")
        st.write(user["username"])
        st.caption(user["email"])
        if st.button("Sign out", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    try:
        threads = client.threads()
        overview, health, knowledge, agent = st.tabs(
            ["Overview", "Health", "Knowledge Base", "AI Agent"]
        )
        with overview:
            render_overview(client)
        with health:
            render_health(client)
        with knowledge:
            render_knowledge_base(client, threads)
        with agent:
            render_agent(client, threads)
    except APIError as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
