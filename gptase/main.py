"""CLI entry point for GPTase."""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import re
import sys
from typing import List, Optional

from .core.orchestrator import AgentOrchestrator
from .core.types import DispatchRequest
from .utils.config import FrameworkConfig

logger = logging.getLogger(__name__)

# Subdirectory name patterns that typically hold a paper's supplementary
# information markdown (MinerU's output layout). Matched as a regex against
# the directory's basename, case-insensitive.
_SI_SUBDIR_PATTERNS: List[str] = [
    r"^SI(_|$)",
    r"^MOESM\d+",
    r"^supplementary",
    r"^supplemental",
    r"_SI($|_)",
]


def _detect_supplementary_path(document_path: str) -> Optional[str]:
    """Best-effort discovery of a paper's supplementary-information markdown.

    Resolution order:
      1. Sibling file ``<stem>_si.<suffix>`` next to ``document_path``.
      2. First subdirectory in the document's parent that matches one of
         ``_SI_SUBDIR_PATTERNS`` (case-insensitive, alphabetical) AND
         contains a ``main.md`` (MinerU's output convention).
    """
    if not document_path:
        return None
    doc = Path(document_path)
    if not doc.exists():
        return None

    if doc.is_file():
        sibling = doc.with_name(doc.stem + "_si" + doc.suffix)
        if sibling.exists():
            return str(sibling)

    parent = doc.parent if doc.is_file() else doc
    if not parent.is_dir():
        return None

    for child in sorted(parent.iterdir()):
        if not child.is_dir():
            continue
        for pattern in _SI_SUBDIR_PATTERNS:
            if re.search(pattern, child.name, re.IGNORECASE):
                main_md = child / "main.md"
                if main_md.exists():
                    return str(main_md)
                break
    return None


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add shared args (--debug) to a sub-parser."""
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gptase",
        description="GPTase - Multi-Agent Framework for AI Task Automation",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── Three core modes ──────────────────────────────────────

    # chat: Auto Orchestrator (interactive runtime → direct answer / coordinator / plan handoff)
    chat_p = sub.add_parser("chat", help="Auto Orchestrator mode")
    chat_p.add_argument("description",
                        type=str,
                        nargs="?",
                        default=None,
                        help="Task description (prompted if omitted)")
    chat_p.add_argument("-p",
                        "--plan",
                        type=str,
                        default=None,
                        metavar="PLAN_ID",
                        help="Seed the coordinator with a structured plan prompt from "
                        "config/plans/<PLAN_ID>.md")
    chat_p.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        metavar="FILE",
        help="Input document path (resolves {{document_path}} in plan prompts)")
    chat_p.add_argument("-o",
                        "--output",
                        type=str,
                        default=None,
                        metavar="DIR",
                        help="Workspace directory for plan-driven runs")
    chat_p.add_argument("--si",
                        type=str,
                        default=None,
                        metavar="PATH",
                        help="Explicit supplementary-information document path "
                        "(overrides auto-detection)")
    _add_common_args(chat_p)

    # agent: Direct single-agent execution
    agent_p = sub.add_parser("agent", help="Run a single agent directly")
    agent_p.add_argument("-n", "--name", type=str, required=True, help="Agent name")
    agent_p.add_argument("-d",
                         "--description",
                         type=str,
                         default=None,
                         help="Task description")
    _add_common_args(agent_p)

    # ── Utility commands ──────────────────────────────────────

    sub.add_parser("list", help="List available agents")
    sub.add_parser("status", help="Show system status")

    mem_p = sub.add_parser("memory", help="Inspect agent working memory")
    mem_p.add_argument("--agent", type=str, required=True, help="Agent ID to inspect")

    eval_p = sub.add_parser("eval", help="Evaluate agent output quality")
    eval_p.add_argument("-a", "--agent", type=str, required=True, help="Agent name")
    eval_p.add_argument("--live", action="store_true", help="Run live against LLM API")
    eval_p.add_argument("--save-output",
                        action="store_true",
                        help="Save live output to evals directory")
    eval_p.add_argument("--save",
                        type=str,
                        default=None,
                        help="Save JSON report to file")
    eval_p.add_argument("--config",
                        type=str,
                        default=None,
                        metavar="FILE",
                        help="LLM config JSON for live runs")

    web_p = sub.add_parser("web", help="Start the Web UI")
    web_p.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    web_p.add_argument("--host",
                       type=str,
                       default="127.0.0.1",
                       help="Host (default: 127.0.0.1)")

    return parser.parse_args()


async def run_chat(args: argparse.Namespace) -> int:
    """Auto Orchestrator mode: interactive runtime with optional plan seed."""
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    plan_id = getattr(args, "plan", None)
    input_path = getattr(args, "input", None)
    output_dir = getattr(args, "output", None)
    si_override = getattr(args, "si", None)

    description = args.description
    workspace_dir: Optional[str] = None

    if plan_id:
        # Plan-seeded chat: load a pre-rendered prompt from
        # config/plans/<plan_id>.md and substitute the runtime variables.
        if not input_path:
            logger.error("[ERROR] -p/--plan requires -i/--input <document>")
            return 1
        doc_path = Path(input_path)
        if not doc_path.exists():
            logger.error("[ERROR] Input file not found: %s", input_path)
            return 1

        from .utils.paths import get_paths
        plan_path = (get_paths().project_root / "config" / "plans" / f"{plan_id}.md")
        if not plan_path.is_file():
            logger.error("[ERROR] Plan not found: %s", plan_path)
            return 1

        if output_dir:
            workspace = Path(output_dir)
        else:
            from datetime import datetime as _dt
            ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            base = doc_path if doc_path.is_dir() else doc_path.parent
            workspace = base / f"{plan_id}_{ts}"
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_dir = str(workspace)

        # Resolve SI document: explicit --si wins over auto-detection.
        si_path: Optional[str] = None
        if si_override:
            override_path = Path(si_override)
            if not override_path.exists():
                logger.error("[ERROR] --si path not found: %s", si_override)
                return 1
            si_path = str(override_path)
            logger.info("[INFO] Using explicit SI document: %s", si_path)
        else:
            si_path = _detect_supplementary_path(str(doc_path))
            if si_path:
                logger.info("[INFO] Auto-detected SI document: %s", si_path)

        description = (plan_path.read_text(encoding="utf-8").replace(
            "{{document_path}}",
            str(doc_path)).replace("{{si_document_path}}", si_path
                                   or "").replace("{{workspace_dir}}", workspace_dir))

    if not description:
        description = input("gptase> ").strip()
        if not description:
            return 0

    orchestrator = AgentOrchestrator(FrameworkConfig())
    try:
        result = await orchestrator.dispatch(
            DispatchRequest(
                query=description,
                auto_execute=True,
                document_path=input_path if plan_id else None,
                workspace_dir=workspace_dir,
            ))
    finally:
        await orchestrator.close()

    # Persist trace + final answer when running with a plan + workspace.
    if plan_id and workspace_dir:
        _dump_chat_plan_artifacts(workspace_dir, plan_id, result)

    if result.get("status") == "failed":
        logger.error("[ERROR] %s", result.get("error"))
        return 1

    data = result.get("data")
    if data and isinstance(data, dict):
        print(data.get("content", ""))
    elif data:
        print(data)
    return 0


def _dump_chat_plan_artifacts(workspace_dir: str, plan_id: str, result: dict) -> None:
    """Write the full coordinator result + per-step worker outputs to disk.

    Layout (mirrors `_organize_plan_output` for legacy plan runs, but only
    writes what the coordinator actually produced — no schema rewriting):

        <workspace_dir>/
          <plan_id>_result.json     full dispatch result (trace + data)
          worker_results/
            turn<N>_<idx>_<agent_id>.json    one file per delegated worker
    """
    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)

    full_path = workspace / f"{plan_id}_result.json"
    full_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info("[INFO] Saved full result to %s", full_path)

    runtime = ((result.get("trace") or {}).get("runtime") or {})
    coordinator = runtime.get("coordinator") or {}
    turns = coordinator.get("turns") or []
    if not turns:
        return

    worker_dir = workspace / "worker_results"
    worker_dir.mkdir(parents=True, exist_ok=True)
    for turn in turns:
        turn_idx = turn.get("turn_index", "?")
        for idx, wr in enumerate(turn.get("worker_results") or []):
            agent_id = wr.get("agent_id", "unknown").replace("/", "_")
            out_path = worker_dir / f"turn{turn_idx}_{idx:02d}_{agent_id}.json"
            payload = {
                "agent_id": agent_id,
                "status": wr.get("status"),
                "error": wr.get("error"),
                "content": wr.get("content"),
            }
            out_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )


async def run_agent(args: argparse.Namespace) -> int:
    """Run a single agent.

    Args:
        args: Parsed command-line arguments with name and description.
    """
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    from gptase.agents.base import Agent
    from gptase.models.model import Model

    description = args.description
    if not description:
        logger.error("[ERROR] Task description required. Use -d/--description")
        return 1

    # Initialize model
    model = Model()

    # Create agent from markdown definition
    agent_name = args.name
    try:
        agent = Agent.from_markdown(agent_name, model_manager=model)
    except FileNotFoundError:
        logger.error("[ERROR] Agent not found: %s", agent_name)
        logger.info("[INFO] Available agents: %s", ", ".join(_list_agent_names()))
        return 1

    logger.info("[INFO] Running agent: %s", agent_name)

    # Run agent
    result = await agent.run(prompt=description)

    if result.get("status") == "error":
        logger.error("[ERROR] Agent execution failed: %s", result.get("error"))
        return 1

    logger.info("[OK] Agent completed successfully")

    # Print output
    output = result.get("data", {}).get("content", "")
    print(output)
    return 0


def _list_agent_names() -> list:
    """List available agent names (flat and directory layouts)."""
    from gptase.agents.base import list_agent_md_files

    agents_dir = Path(__file__).parent.parent / ".claude" / "agents"
    if not agents_dir.exists():
        return []
    return [f.stem for f in list_agent_md_files(agents_dir)]


async def list_agents() -> int:
    """List available agents."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    agents = await orchestrator.list_available_agents()

    print("Available Agents:")
    print("-" * 50)
    for agent in agents:
        print(f"  {agent['agent_id']}")
        print(f"    Type: {agent['type']}")
        print()

    return 0


async def show_status() -> int:
    """Show system status."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    status = await orchestrator.get_system_status()

    print("System Status:")
    print("-" * 50)
    print(f"  Timestamp: {status['timestamp']}")
    print(f"  Active Agents: {len(status['agents'])}")
    print(f"  Memory Usage: {status['memory']}")

    return 0


async def show_agent_memory(args: argparse.Namespace) -> int:
    """Show compressed working memory for a named agent."""
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    payload = await orchestrator.get_agent_working_memory(args.agent)
    memory = payload.get("working_memory")

    print(f"Agent Memory: {args.agent}")
    print("-" * 50)
    if not memory:
        print("  No working memory stored.")
        return 0

    print(f"  Last Updated: {memory['last_updated']}")
    if memory.get("metadata"):
        print(f"  Metadata: {memory['metadata']}")
    print("  Summary:")
    for line in str(memory["summary"]).splitlines():
        print(f"    {line}")
    return 0


async def run_eval(args: argparse.Namespace) -> int:
    """Run agent output quality evaluation.

    Args:
        args: Parsed command-line arguments.
    """
    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    from gptase.evals.report import print_eval_report
    from gptase.evals.report import save_eval_report
    from gptase.evals.runner import EvalRunner

    config_path = args.config

    try:
        runner = EvalRunner(agent_name=args.agent, config_path=config_path)
    except FileNotFoundError as exc:
        logger.error("[ERROR] %s", exc)
        return 1

    result = await runner.eval_agent(live=args.live, save_output=args.save_output)
    results = [result]

    print_eval_report(results)

    if args.save:
        save_eval_report(results, args.save)
        print(f"[INFO] Report saved to: {args.save}")

    all_passed = all(r.schema_valid and r.score == 1.0 for r in results)
    return 0 if all_passed else 1


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.command is None:
        print("GPTase - Multi-Agent Framework")
        print("Use 'gptase --help' for usage information.")
        return 0

    if args.command == "chat":
        return asyncio.run(run_chat(args))
    elif args.command == "agent":
        return asyncio.run(run_agent(args))
    elif args.command == "list":
        return asyncio.run(list_agents())
    elif args.command == "status":
        return asyncio.run(show_status())
    elif args.command == "memory":
        return asyncio.run(show_agent_memory(args))
    elif args.command == "eval":
        return asyncio.run(run_eval(args))
    elif args.command == "web":
        import threading
        import webbrowser

        import uvicorn

        from gptase.web.server import app

        url = f"http://{args.host}:{args.port}"
        print(f"Starting GPTase Web UI on {url}")

        # Open browser in a separate thread after a short delay
        def open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()

        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
