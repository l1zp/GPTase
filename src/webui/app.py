"""Main Streamlit application for conversation visualization."""

import asyncio
from pathlib import Path
import sys
import json
import re

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

# Custom CSS - Scientific Laboratory Theme
st.markdown(
    """
<style>
/* CSS Variables for consistent theming */
:root {
    --lab-bg-dark: #1a1f2e;
    --lab-bg-panel: #0d1419;
    --lab-neon-green: #00ff9d;
    --lab-neon-blue: #00d4ff;
    --lab-neon-purple: #a855f7;
    --lab-text-primary: #f1f5f9;
    --lab-text-secondary: #cbd5e1;
    --lab-border-glow: rgba(0, 255, 157, 0.3);
    --lab-glow-shadow: 0 0 20px rgba(0, 255, 157, 0.15);
    --lab-mono-font: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    --lab-display-font: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* Dark theme base with better contrast */
.main {
    background: linear-gradient(135deg, #1a1f2e 0%, #0f1a1f 100%) !important;
    color: #f1f5f9 !important;
}

[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #1a1f2e 0%, #0f1a1f 100%) !important;
}

[data-testid="stAppViewContainer"] > div {
    background: transparent;
}

/* Ensure all text is visible - EXCEPT buttons */
.main *:not(button):not([data-testid="stButton"]) {
    color: #f1f5f9 !important;
}

/* Streamlit text elements */
.stMarkdown, .stText {
    color: #f1f5f9 !important;
}

.main .block-container {
    max-width: 1400px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Page header with neon glow */
.page-header {
    margin-bottom: 2rem;
    padding: 1.5rem 2rem;
    background: linear-gradient(135deg, rgba(13, 20, 25, 0.9) 0%, rgba(15, 26, 31, 0.9) 100%);
    border: 1px solid var(--lab-border-glow);
    border-radius: 4px;
    color: var(--lab-text-primary);
    box-shadow: var(--lab-glow-shadow), inset 0 1px 0 rgba(0, 255, 157, 0.1);
    position: relative;
    overflow: hidden;
}

.page-header::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--lab-neon-green) 0%, var(--lab-neon-blue) 50%, var(--lab-neon-purple) 100%);
    animation: glow-pulse 3s ease-in-out infinite;
}

@keyframes glow-pulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
}

.page-title {
    font-family: var(--lab-display-font);
    font-size: 2rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--lab-neon-green);
    text-shadow: 0 0 10px rgba(0, 255, 157, 0.5);
}

.page-subtitle {
    font-family: var(--lab-mono-font);
    font-size: 0.85rem;
    color: var(--lab-text-secondary);
    margin-top: 0.5rem;
    letter-spacing: 0.05em;
}

/* Metrics with neon styling */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(13, 20, 25, 0.8) 0%, rgba(15, 26, 31, 0.8) 100%) !important;
    border: 1px solid var(--lab-border-glow) !important;
    border-radius: 4px !important;
    padding: 1rem 1.25rem;
    box-shadow: var(--lab-glow-shadow);
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
}

[data-testid="stMetric"]:hover {
    border-color: var(--lab-neon-blue) !important;
    box-shadow: 0 0 25px rgba(0, 212, 255, 0.2);
    transform: translateY(-2px);
}

[data-testid="stMetric"] label {
    color: var(--lab-text-secondary) !important;
    font-family: var(--lab-mono-font);
    font-size: 0.75rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--lab-neon-green) !important;
    font-family: var(--lab-mono-font);
    font-size: 1.75rem;
    font-weight: 600;
    text-shadow: 0 0 10px rgba(0, 255, 157, 0.3);
}

/* Expanders with lab styling */
[data-testid="stExpander"] {
    border: 1px solid var(--lab-border-glow) !important;
    border-radius: 4px !important;
    background: linear-gradient(135deg, rgba(21, 32, 45, 0.95) 0%, rgba(15, 26, 31, 0.95) 100%) !important;
    box-shadow: var(--lab-glow-shadow);
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
    margin-bottom: 1rem;
}

[data-testid="stExpander"]:hover {
    border-color: var(--lab-neon-blue) !important;
    box-shadow: 0 0 25px rgba(0, 212, 255, 0.15);
}

/* Fix expander header background for all states */
[data-testid="stExpander"] > div,
[data-testid="stExpander"] > div > div,
[data-testid="stExpander"] > div > div > div,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary > div,
[data-testid="stExpander"] summary > span {
    background: transparent !important;
}

[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary:hover > div,
[data-testid="stExpander"] summary:hover > span {
    background: transparent !important;
}

[data-testid="stExpander"] > div > div > svg {
    color: var(--lab-neon-green);
    filter: drop-shadow(0 0 5px rgba(0, 255, 157, 0.5));
}

/* Fix ALL Streamlit default white backgrounds */
div[style*="background-color: white"],
div[style*="background: rgb(255, 255, 255)"] {
    background-color: #0f172a !important;
}

/* Toolbar with lab theme */
[data-testid="stToolbar"],
.stAppToolbar {
    background: linear-gradient(180deg, var(--lab-bg-dark) 0%, var(--lab-bg-panel) 100%) !important;
    border-bottom: 1px solid var(--lab-border-glow) !important;
}

/* Sidebar with lab theme */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--lab-bg-dark) 0%, var(--lab-bg-panel) 100%) !important;
    border-right: 1px solid var(--lab-border-glow) !important;
}

[data-testid="stSidebar"] * {
    color: var(--lab-text-primary);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: var(--lab-text-secondary);
    font-family: var(--lab-mono-font);
    font-size: 0.8rem;
}

[data-testid="stSidebar"] .css-1d391kg {
    color: var(--lab-neon-green) !important;
    font-family: var(--lab-mono-font);
    font-weight: 600;
    letter-spacing: 0.05em;
}

/* Ensure all text is visible with better contrast */
[data-testid="stMarkdownContainer"] {
    color: #f1f5f9 !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {
    color: #f1f5f9 !important;
}

/* Labels and inputs */
label {
    color: #cbd5e1 !important;
}

/* Button styling - simplified to avoid React errors */
button[data-testid="stBaseButton-secondary"] {
    background: linear-gradient(135deg, rgba(0, 255, 157, 0.2) 0%, rgba(0, 212, 255, 0.2) 100%) !important;
    pointer-events: auto !important;
}

button[data-testid="stBaseButton-secondary"]:hover {
    background: linear-gradient(135deg, rgba(0, 255, 157, 0.3) 0%, rgba(0, 212, 255, 0.3) 100%) !important;
}

/* Number input step buttons */
button[data-testid="stNumberInputStepUp"],
button[data-testid="stNumberInputStepDown"] {
    vertical-align: middle !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}

/* Filter row alignment - shared across all views */
.stColumns > div > div[data-testid="stVerticalBlock"] > div > div {
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
}

/* Selectbox alignment */
[data-testid="stSelectbox"] > div {
    display: flex !important;
    align-items: center !important;
    min-height: 42px !important;
}

/* Number input alignment */
[data-testid="stNumberInput"] > div {
    display: flex !important;
    align-items: center !important;
    min-height: 42px !important;
}

[data-testid="stNumberInput"] > div > div {
    display: flex !important;
    align-items: center !important;
    min-height: 42px !important;
}

/* Number input field */
input[data-testid="stNumberInputField"] {
    height: 42px !important;
    padding: 0.5rem 0.75rem !important;
    border-radius: 4px !important;
    border: 1px solid var(--lab-border-glow) !important;
    background: rgba(21, 32, 45, 0.95) !important;
    color: #f1f5f9 !important;
}

hr {
    border: none;
    height: 1px;
    background: var(--lab-border-glow);
    margin: 1.5rem 0;
}

/* Workflow visualization styles */
.workflow-container {
    position: relative;
    padding: 2rem 0;
}

.workflow-node {
    background: linear-gradient(135deg, rgba(13, 20, 25, 0.9) 0%, rgba(15, 26, 31, 0.9) 100%);
    border: 1px solid var(--lab-border-glow);
    border-radius: 4px;
    padding: 1rem 1.5rem;
    margin: 0.5rem 0;
    position: relative;
    transition: all 0.3s ease;
}

.workflow-node::before {
    content: '';
    position: absolute;
    left: -1rem;
    top: 50%;
    transform: translateY(-50%);
    width: 0.75rem;
    height: 0.75rem;
    background: var(--lab-neon-green);
    border-radius: 50%;
    box-shadow: 0 0 10px var(--lab-neon-green);
    animation: node-pulse 2s ease-in-out infinite;
}

@keyframes node-pulse {
    0%, 100% { transform: translateY(-50%) scale(1); opacity: 1; }
    50% { transform: translateY(-50%) scale(1.2); opacity: 0.7; }
}

.workflow-node.completed {
    border-color: var(--lab-neon-green);
}

.workflow-node.completed::before {
    background: var(--lab-neon-green);
}

.workflow-node.in_progress {
    border-color: var(--lab-neon-blue);
}

.workflow-node.in_progress::before {
    background: var(--lab-neon-blue);
    animation: node-pulse-blue 1.5s ease-in-out infinite;
}

@keyframes node-pulse-blue {
    0%, 100% { transform: translateY(-50%) scale(1); opacity: 1; }
    50% { transform: translateY(-50%) scale(1.3); opacity: 0.8; }
}

.workflow-node.failed {
    border-color: #ef4444;
}

.workflow-node.failed::before {
    background: #ef4444;
    animation: none;
}

/* Status badges */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 2px;
    font-family: var(--lab-mono-font);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.status-completed {
    background: rgba(0, 255, 157, 0.1);
    color: var(--lab-neon-green);
    border: 1px solid var(--lab-neon-green);
}

.status-in-progress {
    background: rgba(0, 212, 255, 0.1);
    color: var(--lab-neon-blue);
    border: 1px solid var(--lab-neon-blue);
    animation: status-glow 2s ease-in-out infinite;
}

@keyframes status-glow {
    0%, 100% { box-shadow: 0 0 5px rgba(0, 212, 255, 0.3); }
    50% { box-shadow: 0 0 15px rgba(0, 212, 255, 0.5); }
}

.status-failed {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
    border: 1px solid #ef4444;
}

/* Neon text effects */
.neon-text-green {
    color: var(--lab-neon-green);
    text-shadow: 0 0 10px rgba(0, 255, 157, 0.5);
}

.neon-text-blue {
    color: var(--lab-neon-blue);
    text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
}

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--lab-bg-dark);
}

::-webkit-scrollbar-thumb {
    background: var(--lab-border-glow);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--lab-neon-green);
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


def render_page_header(title: str, subtitle: str):
    if subtitle:
        st.markdown(
            f"""
            <div class="page-header">
                <div class="page-title">{title}</div>
                <div class="page-subtitle">{subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="page-header">
                <div class="page-title">{title}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_response_content(content: str):
    """Render response content, detecting and formatting JSON if present.

    Args:
        content: Response content string that may contain JSON.
    """
    if not content:
        return

    # Try to detect and extract JSON from content
    json_pattern = r'\{[^{}]*"is_reaction_related"[^{}]*\}|\{[^{}]*"confidence"[^{}]*\}|\{.*"reasoning".*\}'
    json_matches = re.findall(json_pattern, content, re.DOTALL)

    if json_matches:
        # Display formatted JSON in an expander
        for json_str in json_matches:
            try:
                # Try to parse as JSON
                parsed = json.loads(json_str)

                # Display in a nice card format
                with st.container():
                    col1, col2 = st.columns([3, 1])

                    # is_reaction_related
                    if "is_reaction_related" in parsed:
                        with col1:
                            is_related = parsed["is_reaction_related"]
                            if is_related:
                                st.success("✅ Reaction Related")
                            else:
                                st.info("❌ Not Reaction Related")

                    # confidence
                    if "confidence" in parsed:
                        with col2:
                            conf = parsed["confidence"]
                            st.metric("Confidence", f"{conf:.0%}")

                    # reasoning
                    if "reasoning" in parsed:
                        with st.expander("📝 Reasoning", expanded=False):
                            st.markdown(parsed["reasoning"])

                    # Display any other fields
                    other_fields = {k: v for k, v in parsed.items()
                                   if k not in ["is_reaction_related", "confidence", "reasoning"]}
                    if other_fields:
                        with st.expander("📋 Additional Info", expanded=False):
                            st.json(other_fields)

                    st.markdown("---")

            except (json.JSONDecodeError, Exception):
                # If parsing fails, display as regular markdown
                st.markdown(content)
                break
    else:
        # No JSON detected, display as regular markdown
        st.markdown(content)


def render_sidebar():
    """Render sidebar with navigation and stats."""
    storage = get_storage()

    with st.sidebar:
        st.title("🤖 GPTase")
        st.markdown("<span class=\"muted-text\">Conversation Intelligence Hub</span>", unsafe_allow_html=True)
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
    render_page_header("🔴 Live Conversation View", "Watch active conversations as they stream in real time.")

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
                                render_response_content(resp[2])
                                st.spinner("Generating...")

                st.markdown("---")

    # Auto-refresh
    if auto_refresh:
        import time

        time.sleep(2)
        st.rerun()


def show_history():
    """Display historical conversations with search and filtering."""
    render_page_header("📚 Conversation History", "Search and review completed conversations.")

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

                    render_response_content(resp[2])

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
    render_page_header("📊 Statistics & Analytics", "Monitor usage, reliability, and throughput.")

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


def show_agent_conversations():
    render_page_header("🧑‍💻 Agent Conversations", "Browse and filter conversations grouped by agent.")
    storage = get_storage()
    _show_agent_conversations_view(storage)


def show_agent_sessions():
    """Display agent execution sessions with workflow tracking."""
    from src.webui.agent_sessions_lab import show_agent_sessions_lab_theme

    show_agent_sessions_lab_theme()


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
                        render_response_content(resp[2])

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
        show_agent_sessions()


if __name__ == "__main__":
    main()
