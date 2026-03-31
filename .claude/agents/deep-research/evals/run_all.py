#!/usr/bin/env python3
"""Run all 3 deep-research eval cases in parallel and save results."""

import asyncio
from datetime import datetime
import json
from pathlib import Path

EVALS_DIR = Path(__file__).parent
AGENT_NAME = "deep-research"

CASES = [
    {
        "id":
        1,
        "name":
        "enzyme-engineering-strategy-comparison",
        "prompt":
        ("Compare directed evolution and rational design as strategies for engineering "
         "thermostable enzymes. We are a biotech team choosing between these approaches "
         "for an industrial enzyme project. Please cover: success rates and typical "
         "timelines, cost and equipment requirements, the quality of the resulting "
         "variants, recent breakthroughs, and common failure modes for each strategy."),
    },
    {
        "id":
        2,
        "name":
        "plastic-degrading-enzyme-landscape",
        "prompt":
        ("What is the current state of enzyme engineering for plastic degradation "
         "(PET, PEF, polyurethane, etc.)? Map the main enzyme candidates such as "
         "PETase, MHETase, and LCC variants, their key performance metrics (degradation "
         "rate, temperature range, substrate specificity), current limitations, and "
         "where the field is heading based on recent literature."),
    },
    {
        "id":
        3,
        "name":
        "enzyme-immobilization-strategy-recommendation",
        "prompt":
        ("We are designing a continuous flow biocatalysis process for cellulose "
         "hydrolysis and need to choose an enzyme immobilization strategy. Compare "
         "covalent binding, physical entrapment, and cross-linked enzyme aggregates "
         "(CLEAs) in terms of activity retention after immobilization, operational "
         "stability and reusability, scalability to industrial volumes, and typical "
         "failure modes in continuous flow conditions. Give a recommendation for our "
         "use case."),
    },
]


async def run_case(case: dict, model) -> dict:
    """Run a single eval case and return results."""
    from gptase.agents.base import Agent

    agent = Agent.from_markdown(AGENT_NAME, model_manager=model)
    result = await agent.run(content=case["prompt"])

    status = result.get("status")
    content = result.get("data", {}).get("content", "")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = EVALS_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = case["name"]
    if content:
        report_path = output_dir / f"report_{slug}_{timestamp}.md"
        report_path.write_text(content, encoding="utf-8")

        json_path = output_dir / f"output_{slug}_{timestamp}.json"
        json_path.write_text(
            json.dumps({"content": content}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {
        "id": case["id"],
        "name": case["name"],
        "status": status,
        "content_length": len(content),
        "saved": str(report_path) if content else None,
    }


async def main():
    from gptase.models.model import Model

    model = Model()
    print(f"Running {len(CASES)} eval cases in parallel...\n")

    tasks = [run_case(case, model) for case in CASES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    for r in results:
        if isinstance(r, Exception):
            print(f"[FAIL] {r}")
        else:
            status_tag = "[OK]" if r["status"] == "success" else "[FAIL]"
            print(f"{status_tag} Case {r['id']}: {r['name']}")
            print(f"      chars={r['content_length']}  saved={r['saved']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
