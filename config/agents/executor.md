<!--
@agent_id: executor
@capabilities: plan_execution, agent_orchestration, result_aggregation, workflow_coordination
@requires_model: false
@tools: executor
-->

# Executor Agent

## Agent Description
This agent is responsible for executing finalized plans. It coordinates multiple specialized agents to complete a complex workflow.

## Task Processing
The agent takes a `plan_id` and uses the `executor` tool to run all steps defined in that plan.

## Output Format
Returns the aggregate results of all executed workflow steps.
