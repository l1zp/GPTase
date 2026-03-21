"""Agent evaluation framework for GPTase.

Provides three-tier evaluation of agent output quality:
  1. Schema validation -- correct JSON structure (Pydantic)
  2. Key fact assertions -- important values present and correct
  3. Completeness metrics -- recall of expected entities

Usage:
    from gptase.evals import run_eval, EvalResult, EvalRunner

    runner = EvalRunner(agent_name="vision-image-analyzer")
    result = await runner.eval_agent()
"""

from typing import Optional

from gptase.evals.assertions import EvalResult
from gptase.evals.runner import EvalRunner
from gptase.evals.runner import run_eval as _run_eval


async def run_eval(
    agent_name: str,
    live: bool = False,
    save_output: bool = False,
    config_path: Optional[str] = None,
) -> EvalResult:
    """Run evaluation for an agent.

    Args:
        agent_name: Agent identifier (e.g., "vision-image-analyzer").
        live: If True, run agent live against the LLM API.
        save_output: If True, save live output to evals directory.
        config_path: Optional path to an llm_config JSON file for live runs.
            Supports the full format including agent_models overrides.

    Returns:
        EvalResult for this agent.
    """
    return await _run_eval(
        agent_name,
        live=live,
        save_output=save_output,
        config_path=config_path,
    )


__all__ = ["run_eval", "EvalResult", "EvalRunner"]
