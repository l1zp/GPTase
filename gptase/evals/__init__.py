"""Agent evaluation framework for GPTase.

Provides three-tier evaluation of agent output quality:
  1. Schema validation -- correct JSON structure (Pydantic)
  2. Key fact assertions -- important values present and correct
  3. Completeness metrics -- recall of expected entities

Usage:
    from gptase.evals import run_eval, EvalResult, EvalRunner

    runner = EvalRunner(paper_id="listov2025")
    results = await runner.eval_all()
"""

from gptase.evals.assertions import EvalResult
from gptase.evals.runner import EvalRunner


async def run_eval(
    paper_id: str,
    agent_name: str = None,
    live: bool = False,
    cache_dir: str = None,
):
    """Run evaluation for a paper.

    Args:
        paper_id: Paper identifier (must have a golden.yaml in data/evals/).
        agent_name: Single agent to evaluate; if None, evaluates all.
        live: If True, run agents live against the LLM API.
        cache_dir: Custom directory with cached agent outputs.

    Returns:
        List of EvalResult objects.
    """
    runner = EvalRunner(paper_id=paper_id, cache_dir=cache_dir)
    if agent_name:
        result = await runner.eval_agent(agent_name, live=live)
        return [result]
    return await runner.eval_all(live=live)


__all__ = ["run_eval", "EvalResult", "EvalRunner"]
