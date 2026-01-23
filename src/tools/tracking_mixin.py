"""Tracking mixin for tools that support conversation and session tracking.

This module provides a reusable mixin class for tools that need to track
their LLM calls with agent_id, session_id, and step_id parameters.
"""

from typing import Optional


class TrackingMixin:
    """Mixin class for tools that support conversation tracking.

    This mixin provides common initialization and storage for tracking
    parameters used by ModelManager to link LLM calls to extraction
    sessions and workflow steps.

    Attributes:
        agent_id: Optional agent ID for tracking which agent initiated the call.
        session_id: Optional session ID for tracking extraction sessions.
        step_id: Optional step ID for tracking workflow steps within sessions.

    Example:
        ```python
        class MyTool(BaseTool, TrackingMixin):
            def __init__(self, model_manager, agent_id=None, session_id=None, step_id=None):
                BaseTool.__init__(self, name="my_tool", description="...")
                TrackingMixin.__init__(self, agent_id, session_id, step_id)
                self.model_manager = model_manager

            async def execute(self, **kwargs):
                # Use tracking IDs when calling LLM
                response = await self.model_manager.generate(
                    messages,
                    agent_id=self.agent_id,
                    session_id=self.session_id,
                    step_id=self.step_id,
                )
                return ToolResult.success(response)
        ```
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ):
        """Initialize tracking parameters.

        Args:
            agent_id: Optional agent ID for tracking.
            session_id: Optional session ID for tracking.
            step_id: Optional step ID for tracking.
        """
        self.agent_id = agent_id
        self.session_id = session_id
        self.step_id = step_id

    def get_tracking_params(self) -> dict:
        """Get tracking parameters as a dictionary.

        Useful for passing tracking IDs to functions that accept **kwargs.

        Returns:
            Dictionary with non-None tracking parameters.

        Example:
            ```python
            tracking = self.get_tracking_params()
            await model_manager.generate(messages, **tracking)
            ```
        """
        params = {}
        if self.agent_id is not None:
            params["agent_id"] = self.agent_id
        if self.session_id is not None:
            params["session_id"] = self.session_id
        if self.step_id is not None:
            params["step_id"] = self.step_id
        return params

    def update_tracking(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> None:
        """Update tracking parameters.

        Args:
            agent_id: New agent ID (None to keep current).
            session_id: New session ID (None to keep current).
            step_id: New step ID (None to keep current).
        """
        if agent_id is not None:
            self.agent_id = agent_id
        if session_id is not None:
            self.session_id = session_id
        if step_id is not None:
            self.step_id = step_id
