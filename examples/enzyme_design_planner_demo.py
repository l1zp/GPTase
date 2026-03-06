#!/usr/bin/env python3
"""Interactive demonstration of enzyme design workflow planning.

This script demonstrates how to use the Planner agent to analyze an enzyme
design paper and create a reproduction plan for the design workflow.
"""

import asyncio
import json
import logging
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")
    logger.info("Starting phase: %s", title)


def print_phase_result(phase: int, result: dict) -> None:
    """Print phase result summary."""
    print(f"\n[PHASE {phase} COMPLETE]")
    data = result.get("data", {})
    print(f"  Plan ID: {data.get('plan_id', 'N/A')}")
    print(f"  Status: {data.get('plan_status', 'N/A')}")
    print(f"  Next Phase: {data.get('next_phase', 'N/A')}")
    print(f"  Ready to Execute: {data.get('ready_to_execute', False)}")

    logger.info(
        "Phase %d complete: plan_id=%s, status=%s, next_phase=%s",
        phase,
        data.get("plan_id"),
        data.get("plan_status"),
        data.get("next_phase"),
    )


def load_paper_content(paper_path: str) -> str:
    """Load paper content from markdown file.

    Args:
        paper_path: Path to the paper markdown file.

    Returns:
        Paper content as string.
    """
    paper_file = Path(paper_path)

    if not paper_file.exists():
        raise FileNotFoundError(f"Paper file not found: {paper_path}")

    logger.info("Loading paper from: %s", paper_file)
    content = paper_file.read_text(encoding="utf-8")

    # Truncate content if too large for planning context
    max_chars = 50000  # Limit for planning phase
    if len(content) > max_chars:
        logger.warning(
            "Paper content truncated from %d to %d characters for planning",
            len(content),
            max_chars,
        )
        content = content[:max_chars] + "\n\n[Content truncated...]"

    return content


async def run_enzyme_design_planning(
    paper_path: str,
    auto_approve: bool = False,
) -> None:
    """Run enzyme design workflow planning.

    Args:
        paper_path: Path to the enzyme design paper (markdown file).
        auto_approve: If True, automatically approve all phases.
    """
    print_section("Enzyme Design Workflow Planner")

    # Load paper content
    try:
        paper_content = load_paper_content(paper_path)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        print("\nPlease provide a valid path to the paper markdown file.")
        print("Example: data/listov2025/listov2025.md")
        return

    print(f"[OK] Paper loaded: {paper_path}")
    print(f"     Content length: {len(paper_content)} characters")

    # Task description for enzyme design planning
    task_description = f"""
I need to analyze an enzyme design paper and create a reproduction plan.

Paper path: {paper_path}

Paper content:
{paper_content}

I want to:
1. Extract the complete enzyme design workflow described in the paper
2. Identify the key design steps, techniques, and methodologies used
3. Extract design objectives, constraints, and optimization strategies
4. Generate a detailed reproduction plan that could be used to replicate
   the design workflow in a computational or experimental setting

Please create a comprehensive plan for reproducing this enzyme design workflow.
"""

    print("\n[OBJECTIVES]")
    print("  1. Extract enzyme design workflow")
    print("  2. Identify design steps and methodologies")
    print("  3. Extract optimization strategies")
    print("  4. Generate reproduction plan")

    logger.info("Starting enzyme design planning: paper=%s, auto_approve=%s",
                paper_path, auto_approve)

    # Initialize orchestrator
    print_section("Initializing Agent Orchestrator")
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    # Check available agents
    agents = await orchestrator.list_available_agents()
    print(f"Available Agents: {len(agents)}")

    enzyme_agents = [
        a for a in agents
        if "enzyme" in a["agent_id"].lower() or "design" in a["agent_id"].lower()
    ]

    print(f"\nEnzyme Design Agents: {len(enzyme_agents)}")
    for agent in enzyme_agents:
        print(f"  - {agent['agent_id']}: {', '.join(agent['capabilities'][:2])}")

    logger.info("Initialized orchestrator with %d agents (%d enzyme-related)",
                len(agents), len(enzyme_agents))

    # ==========================================================================
    # Phase 1: Initial Understanding
    # ==========================================================================
    print_section("Phase 1: Initial Understanding")

    if auto_approve:
        print("Auto-approve mode: Providing default answers...")
        user_input = """
- Objectives: Extract complete enzyme design workflow and create reproduction plan
- Constraints: Follow the methodology described in the paper, identify all key steps
- Resources: Paper content provided above
- Outputs: Detailed reproduction plan with step-by-step workflow
"""
    else:
        print("\n[PLANNER ASKS]")
        print("The planner needs to understand your requirements.")
        print("Please answer the following questions:")
        print("(Press Enter to use default answers)")
        user_input = input("\nYour answers: ") or """
- Objectives: Extract complete enzyme design workflow and create reproduction plan
- Constraints: Follow the methodology described in the paper, identify all key steps
- Resources: Paper content provided above
- Outputs: Detailed reproduction plan with step-by-step workflow
"""

    task = {
        "id": "enzyme_design_planning_001",
        "description": task_description,
        "use_planner": True,
        "phase": 1,
        "user_input": user_input,
    }

    result = await orchestrator.execute_task(task)
    print_phase_result(1, result)

    plan_id = result.get("plan_id")
    logger.info("Created plan: %s", plan_id)

    # ==========================================================================
    # Phase 2: Design Approach
    # ==========================================================================
    print_section("Phase 2: Design Approach")

    if auto_approve:
        print("Auto-approve mode: Accepting proposed approach...")
        user_input = ("The approach looks good. Please proceed with extracting "
                      "the design workflow in detail.")
    else:
        print("\n[PLANNER PRESENTS APPROACH]")
        print("Review the proposed workflow extraction strategy.")
        user_input = input("\nYour feedback: ") or (
            "The approach looks good. Please proceed with extracting "
            "the design workflow in detail.")

    task["plan_id"] = plan_id
    task["phase"] = 2
    task["user_input"] = user_input

    result = await orchestrator.execute_task(task)
    print_phase_result(2, result)

    # ==========================================================================
    # Phase 3: Review and Validation
    # ==========================================================================
    print_section("Phase 3: Review and Validation")

    if auto_approve:
        print("Auto-approve mode: Approving plan...")
        user_input = "Approved. Please proceed to final plan generation."
    else:
        print("\n[PLANNER PRESENTS PLAN SUMMARY]")
        print("Review the extracted enzyme design workflow.")
        approved = input("\nApprove this plan? (y/n): ").lower()
        user_input = ("Approved. Please proceed." if approved == "y" else
                      "I have concerns: " + input("Enter concerns: "))

    task["phase"] = 3
    task["user_input"] = user_input

    result = await orchestrator.execute_task(task)
    print_phase_result(3, result)

    # ==========================================================================
    # Phase 4: Final Plan Generation
    # ==========================================================================
    print_section("Phase 4: Final Plan Generation")

    task["phase"] = 4
    task["user_input"] = ""

    result = await orchestrator.execute_task(task)
    print_phase_result(4, result)

    # ==========================================================================
    # Phase 5: Exit and Approval
    # ==========================================================================
    print_section("Phase 5: Final Approval")

    if auto_approve:
        print("Auto-approve mode: Confirming execution...")
        user_input = "Confirmed. Ready to generate the reproduction plan."
    else:
        print("\n[PLANNER REQUESTS FINAL CONFIRMATION]")
        print("The reproduction plan is ready.")
        user_input = input("\nConfirm plan generation? (yes/no): ").lower()
        user_input = ("Confirmed. Ready to generate the reproduction plan."
                      if user_input == "yes" else "Need more time.")

    task["phase"] = 5
    task["user_input"] = user_input

    result = await orchestrator.execute_task(task)
    print_phase_result(5, result)

    # ==========================================================================
    # Save Reproduction Plan
    # ==========================================================================
    if result.get("ready_to_execute"):
        print_section("Reproduction Plan Generated")

        print(f"\nPlan ID: {plan_id}")
        print(f"Plan file: data/plans/{plan_id}.json")

        # Load and display the plan
        plan_file_path = Path(f"data/plans/{plan_id}.json")
        if plan_file_path.exists():
            with open(plan_file_path, "r", encoding="utf-8") as f:
                plan_data = json.load(f)

            print("\n[PLAN SUMMARY]")
            print(f"  Name: {plan_data.get('name', 'N/A')}")
            print(f"  Description: {plan_data.get('description', 'N/A')}")
            print(f"  Total Steps: {len(plan_data.get('workflow', []))}")

            workflow = plan_data.get("workflow", [])
            print("\n[WORKFLOW STEPS]")
            for i, step in enumerate(workflow, 1):
                print(f"\n  Step {i}:")
                print(f"    Agent: {step.get('agent', 'N/A')}")
                print(f"    Action: {step.get('action', 'N/A')}")
                print(f"    Description: {step.get('description', 'N/A')}")

            # Save as reproduction plan
            reproduction_plan_path = Path("data/plans") / f"reproduction_{plan_id}.json"
            with open(reproduction_plan_path, "w", encoding="utf-8") as f:
                json.dump(plan_data, f, indent=2, ensure_ascii=False)

            print(f"\n[OK] Reproduction plan saved: {reproduction_plan_path}")

            if auto_approve:
                print("\nAuto-approve mode: Executing extraction workflow...")
                execute = True
            else:
                execute = input(
                    "\nExecute the extraction workflow now? (y/n): ").lower() == "y"

            if execute:
                print_section("Executing Extraction Workflow")

                exec_task = {
                    "id": "enzyme_design_extraction_001",
                    "plan_id": plan_id,
                    "text": paper_content[:100000],  # Use more content for extraction
                }

                exec_result = await orchestrator.execute_task(exec_task)

                print("\n[EXTRACTION COMPLETE]")
                summary = exec_result.get("execution_summary", {})
                print(f"  Total Steps: {summary.get('total_steps', 0)}")
                print(f"  Completed: {summary.get('completed_steps', 0)}")
                print(f"  Failed: {summary.get('failed_steps', 0)}")
                print(f"  Success Rate: {summary.get('success_rate', 0):.1%}")
                print(f"  Status: {summary.get('status', 'unknown')}")

                # Save extraction results
                output_path = Path("data/output") / f"extraction_{plan_id}.json"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(exec_result, f, indent=2, ensure_ascii=False)

                print(f"\n[OK] Extraction results saved: {output_path}")
        else:
            print(f"\n[WARNING] Plan file not found: {plan_file_path}")
    else:
        print_section("Planning Complete - Plan Not Approved")
        print("The reproduction plan was not approved.")
        print("You can continue planning by re-running with the plan_id.")

    # Cleanup
    print_section("Cleanup")
    await orchestrator.shutdown()
    print("Orchestrator shutdown complete.")
    logger.info("Demo completed successfully")


async def run_quick_demo(paper_path: str) -> None:
    """Run a quick demonstration with auto-approval.

    Args:
        paper_path: Path to the enzyme design paper.
    """
    print("Running quick demo with auto-approval enabled...\n")
    await run_enzyme_design_planning(paper_path, auto_approve=True)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Enzyme Design Workflow Planner Demo")
    parser.add_argument(
        "paper",
        help="Path to the enzyme design paper (markdown file)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run in auto-approve mode (for testing/CI)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick demo (alias for --auto)",
    )

    args = parser.parse_args()

    logger.info(
        "Starting enzyme design planner demo: paper=%s, auto=%s, quick=%s",
        args.paper,
        args.auto,
        args.quick,
    )

    if args.quick:
        asyncio.run(run_quick_demo(args.paper))
    else:
        asyncio.run(run_enzyme_design_planning(args.paper, auto_approve=args.auto))


if __name__ == "__main__":
    main()
