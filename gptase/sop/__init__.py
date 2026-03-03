"""SOP (Standard Operating Procedure) execution system.

This module provides a complete system for defining and executing
workflows composed of agent tasks. It supports:

- YAML and JSON format SOP definitions
- Sequential and parallel step execution
- Template variable resolution for data flow
- AI-driven failure recovery (abort/skip/retry)
- Session tracking and persistence

Quick Start:
    from gptase.sop import SOPOrchestratorAgent, SOPRegistry

    # List available SOPs
    registry = SOPRegistry.get_instance()
    for sop in registry.list_sops():
        print(f"{sop['plan_id']}: {sop['name']}")

    # Execute an SOP
    orchestrator = SOPOrchestratorAgent()
    result = await orchestrator.execute_sop(
        plan_id="enzyme_extraction_pipeline",
        input_data={"text": "...", "document_path": "..."},
    )

Defining a New SOP:
    Create a YAML file in config/sops/my_pipeline.yaml:

    plan_id: my_pipeline
    name: My Pipeline
    description: What this pipeline does
    version: "1.0"

    workflow:
      - step_id: "1"
        agent: document_structure_analyzer
        action: analyze
        description: Analyze document structure
        inputs:
          text: "{{input_text}}"

      - parallel:
          - step_id: "2a"
            agent: extractor_a
            inputs:
              data: "{{step1}}"
          - step_id: "2b"
            agent: extractor_b
            inputs:
              data: "{{step1}}"

      - step_id: "3"
        agent: summarizer
        inputs:
          result_a: "{{step2a}}"
          result_b: "{{step2b}}"
"""

from gptase.sop.dispatcher import TaskDispatcher
from gptase.sop.exceptions import AgentDispatchError
from gptase.sop.exceptions import SOPError
from gptase.sop.exceptions import SOPExecutionError
from gptase.sop.exceptions import SOPNotFoundError
from gptase.sop.exceptions import SOPValidationError
from gptase.sop.failure_handler import FailureHandler
from gptase.sop.loader import SOPLoader
from gptase.sop.loader import SOPRegistry
from gptase.sop.orchestrator_agent import SOPOrchestratorAgent
from gptase.sop.types import ExecutionContext
from gptase.sop.types import FailureContext
from gptase.sop.types import FailureDecision
from gptase.sop.types import ParallelStep
from gptase.sop.types import SOPDefinition
from gptase.sop.types import SOPStep
from gptase.sop.types import StepResult
from gptase.sop.types import StepStatus
from gptase.sop.types import TaskResult
from gptase.sop.types import WorkflowItem

__all__ = [
    # Core types
    "SOPDefinition",
    "SOPStep",
    "ParallelStep",
    "WorkflowItem",
    "TaskResult",
    "StepResult",
    "ExecutionContext",
    "FailureContext",
    "FailureDecision",
    "StepStatus",
    # Exceptions
    "SOPError",
    "SOPNotFoundError",
    "SOPValidationError",
    "SOPExecutionError",
    "AgentDispatchError",
    # Loader and Registry
    "SOPLoader",
    "SOPRegistry",
    # Components
    "TaskDispatcher",
    "FailureHandler",
    "SOPOrchestratorAgent",
]
