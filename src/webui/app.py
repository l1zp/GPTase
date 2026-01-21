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
            options=["Live View", "History", "Statistics"],
            icons=["🔴", "📚", "📊"],
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
                    if full_conv["response"][5]:  # total_tokens
                        st.caption(f"Tokens: {full_conv['response'][5]}")
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
                        if resp[4]:  # reasoning_content
                            with st.expander("🧠 Thinking", expanded=True):
                                st.markdown(resp[4])
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

                    if resp[4]:  # reasoning_content
                        with st.expander("🧠 Thinking Process", expanded=False):
                            st.markdown(resp[4])

                    st.markdown(resp[2])  # content

                    # Metadata
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if resp[5]:  # total_tokens
                            st.metric("Tokens", resp[5])
                    with col2:
                        if resp[7]:  # latency_seconds
                            st.metric("Latency", f"{resp[7]:.2f}s")
                    with col3:
                        if resp[5] and resp[7]:
                            st.metric("Tokens/sec", f"{resp[5] / resp[7]:.1f}")

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


def main():
    """Main application entry point."""
    page = render_sidebar()

    if page == "Live View":
        show_live_view()
    elif page == "History":
        show_history()
    elif page == "Statistics":
        show_stats()


if __name__ == "__main__":
    main()
