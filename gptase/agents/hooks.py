"""Hook protocol for Agent.run().

Agents may ship a sibling ``hooks.py`` file alongside their ``.md`` definition
to inject behavior around the LLM call. Two hook points are supported:

* ``pre_run(ctx)``  — runs after memory injection and multimodal prompt
  assembly, before the SDK / LLM dispatch. May mutate ``ctx.prompt`` /
  ``ctx.image_paths`` in place. Returning a ``dict`` short-circuits the run:
  the returned dict becomes the final result and the LLM is never invoked.
  Returning ``None`` continues the normal flow.

* ``post_run(ctx, result)`` — runs after dispatch (or after short-circuit),
  with the populated ``ctx.result``. Returning a ``dict`` replaces the
  result; returning ``None`` leaves it untouched.

Both functions may be sync or async; ``Agent.run`` awaits when needed.
A raised exception propagates as a run failure (fail-fast).

Discovery is convention-based: the file at
``.claude/agents/<agent_id>/hooks.py`` is auto-loaded by
``Agent._register_agent_local_hooks`` when the agent is constructed via
``Agent.from_markdown``. Module-level callables named ``pre_run`` and
``post_run`` are picked up; anything else is ignored.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class HookContext:
    """State threaded through ``pre_run`` and ``post_run`` for a single run.

    Attributes:
        agent_id: The owning agent's identifier. Treat as read-only.
        tools: Tuple of allowed tool names. Treat as read-only.
        workspace_dir: The agent's workspace directory, if any. Read-only.
        prompt: The prompt that will be sent to the LLM. May be a plain
            string or a multimodal list of content dicts. Mutating this
            in ``pre_run`` changes what the LLM sees.
        image_paths: Image paths attached to this run, if any. May be
            replaced or appended to in ``pre_run``.
        extras: Free-form dict for passing state from ``pre_run`` to
            ``post_run`` (e.g. start timestamps, cache keys).
        result: The run's result dict. ``None`` during ``pre_run``;
            populated before ``post_run`` runs.
        short_circuited: ``True`` when ``pre_run`` returned a result and
            the LLM dispatch was skipped. ``False`` for normal LLM runs.
    """

    agent_id: str
    tools: Tuple[str, ...]
    workspace_dir: Optional[str]
    prompt: Union[str, List[Dict[str, Any]]]
    image_paths: Optional[List[str]] = None
    extras: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    short_circuited: bool = False
