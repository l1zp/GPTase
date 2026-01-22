"""Main Streamlit application for conversation visualization."""

import asyncio
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st

# Configure page
st.set_page_config(
    page_title="GPTase Conversations",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


def get_storage():
    """Get or create conversation storage instance."""
    from src.conversations.storage import ConversationStorage

    if "storage" not in st.session_state:
        st.session_state.storage = ConversationStorage(
            db_path="data/conversations.db",
            enabled=True,
        )
        # Run async init in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(st.session_state.storage.initialize())
    return st.session_state.storage


def render_sidebar():
    """Render sidebar with navigation and stats."""
    storage = get_storage()

    with st.sidebar:
        st.title("🤖 GPTase")
        st.markdown("---")

        # Navigation
        page = st.radio(
            "Navigation",
            options=["Live View", "History", "Statistics", "Agent Sessions"],
        )

        st.markdown("---")

        # Quick stats
        st.subheader("📊 Quick Stats")
        stats = asyncio.run(storage.get_stats())

        if stats.get("tracking_enabled"):
            st.metric("Total Conversations", stats.get("total_conversations", 0))
            st.metric("Completed", stats.get("completed", 0))
            st.metric("Errors", stats.get("errors", 0))
            st.metric("Total Tokens", f"{stats.get('total_tokens', 0):,}")
        else:
            st.warning("Conversation tracking is disabled")

    return page


def show_live_view():
    """Display real-time streaming conversations."""
    st.title("🔴 Live Conversation View")

    storage = st.session_state.storage

    # Auto-refresh toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(
            "💡 This page shows conversations as they happen. "
            "Auto-refreshes every 2 seconds."
        )
    with col2:
        auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)

    st.markdown("---")

    # Get in-progress conversations
    conversations = asyncio.run(storage.list_conversations(limit=10))
    in_progress = [c for c in conversations if c["status"] == "in_progress"]

    if not in_progress:
        st.info("No active conversations. Start a chat to see it here live!")

        # Show recent completed conversations
        st.markdown("### Recently Completed")
        recent = [c for c in conversations if c["status"] == "completed"][:5]
        for conv in recent:
            with st.expander(f"💬 {conv['model_name']} - {conv['timestamp']}", expanded=False):
                full_conv = asyncio.run(storage.get_conversation(conv["id"]))
                if full_conv and full_conv["response"]:
                    st.markdown(f"**Response:** {full_conv['response'][2][:500]}...")
                    if full_conv["response"][6]:  # total_tokens
                        st.caption(f"Tokens: {full_conv['response'][6]}")
    else:
        for conv in in_progress:
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.subheader(f"💬 {conv['model_name']}")
                with col2:
                    st.markdown("🔴 **LIVE**")

                st.caption(f"Started: {conv['timestamp']}")
                st.caption(f"ID: `{conv['id'][:8]}...`")

                # Load and display what we have so far
                full_conv = asyncio.run(storage.get_conversation(conv["id"]))
                if full_conv:
                    # Messages
                    for msg in full_conv["messages"]:
                        with st.chat_message(msg[0]):
                            st.markdown(msg[1])

                    # Partial response (if any)
                    if full_conv["response"]:
                        resp = full_conv["response"]
                        if resp[3]:  # reasoning_content
                            with st.expander("🧠 Thinking", expanded=True):
                                st.markdown(resp[3])
                        if resp[2]:  # content
                            with st.chat_message("assistant"):
                                st.markdown(resp[2])
                                st.spinner("Generating...")

                st.markdown("---")

    # Auto-refresh
    if auto_refresh:
        import time

        time.sleep(2)
        st.rerun()


def show_history():
    """Display historical conversations with search and filtering."""
    st.title("📚 Conversation History")

    storage = st.session_state.storage

    # Search and filters
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        search_query = st.text_input("🔍 Search conversations", placeholder="Search by content...")

    with col2:
        status_filter = st.selectbox("Status", options=["All", "Completed", "In Progress", "Error"])

    with col3:
        limit = st.number_input("Show", min_value=10, max_value=500, value=50, step=10)

    # Load conversations
    if search_query:
        conversations = asyncio.run(storage.search_conversations(search_query, limit))
    else:
        conversations = asyncio.run(storage.list_conversations(limit=limit))

    # Apply status filter
    if status_filter != "All":
        conversations = [
            c for c in conversations if c["status"] == status_filter.lower().replace(" ", "_")
        ]

    st.markdown(f"**Found {len(conversations)} conversations**")
    st.markdown("---")

    # Display conversations
    for conv in conversations:
        with st.expander(
            f"💬 {conv['model_name']} - {conv['timestamp']} - {conv['status'].upper()}", expanded=False
        ):
            # Conversation metadata
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.write(f"**ID:** `{conv['id'][:8]}...`")
            with col2:
                st.write(f"**Model:** {conv['model_name']}")
            with col3:
                st.write(f"**Provider:** {conv['provider']}")
            with col4:
                if conv["agent_id"]:
                    st.write(f"**Agent:** {conv['agent_id']}")

            # Load and display messages
            full_conv = asyncio.run(storage.get_conversation(conv["id"]))
            if full_conv:
                st.markdown("### 📨 Messages")

                # Display input messages
                for msg in full_conv["messages"]:
                    with st.chat_message(msg[0]):
                        st.markdown(msg[1])

                # Display response
                if full_conv["response"]:
                    resp = full_conv["response"]
                    st.markdown("### 📤 Response")

                    if resp[3]:  # reasoning_content
                        with st.expander("🧠 Thinking Process", expanded=False):
                            st.markdown(resp[3])

                    st.markdown(resp[2])  # content

                    # Metadata
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if resp[6]:  # total_tokens
                            st.metric("Tokens", resp[6])
                    with col2:
                        if resp[7]:  # latency_seconds
                            st.metric("Latency", f"{resp[7]:.2f}s")
                    with col3:
                        if resp[6] and resp[7]:
                            st.metric("Tokens/sec", f"{resp[6] / resp[7]:.1f}")

    if not conversations:
        st.info("No conversations found. Start by running some GPTase agents!")


def show_stats():
    """Display statistics and analytics."""
    st.title("📊 Statistics & Analytics")

    storage = st.session_state.storage

    # Overall stats
    st.subheader("Overview")
    stats = asyncio.run(storage.get_stats())

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Conversations", stats.get("total_conversations", 0))
    with col2:
        success_rate = (
            (stats.get("completed", 0) / max(stats.get("total_conversations", 1), 1)) * 100
            if stats.get("total_conversations", 0) > 0
            else 0
        )
        st.metric("Success Rate", f"{success_rate:.1f}%")
    with col3:
        st.metric("Total Tokens", f"{stats.get('total_tokens', 0):,}")
    with col4:
        total_hours = stats.get("total_duration_seconds", 0) / 3600
        st.metric("Total Duration", f"{total_hours:.2f}h")

    st.markdown("---")

    # Model usage
    st.subheader("Model Usage")
    conversations = asyncio.run(storage.list_conversations(limit=1000))

    if conversations:
        # Count by model
        model_counts = {}
        for conv in conversations:
            model = conv["model_name"]
            model_counts[model] = model_counts.get(model, 0) + 1

        # Display as metrics
        cols = st.columns(min(len(model_counts), 4))
        for i, (model, count) in enumerate(model_counts.items()):
            with cols[i % len(cols)]:
                st.metric(model, count)

    st.markdown("---")

    # Recent activity
    st.subheader("Recent Activity")
    if conversations:
        # Group by date
        dates = {}
        for conv in conversations:
            date = conv["timestamp"][:10]  # YYYY-MM-DD
            dates[date] = dates.get(date, 0) + 1

        # Display as table
        for date, count in sorted(dates.items(), reverse=True)[:10]:
            st.write(f"**{date}:** {count} conversations")


def show_extraction_sessions():
    """Display agent sessions with workflow tracking."""
    from datetime import datetime
    from collections import defaultdict

    st.title("🤖 Agent Sessions")

    storage = get_storage()

    # View type selector
    view_type = st.radio(
        "View",
        options=["Extraction Sessions", "Agent Conversations"],
        horizontal=True,
    )

    st.markdown("---")

    if view_type == "Extraction Sessions":
        _show_extraction_sessions_view(storage)
    else:
        _show_agent_conversations_view(storage)


def _show_extraction_sessions_view(storage):
    """Display extraction sessions with workflow tracking."""
    from datetime import datetime
    from collections import defaultdict

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status_filter = st.selectbox(
            "Status",
            options=["All", "In Progress", "Completed", "Failed", "Partial"],
        )

    with col2:
        document_filter = st.text_input(
            "Filter by Document",
            placeholder="e.g., listov2025.md"
        )

    with col3:
        limit = st.number_input("Show", min_value=10, max_value=500, value=50, step=10)

    with col4:
        st.write("")  # spacing
        if st.button("🔄 Refresh", key="refresh_extraction"):
            st.rerun()

    st.markdown("---")

    # Map status filter to enum
    from src.conversations.models import ExtractionSessionStatus
    status_map = {
        "All": None,
        "In Progress": ExtractionSessionStatus.IN_PROGRESS,
        "Completed": ExtractionSessionStatus.COMPLETED,
        "Failed": ExtractionSessionStatus.FAILED,
        "Partial": ExtractionSessionStatus.PARTIAL,
    }

    # Load sessions
    sessions = asyncio.run(storage.get_extraction_sessions(
        limit=limit,
        status=status_map[status_filter],
        document_path=document_filter or None,
    ))

    st.markdown(f"**Found {len(sessions)} extraction sessions**")
    st.markdown("---")

    if not sessions:
        st.info("No extraction sessions found. Run the reaction extractor to see sessions here!")
        return

    # Group by document
    sessions_by_doc = defaultdict(list)
    for session in sessions:
        doc = session["document_path"]
        sessions_by_doc[doc].append(session)

    # Display sessions grouped by document
    for doc_path, doc_sessions in sorted(sessions_by_doc.items()):
        doc_name = Path(doc_path).name
        with st.expander(f"📄 {doc_name} ({len(doc_sessions)} sessions)", expanded=False):
            for session in sorted(doc_sessions, key=lambda x: x["started_at"], reverse=True):
                # Session header
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.markdown(f"**Session ID:** `{session['id'][:8]}...`")

                with col2:
                    st.markdown(f"**Type:** {session['extraction_type']}")

                with col3:
                    status_icon = {
                        "completed": "✅",
                        "in_progress": "🔄",
                        "failed": "❌",
                        "partial": "⚠️",
                    }.get(session["status"], "❓")
                    st.markdown(f"**Status:** {status_icon} {session['status'].upper()}")

                with col4:
                    st.markdown(f"**Started:** {session['started_at'][:19]}")

                # Duration
                if session.get("completed_at"):
                    started = datetime.fromisoformat(session["started_at"])
                    completed = datetime.fromisoformat(session["completed_at"])
                    duration = (completed - started).total_seconds()
                    st.caption(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")

                st.markdown("---")

                # Load and display steps
                steps = asyncio.run(storage.get_session_steps(session["id"]))

                if steps:
                    st.markdown("### 📋 Workflow Steps")

                    for step in steps:
                        # Step status indicator
                        status_icon = {
                            "completed": "✅",
                            "in_progress": "🔄",
                            "failed": "❌",
                            "pending": "⏳",
                        }.get(step["status"], "❓")

                        with st.container():
                            col1, col2, col3 = st.columns([4, 2, 1])

                            with col1:
                                st.markdown(f"{status_icon} **{step['step_name']}**")
                                st.caption(f"Phase: {step['step_phase']}")

                            with col2:
                                if step.get("started_at") and step.get("completed_at"):
                                    started = datetime.fromisoformat(step["started_at"])
                                    completed = datetime.fromisoformat(step["completed_at"])
                                    duration = (completed - started).total_seconds()
                                    st.caption(f"Duration: {duration:.2f}s")

                            with col3:
                                st.caption(f"Order: {step['step_order']}")

                            # Show linked conversation if exists
                            if step.get("conversation_id"):
                                conv_id = step["conversation_id"]
                                if st.button(f"View LLM Call", key=f"view_{step['id']}"):
                                    # Show conversation details
                                    conv = asyncio.run(storage.get_conversation(conv_id))
                                    if conv:
                                        st.markdown("**LLM Call Details:**")

                                        # Messages
                                        if conv.get("messages"):
                                            for msg in conv["messages"]:
                                                with st.chat_message(msg[0]):
                                                    st.markdown(msg[1])

                                        # Response
                                        if conv.get("response"):
                                            resp = conv["response"]
                                            if resp[3]:  # reasoning_content
                                                with st.expander("🧠 Thinking Process", expanded=False):
                                                    st.markdown(resp[3])

                                            st.markdown("**Response:**")
                                            st.markdown(resp[2])  # content

                                            # Metadata
                                            if resp[6]:  # total_tokens
                                                st.metric("Tokens", resp[6])
                                            if resp[7]:  # latency_seconds
                                                st.metric("Latency", f"{resp[7]:.2f}s")

                            if step.get("error_message"):
                                st.error(f"Error: {step['error_message']}")

                            st.markdown("---")

                # Show session statistics
                st.markdown("### 📊 Session Statistics")
                stats = asyncio.run(storage.get_session_statistics(session["id"]))
                if stats:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Steps", stats.get("total_steps", 0))
                    with col2:
                        if stats.get("total_tokens"):
                            st.metric("Total Tokens", f"{stats['total_tokens']:,}")
                    with col3:
                        if stats.get("total_latency_seconds"):
                            st.metric("Total Time", f"{stats['total_latency_seconds']:.1f}s")
                    with col4:
                        st.metric("Status", stats["status"].upper()) if isinstance(stats["status"], str) else st.metric("Status", stats["status"])

                st.markdown("---")


def _show_agent_conversations_view(storage):
    """Display all agent conversations grouped by agent."""
    from collections import defaultdict

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Get list of agents
        agents = asyncio.run(storage.get_agent_list())
        agent_options = ["All"] + [a["agent_id"] for a in agents]
        agent_filter = st.selectbox("Filter by Agent", options=agent_options)

    with col2:
        status_filter = st.selectbox(
            "Status",
            options=["All", "Completed", "In Progress", "Error"],
        )

    with col3:
        limit = st.number_input("Show", min_value=10, max_value=500, value=50, step=10)

    with col4:
        st.write("")  # spacing
        if st.button("🔄 Refresh", key="refresh_agents"):
            st.rerun()

    st.markdown("---")

    # Load conversations
    agent_id = agent_filter if agent_filter != "All" else None
    conversations = asyncio.run(storage.get_conversations_by_agent(
        agent_id=agent_id,
        limit=limit,
    ))

    # Apply status filter
    if status_filter != "All":
        conversations = [
            c for c in conversations
            if c["status"] == status_filter.lower()
        ]

    st.markdown(f"**Found {len(conversations)} conversations**")
    st.markdown("---")

    if not conversations:
        st.info("No conversations found for this agent.")
        return

    # Group by agent
    conversations_by_agent = defaultdict(list)
    for conv in conversations:
        agent = conv.get("agent_id") or "Unknown"
        conversations_by_agent[agent].append(conv)

    # Display conversations grouped by agent
    for agent_id, agent_convs in sorted(conversations_by_agent.items()):
        with st.expander(f"🤖 {agent_id} ({len(agent_convs)} conversations)", expanded=False):
            for conv in sorted(agent_convs, key=lambda x: x["timestamp"], reverse=True):
                # Conversation header
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.markdown(f"**ID:** `{conv['id'][:8]}...`")

                with col2:
                    st.markdown(f"**Model:** {conv['model_name']}")

                with col3:
                    status_icon = {
                        "completed": "✅",
                        "in_progress": "🔄",
                        "error": "❌",
                    }.get(conv["status"], "❓")
                    st.markdown(f"**Status:** {status_icon} {conv['status'].upper()}")

                with col4:
                    st.markdown(f"**Time:** {conv['timestamp'][:19]}")

                st.markdown("---")

                # Load and display messages
                full_conv = asyncio.run(storage.get_conversation(conv["id"]))
                if full_conv:
                    st.markdown("### 💬 Messages")

                    # Display input messages
                    for msg in full_conv.get("messages", []):
                        with st.chat_message(msg[0]):
                            st.markdown(msg[1])

                    # Display response
                    if full_conv.get("response"):
                        resp = full_conv["response"]
                        if resp[3]:  # reasoning_content
                            with st.expander("🧠 Thinking Process", expanded=False):
                                st.markdown(resp[3])

                        st.markdown("**Response:**")
                        st.markdown(resp[2])  # content

                        # Metadata
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if resp[6]:  # total_tokens
                                st.metric("Tokens", resp[6])
                        with col2:
                            if resp[7]:  # latency_seconds
                                st.metric("Latency", f"{resp[7]:.2f}s")
                        with col3:
                            if resp[6] and resp[7]:
                                st.metric("Tokens/sec", f"{resp[6] / resp[7]:.1f}")

                st.markdown("---")


def main():
    """Main application entry point."""
    page = render_sidebar()

    if page == "Live View":
        show_live_view()
    elif page == "History":
        show_history()
    elif page == "Statistics":
        show_stats()
    elif page == "Agent Sessions":
        show_extraction_sessions()


if __name__ == "__main__":
    main()
