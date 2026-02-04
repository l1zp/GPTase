#!/usr/bin/env python3
"""Interactive demonstration of the 5-phase planning workflow.

This script shows how to use the Planner agent and the Orchestrator's
execution capability for complex enzyme design workflow planning.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig
from src.core.logging import setup_logging

# Configure logging
setup_logging("INFO")
logger = logging.getLogger(__name__)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")
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
        data.get('plan_id'),
        data.get('plan_status'),
        data.get('next_phase'),
    )


async def run_interactive_demo(auto_approve: bool = False) -> None:
    """Run interactive planning demonstration.

    Args:
        auto_approve: If True, automatically approve all phases.
    """
    print_section("GPTase Planner Demo - Enzyme Design Workflow")

    # Example task description
    task_description = """
    I need to analyze an enzyme design paper about lipase engineering.

    The paper is located at: data/listov2025.md

    I want to:
    1. Extract the complete enzyme design workflow
    2. Extract kinetic parameters for all variants
    3. Generate a comprehensive summary report

    Please create a plan for this analysis.
    """

    print("Task Description:")
    print(task_description)

    logger.info("Starting planning demo: auto_approve=%s", auto_approve)

    # Initialize orchestrator
    print_section("Initializing Agent Orchestrator")
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    # Check available agents
    agents = await orchestrator.list_available_agents()
    print(f"Available Agents: {len(agents)}")
    for agent in agents:
        print(f"  - {agent['agent_id']}: {', '.join(agent['capabilities'][:2])}")

    logger.info("Initialized orchestrator with %d agents", len(agents))

    # Phase 1: Initial Understanding
    print_section("Phase 1: Initial Understanding")

    if auto_approve:
        print("Auto-approve mode: Providing default answers...")
        user_input = """
        - Objectives: Extract design workflow and kinetics data
        - Constraints: Use existing tools, complete within 2 hours
        - Resources: Paper at data/listov2025.md
        - Outputs: JSON data + Markdown summary report
        """
    else:
        print("\n[PLANNER ASKS]")
        print("Please answer the following questions:")
        print("(Press Enter to use default answers)")
        user_input = input("\nYour answers: ") or """
        - Objectives: Extract design workflow and kinetics data
        - Constraints: Use existing tools, complete within 2 hours
        - Resources: Paper at data/listov2025.md
        - Outputs: JSON data + Markdown summary report
        """

    task = {
        "id": "demo_task_001",
        "description": task_description,
        "use_planner": True,
        "phase": 1,
        "user_input": user_input,
    }

    result = await orchestrator.execute_task(task)
    print_phase_result(1, result)

    plan_id = result.get("plan_id")
    logger.info("Created plan: %s", plan_id)

    # Phase 2: Design Approach
    print_section("Phase 2: Design Approach")

    if auto_approve:
        print("Auto-approve mode: Accepting proposed approach...")
        user_input = "The approach looks good, please proceed."
    else:
        print("\n[PLANNER PRESENTS APPROACH]")
        print("Review the proposed workflow steps.")
        user_input = input(
            "\nYour feedback: ") or "The approach looks good, please proceed."

    task["plan_id"] = plan_id
    task["phase"] = 2
    task["user_input"] = user_input

    result = await orchestrator.execute_task(task)
    print_phase_result(2, result)

    # Phase 3: Review and Validation
    print_section("Phase 3: Review and Validation")

    if auto_approve:
        print("Auto-approve mode: Approving plan...")
        user_input = "Approved, please proceed to final plan generation."
    else:
        print("\n[PLANNER PRESENTS PLAN SUMMARY]")
        print("Review the complete plan.")
        approved = input("\nApprove this plan? (y/n): ").lower()
        user_input = ("Approved, please proceed." if approved == "y" else
                      "I have concerns: " + input("Enter concerns: "))

    task["phase"] = 3
    task["user_input"] = user_input

    result = await orchestrator.execute_task(task)
    print_phase_result(3, result)

    # Phase 4: Final Plan Generation
    print_section("Phase 4: Final Plan Generation")

    task["phase"] = 4
    task["user_input"] = ""

    result = await orchestrator.execute_task(task)
    print_phase_result(4, result)

    # Phase 5: Exit and Approval
    print_section("Phase 5: Final Approval")

    if auto_approve:
        print("Auto-approve mode: Confirming execution...")
        user_input = "Confirmed, ready to execute."
    else:
        print("\n[PLANNER REQUESTS FINAL CONFIRMATION]")
        print("Plan is ready for execution.")
        user_input = input("\nConfirm execution? (yes/no): ").lower()
        user_input = "Confirmed, ready to execute." if user_input == "yes" else "Need more time."

    task["phase"] = 5
    task["user_input"] = user_input

    result = await orchestrator.execute_task(task)
    print_phase_result(5, result)

    # Check if ready to execute
    if result.get("ready_to_execute"):
        print_section("Plan Approved - Ready to Execute")

        print(f"\nPlan ID: {plan_id}")
        print(f"Plan file: data/plans/{plan_id}.json")

        if auto_approve:
            print("\nAuto-approve mode: Executing plan...")
            execute = True
        else:
            execute = input("\nExecute the plan now? (y/n): ").lower() == "y"

        if execute:
            print_section("Executing Plan")

            exec_task = {
                "id": "demo_task_001_exec",
                "plan_id": plan_id,
            }

            exec_result = await orchestrator.execute_task(exec_task)

            print("\n[EXECUTION COMPLETE]")
            summary = exec_result.get("execution_summary", {})
            print(f"  Total Steps: {summary.get('total_steps', 0)}")
            print(f"  Completed: {summary.get('completed_steps', 0)}")
            print(f"  Failed: {summary.get('failed_steps', 0)}")
            print(f"  Success Rate: {summary.get('success_rate', 0):.1%}")
            print(f"  Status: {summary.get('status', 'unknown')}")
        else:
            print("\nPlan saved but not executed.")
            print(f"To execute later, use:")
            print(f'  orchestrator.execute_task({{"plan_id": "{plan_id}"}})')
    else:
        print_section("Planning Complete - Plan Not Approved")
        print("The plan was not approved for execution.")
        print("You can continue planning by re-running with the plan_id.")

    # Cleanup
    print_section("Cleanup")
    await orchestrator.shutdown()
    print("Orchestrator shutdown complete.")
    logger.info("Demo completed successfully")


async def run_quick_demo() -> None:
    """Run a quick demonstration with auto-approval."""
    print("Running quick demo with auto-approval enabled...\n")
    await run_interactive_demo(auto_approve=True)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="GPTase Planner Demo")
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

    logger.info("Starting planner demo with args: auto=%s, quick=%s", args.auto,
                args.quick)

    if args.quick:
        asyncio.run(run_quick_demo())
    else:
        asyncio.run(run_interactive_demo(auto_approve=args.auto))


if __name__ == "__main__":
    main()
