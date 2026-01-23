"""Scientific Laboratory themed Agent Sessions view.

This module provides a distinctive, production-grade interface for viewing
all agent execution sessions with a bold scientific laboratory aesthetic.
Displays the hierarchical structure: Agent → Tasks → Jobs (LLM Calls) → Details
"""

import asyncio
from collections import defaultdict
from datetime import datetime

import streamlit as st


def show_agent_sessions_lab_theme():
    """Display all agent execution sessions with scientific laboratory theme.

    Features:
    - Universal agent tracking (not extraction-specific)
    - Dark theme with neon green/blue bio-luminescent accents
    - Monospace fonts for technical precision
    - Hierarchical display: Agent → Tasks → Jobs (Conversations) → Details
    - Task-level statistics (duration, job count, total tokens)
    """
    from src.conversations.models import ExtractionSessionStatus

    storage = st.session_state.storage

    # Render header with lab aesthetic
    st.markdown("""
    <div class="page-header">
        <div class="page-title">🤖 Agent Execution Sessions</div>
        <div class="page-subtitle">// UNIVERSAL AGENT TRACKING SYSTEM</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        # Get available agents
        agents = asyncio.run(storage.get_agent_list())
        agent_options = ["ALL"] + [a["agent_id"] for a in agents]
        agent_filter = st.selectbox(
            "FILTER_BY_AGENT",
            options=agent_options,
            label_visibility="collapsed",
        )

    with col2:
        status_filter = st.selectbox(
            "FILTER_BY_STATUS",
            options=["ALL", "COMPLETED", "IN_PROGRESS", "FAILED"],
            label_visibility="collapsed",
        )

    with col3:
        limit = st.number_input(
            "DISPLAY_LIMIT",
            min_value=5,
            max_value=100,
            value=20,
            step=5,
            label_visibility="collapsed",
        )

    st.markdown("---")

    # Load extraction sessions (Tasks)
    status_map = {
        "ALL": None,
        "COMPLETED": ExtractionSessionStatus.COMPLETED,
        "IN_PROGRESS": ExtractionSessionStatus.IN_PROGRESS,
        "FAILED": ExtractionSessionStatus.FAILED,
    }

    tasks = asyncio.run(storage.get_extraction_sessions(
        limit=limit,
        status=status_map[status_filter]
    ))

    # Filter by agent if needed
    if agent_filter != "ALL":
        tasks = [t for t in tasks if t.get("agent_id") == agent_filter]

    # Display task count
    st.markdown(f"""
    <div style="font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.85rem;
                color: var(--lab-text-secondary); margin-bottom: 1rem;">
    > DETECTED <span class="neon-text-green" style="font-size: 1.1rem; font-weight: 600;">
    {len(tasks)}</span> TASKS
    </div>
    """, unsafe_allow_html=True)

    if not tasks:
        st.markdown("""
        <div style="padding: 2rem; text-align: center; font-family: 'SF Mono', monospace;
                    color: var(--lab-text-secondary); border: 1px dashed var(--lab-border-glow);
                    border-radius: 4px;">
            [NO TASKS FOUND]
        </div>
        """, unsafe_allow_html=True)
        return

    # Group by agent (Level 1)
    tasks_by_agent = defaultdict(list)
    for task in tasks:
        agent_id = task.get("agent_id", "UNKNOWN")
        tasks_by_agent[agent_id].append(task)

    # Display agents and their tasks
    for agent_id, agent_tasks in sorted(tasks_by_agent.items()):
        # Calculate agent-level stats by loading actual steps
        total_tasks = len(agent_tasks)
        total_jobs = 0
        total_duration = 0

        for task in agent_tasks:
            # Load actual steps to get real job count (ALL jobs, including technical steps)
            task_steps = asyncio.run(storage.get_session_steps(task["id"]))
            total_jobs += len(task_steps)

            if task.get("started_at") and task.get("completed_at"):
                try:
                    started = datetime.fromisoformat(task["started_at"])
                    completed = datetime.fromisoformat(task["completed_at"])
                    total_duration += (completed - started).total_seconds()
                except:
                    pass

        # Agent header with neon styling
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(13, 20, 25, 0.95) 0%, rgba(15, 26, 31, 0.95) 100%);
                    border: 2px solid var(--lab-border-glow); border-left: 4px solid var(--lab-neon-green);
                    border-radius: 4px; padding: 1.25rem 1.5rem; margin: 1.5rem 0;
                    box-shadow: var(--lab-glow-shadow);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-family: var(--lab-mono-font); font-size: 0.7rem;
                                color: var(--lab-text-secondary); letter-spacing: 0.15em; margin-bottom: 0.25rem;">
                        // AGENT_ID
                    </div>
                    <div style="font-family: var(--lab-mono-font); font-size: 1.1rem;
                                color: var(--lab-neon-green); font-weight: 600;
                                text-shadow: 0 0 10px rgba(0, 255, 157, 0.4);">
                        {agent_id}
                    </div>
                </div>
                <div style="display: flex; gap: 2rem; font-family: var(--lab-mono-font); font-size: 0.8rem;">
                    <div><span class="neon-text-blue">TASKS:</span> {total_tasks}</div>
                    <div><span class="neon-text-blue">JOBS:</span> {total_jobs}</div>
                    <div><span class="neon-text-blue">TIME:</span> {total_duration:.0f}s</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Agent metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="TOTAL_TASKS", value=f"{total_tasks}", label_visibility="visible")
        with col2:
            st.metric(label="TOTAL_JOBS", value=f"{total_jobs}", label_visibility="visible")
        with col3:
            st.metric(label="DURATION", value=f"{total_duration:.0f}s", label_visibility="visible")
        with col4:
            avg_jobs = total_jobs / total_tasks if total_tasks > 0 else 0
            st.metric(label="AVG_JOBS", value=f"{avg_jobs:.1f}", label_visibility="visible")

        # Level 2: Tasks (Extraction Sessions)
        for task in sorted(agent_tasks, key=lambda x: x.get("started_at", ""), reverse=True):
            task_id = task["id"]
            doc_path = task.get("document_path", "UNKNOWN")
            doc_name = doc_path.split("/")[-1] if "/" in doc_path else doc_path

            # Load steps to get actual job count (ALL jobs)
            steps = asyncio.run(storage.get_session_steps(task_id))
            # Sort steps by order
            steps_sorted = sorted(steps, key=lambda x: x.get("step_order", 0))
            job_count = len(steps_sorted)

            # Task status
            status = task.get("status", "unknown")
            status_badge_class = {
                "completed": "status-completed",
                "in_progress": "status-in-progress",
                "failed": "status-failed",
            }.get(status, "")

            # Calculate task duration
            duration_str = "N/A"
            if task.get("started_at") and task.get("completed_at"):
                try:
                    started = datetime.fromisoformat(task["started_at"])
                    completed = datetime.fromisoformat(task["completed_at"])
                    duration = (completed - started).total_seconds()
                    duration_str = f"{duration:.1f}s"
                except:
                    pass

            # Task card
            st.markdown(f"""
            <div style="margin-left: 1.5rem; margin-top: 1rem; padding-left: 1rem;
                        border-left: 2px solid var(--lab-border-glow);">
                <div style="background: linear-gradient(135deg, rgba(13, 20, 25, 0.8) 0%, rgba(15, 26, 31, 0.8) 100%);
                            border: 1px solid var(--lab-border-glow); border-radius: 4px;
                            padding: 1rem 1.25rem; backdrop-filter: blur(10px);
                            box-shadow: var(--lab-glow-shadow); transition: all 0.3s ease;"
                     onmouseover="this.style.borderColor='var(--lab-neon-blue)'"
                     onmouseout="this.style.borderColor='var(--lab-border-glow)'">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                        <div style="display: flex; align-items: center; gap: 0.75rem;">
                            <span style="font-size: 1.2rem;">📋</span>
                            <span style="font-family: var(--lab-mono-font); font-weight: 600;
                                        color: var(--lab-text-primary);">{doc_name}</span>
                        </div>
                        <span class="status-badge {status_badge_class}" style="font-size: 0.65rem;">
                            {status.upper().replace('_', ' ')}
                        </span>
                    </div>
                    <div style="display: flex; gap: 2rem; font-family: var(--lab-mono-font);
                                font-size: 0.75rem; color: var(--lab-text-secondary);">
                        <div><span style="color: var(--lab-neon-blue);">ID:</span> {task_id[:8]}...</div>
                        <div><span style="color: var(--lab-neon-blue);">TYPE:</span> {task.get('extraction_type', 'unknown')}</div>
                        <div><span style="color: var(--lab-neon-blue);">JOBS:</span> {job_count}</div>
                        <div><span style="color: var(--lab-neon-blue);">DURATION:</span> {duration_str}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Level 3: Jobs (Conversations) - Show steps if available
            if steps_sorted:
                st.markdown(f"""
                <div style="margin-left: 3rem; margin-top: 1rem; padding: 1.5rem;
                            background: rgba(13, 20, 25, 0.5); border-radius: 4px;
                            border: 1px dashed var(--lab-border-glow);">
                    <div style="font-family: var(--lab-mono-font); font-size: 0.75rem;
                                color: var(--lab-neon-green); letter-spacing: 0.1em; margin-bottom: 1rem;">
                        // WORKFLOW_JOBS
                    </div>
                </div>
                """, unsafe_allow_html=True)

                for i, step in enumerate(steps_sorted, 1):
                    step_name = step.get("step_name", "Unknown")
                    step_status = step.get("status", "unknown")
                    step_status_class = {
                        "completed": "completed",
                        "in_progress": "in_progress",
                        "failed": "failed",
                    }.get(step_status, "")

                    conv_id = step.get("conversation_id")

                    # Job node with animation
                    st.markdown(f"""
                    <div style="margin-left: 4.5rem; position: relative;">
                        <div class="workflow-node {step_status_class}">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div style="font-family: var(--lab-mono-font); font-size: 0.7rem;
                                                color: var(--lab-text-secondary); letter-spacing: 0.1em;">
                                        JOB_{i:02d}
                                    </div>
                                    <div style="font-family: var(--lab-display-font); font-size: 0.95rem;
                                                color: var(--lab-text-primary); margin-top: 0.25rem;">
                                        {step_name}
                                    </div>
                                </div>
                                <span class="status-badge status-{step_status_class}" style="font-size: 0.6rem;">
                                    {step_status.upper().replace('_', ' ')}
                                </span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Level 4: LLM Call Details
                    if conv_id:
                        with st.expander(f"View Job {i} Details", expanded=False):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Order:** `{step.get('step_order', 'N/A')}`")
                                st.markdown(f"**Status:** `{step.get('status', 'unknown').upper()}`")
                            with col2:
                                if step.get("started_at"):
                                    st.markdown(f"**Started:** `{step['started_at'][:19]}`")
                                if step.get("completed_at"):
                                    st.markdown(f"**Completed:** `{step['completed_at'][:19]}`")

                            st.markdown("---")
                            st.markdown("##### 💬 LLM_CALL")

                            try:
                                full_conv = asyncio.run(storage.get_conversation(conv_id))
                                if full_conv and full_conv.get("response"):
                                    resp = full_conv["response"]

                                    # Show prompt - each message in its own expander
                                    if full_conv.get("messages"):
                                        st.markdown("##### 📥 Prompt Messages")
                                        for i, msg in enumerate(full_conv["messages"]):
                                            role = msg[0]
                                            content = msg[1]

                                            # Role-specific emoji and label
                                            role_config = {
                                                "user": {"emoji": "👤", "label": "User", "color": "#3b82f6"},
                                                "assistant": {"emoji": "🤖", "label": "Assistant", "color": "#10b981"},
                                                "system": {"emoji": "⚙️", "label": "System", "color": "#f59e0b"},
                                            }
                                            config = role_config.get(role, {"emoji": "💬", "label": role.title(), "color": "#6b7280"})

                                            # Create expander for each message
                                            with st.expander(
                                                f"{config['emoji']} {config['label']} Message {i+1}",
                                                expanded=False
                                            ):
                                                st.markdown(
                                                    f"<div style='border-left: 3px solid {config['color']}; "
                                                    f"padding-left: 1rem; margin: 0.5rem 0;'>"
                                                    f"<div style='color: {config['color']}; font-weight: 600; "
                                                    f"font-size: 0.8rem; margin-bottom: 0.5rem;'>"
                                                    f"{config['emoji']} {config['label'].upper()}</div>"
                                                    f"<div style='color: var(--lab-text-primary);'>{content}</div>"
                                                    f"</div>",
                                                    unsafe_allow_html=True
                                                )

                                    # Show thinking/reasoning
                                    if resp[3]:  # reasoning_content
                                        with st.expander("🧠 Thinking Process", expanded=False):
                                            st.markdown(resp[3])

                                    # Show response
                                    st.markdown("**Response:**")
                                    response_content = resp[2]
                                    if len(response_content) > 1000:
                                        st.markdown(response_content[:1000] + "...")
                                        if st.button(f"Show full response", key=f"full_{step['id'][:8]}"):
                                            st.markdown(response_content)
                                    else:
                                        st.markdown(response_content)

                                    # LLM call metrics
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        if resp[6]:
                                            st.metric("Tokens", resp[6])
                                    with col2:
                                        if resp[7]:
                                            st.metric("Latency", f"{resp[7]:.2f}s")
                                    with col3:
                                        if resp[6] and resp[7]:
                                            st.metric("Tokens/sec", f"{resp[6] / resp[7]:.1f}")
                            except Exception as e:
                                st.error(f"Error loading conversation: {e}")

                        # Show error if present
                        if step.get("error_message"):
                            st.error(f"**Error:** {step['error_message']}")

            st.markdown("<br>", unsafe_allow_html=True)
