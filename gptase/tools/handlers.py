"""Tool execution handlers."""

import asyncio
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Set

from gptase.tools.base import BaseTool
from gptase.utils.schema import validate_agent_inputs
from gptase.utils.schema import validate_agent_output

logger = logging.getLogger(__name__)

READ_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {
            "type":
            "string",
            "description":
            "The absolute path to the file to read. You can call this tool multiple times in a single response to read multiple files in parallel.",
        },
        "offset": {
            "type": "integer",
            "description": "Line number to start reading from (1-indexed, optional)",
        },
        "limit": {
            "type": "integer",
            "description": "Number of lines to read (optional)",
        },
    },
    "required": ["file_path"],
}

GREP_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type":
            "string",
            "description":
            "The regex pattern to search for. You can call this tool multiple times in a single response to search different patterns or paths in parallel.",
        },
        "path": {
            "type": "string",
            "description": "Directory or file path to search in",
        },
        "glob": {
            "type": "string",
            "description": "File pattern to match (e.g., '*.py')",
        },
    },
    "required": ["pattern", "path"],
}

GLOB_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type":
            "string",
            "description":
            "Glob pattern to match files (e.g., '**/*.py'). You can call this tool multiple times in a single response to search with different patterns in parallel.",
        },
        "path": {
            "type": "string",
            "description": "Base directory for the search (optional)",
        },
    },
    "required": ["pattern"],
}

BASH_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The bash command to execute",
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds (default: 30)",
        },
    },
    "required": ["command"],
}


class ReadTool(BaseTool):
    """Read tool for file reading."""

    name = "Read"
    description = "Read contents from a file on the local filesystem."

    def get_schema(self) -> Dict[str, Any]:
        return READ_TOOL_SCHEMA

    BINARY_EXTENSIONS = {
        '.jpg',
        '.jpeg',
        '.png',
        '.gif',
        '.webp',
        '.bmp',
        '.tiff',
        '.tif',
        '.ico',
        '.svg',
        '.pdf',
        '.zip',
        '.gz',
        '.tar',
        '.bz2',
        '.7z',
        '.mp3',
        '.mp4',
        '.wav',
        '.avi',
        '.mov',
        '.mkv',
        '.exe',
        '.dll',
        '.so',
        '.dylib',
        '.pyc',
        '.pyo',
        '.woff',
        '.woff2',
        '.ttf',
        '.otf',
        '.eot',
    }

    async def execute(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> str:
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return f"[ERROR] File not found: {file_path}"

        if not path.is_file():
            return f"[ERROR] Not a file: {file_path}"

        if path.suffix.lower() in self.BINARY_EXTENSIONS:
            size = path.stat().st_size
            return (f"[INFO] Binary file ({path.suffix}, {size} bytes): {path.name}. "
                    f"Cannot read as text. If this is an image, it may already be "
                    f"available as multimodal content in the conversation.")

        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
            if b"\x00" in chunk:
                size = path.stat().st_size
                return f"[INFO] Binary file ({size} bytes): {path.name}. Cannot read as text."
        except Exception:
            pass

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            start = (offset or 1) - 1  # Convert 1-indexed to 0-indexed
            end = start + (limit or len(lines))
            selected = lines[start:end]

            # Format with line numbers
            result = []
            for i, line in enumerate(selected, start=(offset or 1)):
                result.append(f"{i:6}\t{line.rstrip()}")

            return "\n".join(result)
        except Exception as e:
            return f"[ERROR] Failed to read file: {e}"


class GrepTool(BaseTool):
    """Grep tool for pattern searching."""

    name = "Grep"
    description = "Search for patterns in files using regex."

    def get_schema(self) -> Dict[str, Any]:
        return GREP_TOOL_SCHEMA

    async def execute(
        self,
        pattern: str,
        path: str,
        glob: Optional[str] = None,
    ) -> str:
        search_path = Path(path).expanduser().resolve()

        if not search_path.exists():
            return f"[ERROR] Path not found: {path}"

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"[ERROR] Invalid regex pattern: {e}"

        results = []
        files_to_search = []

        if search_path.is_file():
            files_to_search = [search_path]
        else:
            pattern_glob = glob or "**/*"
            files_to_search = list(search_path.glob(pattern_glob))

        for file_path in files_to_search:
            if not file_path.is_file():
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{file_path}:{line_num}: {line.rstrip()}")
            except Exception:
                continue

        if not results:
            return "[INFO] No matches found"

        return "\n".join(results[:100])  # Limit output


class GlobTool(BaseTool):
    """Glob tool for file pattern matching."""

    name = "Glob"
    description = "Find files matching a glob pattern."

    def get_schema(self) -> Dict[str, Any]:
        return GLOB_TOOL_SCHEMA

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
    ) -> str:
        base_path = Path(path).expanduser().resolve() if path else Path.cwd()

        if not base_path.exists():
            return f"[ERROR] Path not found: {path}"

        matches = list(base_path.glob(pattern))

        if not matches:
            return "[INFO] No files matched the pattern"

        # Format output
        results = []
        for m in matches[:200]:  # Limit output
            try:
                rel_path = m.relative_to(base_path)
                results.append(str(rel_path))
            except ValueError:
                results.append(str(m))

        return "\n".join(results)


class BashTool(BaseTool):
    """Bash tool for command execution."""

    name = "Bash"
    description = "Execute bash commands. Use for read-only operations only."

    # Dangerous commands that should be blocked
    BLOCKED_PATTERNS = [
        r"\brm\s+-rf",
        r"\brm\s+[^-]",  # rm without flags
        r"\bmkfs\b",
        r"\bdd\b",
        r"\bshutdown\b",
        r"\breboot\b",
        r">\s*/dev/",  # Writing to devices
        r"curl.*\|\s*bash",  # Piping curl to bash
        r"wget.*\|\s*bash",  # Piping wget to bash
    ]

    def get_schema(self) -> Dict[str, Any]:
        return BASH_TOOL_SCHEMA

    async def execute(self, command: str, timeout: int = 30) -> str:
        # Safety check
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return "[ERROR] Command blocked for safety: contains potentially dangerous operation"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            result_parts = []
            if stdout:
                result_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                result_parts.append(
                    f"[STDERR] {stderr.decode('utf-8', errors='replace')}")

            if proc.returncode != 0:
                result_parts.append(f"[ERROR] Exit code: {proc.returncode}")

            return "\n".join(result_parts) if result_parts else "[OK] Command completed"

        except asyncio.TimeoutError:
            return f"[ERROR] Command timed out after {timeout} seconds"
        except Exception as e:
            return f"[ERROR] Failed to execute command: {e}"


DELEGATE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "agent_id": {
            "type":
            "string",
            "description":
            "ID of the agent to delegate the task to (e.g., 'code-analyzer', 'literature-synthesis')",
        },
        "task_description": {
            "type":
            "string",
            "description":
            "Complete description of the task for the delegated agent to execute",
        },
        "task_inputs": {
            "type":
            "object",
            "description":
            ("Optional structured arguments for the delegated agent. These "
             "are exposed through ``Task.inputs`` and serialized into the "
             "worker prompt so an agent's pre_run hook (sibling hooks.py) "
             "can read structured fields directly — useful for fan-in "
             "steps that short-circuit the LLM. Prefer this field over "
             "embedding JSON inside task_description, since structured "
             "args avoid network-fragile string serialization."),
        },
        "image_paths": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Optional list of image paths relevant to the task",
        },
    },
    "required": ["agent_id", "task_description"],
}


class DelegateTaskTool(BaseTool):
    """Delegate work to another Agent instance in the Orchestrator."""

    name = "DelegateTask"
    description = "Delegate a specialized task to another agent. Use this when the task requires specialized skills like code analysis, paper structure analysis, etc."

    def __init__(self, orchestrator=None, workspace_dir: Optional[str] = None):
        """Initialize the DelegateTaskTool.

        Args:
            orchestrator: The AgentOrchestrator instance to delegate tasks through.
                          Can be set later if not available at initialization.
            workspace_dir: Optional workspace directory for persisting worker
                           artifacts. When set, full worker payloads are
                           written to ``<workspace>/worker_results/`` and only
                           a compact reference (output_path + preview) is
                           returned to the Coordinator. This keeps the
                           Coordinator's context window stable across long
                           pipelines (Slice 1.18 retro fix).
        """
        self.orchestrator = orchestrator
        self.workspace_dir: Optional[str] = workspace_dir
        # Per-instance counter so consecutive artifacts within one dispatch
        # get unique filenames even when multiple turns delegate to the same
        # agent (e.g. 3 parallel enzyme-kinetics-table-extractor calls).
        self._artifact_counter: int = 0

    def get_schema(self) -> Dict[str, Any]:
        return DELEGATE_TASK_SCHEMA

    async def execute(
        self,
        agent_id: str,
        task_description: str,
        task_inputs: Optional[Dict[str, Any]] = None,
        image_paths: Optional[List[str]] = None,
    ) -> str:
        if not self.orchestrator:
            return self._failure_response(agent_id,
                                          "Orchestrator not found for delegation.")

        if agent_id not in self.orchestrator.agents:
            available = list(self.orchestrator.agents.keys())
            return self._failure_response(
                agent_id,
                f"Agent '{agent_id}' not found. Available agents: {available}",
            )

        target_agent = self.orchestrator.agents[agent_id]

        if (err := validate_agent_inputs(task_inputs,
                                         getattr(target_agent, "inputs_schema", None))):
            return self._failure_response(agent_id, f"inputs schema violation: {err}")

        try:
            resolved_image_paths = list(image_paths or [])
            auto_resolve_on = getattr(target_agent, "auto_resolve_artifacts", False)
            logger.info(
                "DelegateTask non-det: agent_id=%s auto_resolve=%s "
                "image_paths_arg=%r task_inputs_keys=%r task_inputs_preview=%s",
                agent_id, auto_resolve_on, image_paths, list((task_inputs
                                                              or {}).keys()),
                json.dumps(task_inputs)[:400] if task_inputs else "<none>")
            if auto_resolve_on and task_inputs:
                extracted = self._extract_vision_image_paths(task_inputs)
                logger.info("DelegateTask auto-resolve mined %d image paths for %s: %r",
                            len(extracted), agent_id, extracted)
                resolved_image_paths.extend(extracted)

            from gptase.agents import Task
            task_obj = Task(description=task_description,
                            agent_id=agent_id,
                            inputs=task_inputs or {},
                            image_paths=resolved_image_paths)

            result = await self.orchestrator.agents[agent_id].process_task(task_obj)

            if result.get("status") == "error" or result.get("status") == "failed":
                return self._failure_response(
                    agent_id,
                    result.get("error", "Unknown error"),
                    status=result.get("status", "failed"),
                )

            data = result.get("data", {})
            content = data.get("content", str(data)) if isinstance(data,
                                                                   dict) else str(data)

            output_schema = getattr(target_agent, "output_schema", None)
            if output_schema is not None:
                if (err := validate_agent_output(content or "", output_schema)):
                    return self._failure_response(agent_id,
                                                  f"output schema violation: {err}")

            return self._build_response(
                agent_id=agent_id,
                status=result.get("status", "success"),
                content=content or "",
            )

        except Exception as e:
            return self._failure_response(
                agent_id, f"Failed to delegate task to {agent_id}: {e}")

    _PREVIEW_CHARS = 1500

    @staticmethod
    def _failure_response(
        agent_id: str,
        error_msg: str,
        status: str = "failed",
    ) -> str:
        """JSON-encode a DelegateTask failure for the Coordinator.

        Consolidates the eight previously-inlined json.dumps blobs that
        all shared the {agent_id, status, content="", error} shape but
        varied only by message and (rarely) status.
        """
        return json.dumps(
            {
                "agent_id": agent_id,
                "status": status,
                "content": "",
                "error": error_msg,
            },
            ensure_ascii=False,
        )

    def _build_response(
        self,
        agent_id: str,
        status: str,
        content: str,
        error: Optional[str] = None,
    ) -> str:
        """Build the JSON response returned to the Coordinator.

        When a ``workspace_dir`` is configured, full content is persisted
        to a worker-results artifact file and the response carries only a
        compact reference (``output_path`` + ``content_preview``). This
        keeps the Coordinator's context size O(1) regardless of worker
        output size — large fan-in steps no longer balloon the followup
        prompt.

        When no workspace is set (e.g. unit tests), the legacy full
        ``content`` field is preserved for backward compatibility.
        """
        if not self.workspace_dir:
            payload = {
                "agent_id": agent_id,
                "status": status,
                "content": content,
                "error": error,
            }
            return json.dumps(payload, ensure_ascii=False)

        artifact_path = self._save_artifact(agent_id, status, content, error)
        preview = content[:self._PREVIEW_CHARS]
        truncated = len(content) > self._PREVIEW_CHARS
        payload = {
            "agent_id": agent_id,
            "status": status,
            "output_path": str(artifact_path) if artifact_path else None,
            "content_chars": len(content),
            "content_preview": preview + ("…" if truncated else ""),
            "error": error,
        }
        return json.dumps(payload, ensure_ascii=False)

    def _save_artifact(
        self,
        agent_id: str,
        status: str,
        content: str,
        error: Optional[str],
    ) -> Optional[Path]:
        """Persist a worker payload to ``<workspace>/worker_results/``.

        Returns the absolute artifact path, or None on filesystem error.
        Filenames are ``<NN>_<agent_id>.json`` where NN is a zero-padded
        per-instance counter so chronological order is preserved and
        sibling files (e.g. 3 parallel extractor replicas in the same
        turn) get distinct names.
        """
        if not self.workspace_dir:
            return None
        try:
            workspace = Path(self.workspace_dir)
            results_dir = workspace / "worker_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            self._artifact_counter += 1
            fname = f"{self._artifact_counter:03d}_{agent_id}.json"
            path = results_dir / fname
            payload = {
                "agent_id": agent_id,
                "status": status,
                "content": content,
                "error": error,
            }
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return path
        except OSError as exc:
            logger.warning("DelegateTask artifact write failed (%s/%s): %s",
                           self.workspace_dir, agent_id, exc)
            return None

    def _extract_vision_image_paths(self, task_inputs: Dict[str, Any]) -> List[str]:
        """Mine `images[].image_path` entries from upstream artifact paths.

        Used by ``execute`` when the target agent has frontmatter
        ``auto_resolve_artifacts: true``. Walks
        ``task_inputs`` values, treats any string-shaped value (or list of
        strings) as a possible upstream worker artifact, parses its envelope
        via ``_maybe_load_artifacts``, then descends into the parsed payload
        looking for an ``images`` array of ``{"image_path": "..."}`` entries.

        Relative ``image_path`` values are resolved against the artifact's
        own ``source_file`` parent directory (the natural base for MinerU-
        produced markdowns whose images sit alongside the .md file).
        ``self.workspace_dir`` is used only as a fallback for artifacts that
        don't expose ``source_file``. Files that don't exist on disk are
        filtered out so ``Agent._load_image_as_content`` doesn't raise.

        Returns a deduplicated list of absolute paths, preserving first-seen
        order. Empty list when no images can be resolved.
        """
        out: List[str] = []
        seen: Set[str] = set()
        fallback = Path(self.workspace_dir) if self.workspace_dir else None
        for value in task_inputs.values():
            loaded = self._maybe_load_artifacts(value)
            payloads = loaded if isinstance(loaded, list) else [loaded]
            for payload in payloads:
                base = fallback
                if isinstance(payload, dict):
                    src = payload.get("source_file")
                    if isinstance(src, str) and src:
                        parent = Path(src).expanduser().parent
                        if parent.is_dir():
                            base = parent
                for entry in self._iter_image_entries(payload):
                    if not isinstance(entry, dict):
                        continue
                    raw = entry.get("image_path")
                    if not isinstance(raw, str) or not raw:
                        continue
                    p = Path(raw).expanduser()
                    if not p.is_absolute() and base is not None:
                        p = (base / raw).resolve()
                    else:
                        p = p.resolve()
                    key = str(p)
                    if key in seen:
                        continue
                    if p.is_file():
                        seen.add(key)
                        out.append(key)
        return out

    def _iter_image_entries(self, payload: Any) -> Iterable[Any]:
        """Walk a parsed artifact payload yielding entries from any `images` array."""
        if isinstance(payload, list):
            for item in payload:
                yield from self._iter_image_entries(item)
        elif isinstance(payload, dict):
            imgs = payload.get("images")
            if isinstance(imgs, list):
                for entry in imgs:
                    yield entry

    def _maybe_load_artifacts(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._maybe_load_artifacts(v) for v in value]
        if isinstance(value, str):
            loaded = self._try_load_artifact(value)
            if loaded is not None:
                return loaded
            return value
        return value

    def _try_load_artifact(self, candidate: str) -> Optional[Any]:
        """Attempt to interpret ``candidate`` as an artifact path.

        Returns the unwrapped worker payload when the path exists and is
        a JSON file written by ``_save_artifact`` (i.e. has the wrapper
        envelope). Returns None for non-paths or non-artifacts so the
        caller can pass the value through.
        """
        if not candidate or len(candidate) > 2048:
            return None
        # Heuristic: only attempt to load strings that look like a path
        # AND exist on disk. Normal short strings (e.g. "/data/paper.md")
        # that aren't artifacts will fall through unmodified.
        path = Path(candidate)
        if not path.is_file():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not (isinstance(envelope, dict) and "agent_id" in envelope
                and "content" in envelope):
            return None
        # Unwrap the artifact: parse the inner ``content`` as JSON when
        # possible, else return it as-is so the tool gets back what the
        # worker produced.
        content = envelope.get("content", "")
        parsed = _try_parse_json_object(content) if isinstance(content,
                                                               str) else content
        return parsed if parsed is not None else content


def _try_parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from a free-form string.

    Returns the parsed dict, or None when no balanced top-level object can
    be recovered. Handles the common ```json ... ``` fenced-block form and
    raw object literals.
    """
    if not isinstance(text, str):
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        # Strip ```json or ``` fence
        first_newline = candidate.find("\n")
        if first_newline != -1:
            candidate = candidate[first_newline + 1:]
        if candidate.endswith("```"):
            candidate = candidate[:-3]
        candidate = candidate.strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Scan for the first balanced {...} block.
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    parsed = json.loads(text[start:i + 1])
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    start = -1
                    continue
    return None


def register_default_tools(registry: "ToolRegistry") -> None:
    """Register the default set of tools.

    Args:
        registry: The ToolRegistry instance to register tools with.
    """
    registry.register(ReadTool())
    registry.register(GrepTool())
    registry.register(GlobTool())
    registry.register(BashTool())

    # DelegateTaskTool should be imported from orchestrator to avoid circular imports if needed,
    # or we define it here and use it in orchestrator.
    # We will define DelegateTaskTool here.
    registry.register(DelegateTaskTool())
    logger.info("Registered default tools: Read, Grep, Glob, Bash, DelegateTask")
