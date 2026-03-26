export type AgentType =
  | 'general'
  | 'research'
  | 'biochem'
  | 'data-analysis'
  | 'code-expert';

export type SessionStatus =
  | 'draft'
  | 'planning'
  | 'reviewing'
  | 'executing'
  | 'completed'
  | 'failed';

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

export type MessageRole = 'user' | 'system' | 'agent' | 'tool';

export interface Agent {
  id: string;
  name: string;
  type: AgentType;
  description: string;
  capabilities: string[];
  status: 'idle' | 'active' | 'busy';
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  metadata?: {
    agentId?: string;
    toolName?: string;
    executionTime?: number;
    taskId?: string;
    planId?: string;
    label?: string;
    tone?: 'slate' | 'blue' | 'green' | 'amber' | 'red' | 'purple';
  };
}

export interface PlanStep {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  assignedAgent?: string;
  startTime?: Date;
  endTime?: Date;
  output?: string;
  error?: string;
}

export interface Plan {
  id: string;
  goal: string;
  steps: PlanStep[];
  status: 'draft' | 'approved' | 'executing' | 'completed' | 'failed';
  createdAt: Date;
  updatedAt: Date;
  currentStepIndex: number;
}

export interface ExecutionTrace {
  id: string;
  stepId: string;
  timestamp: Date;
  type: 'log' | 'error' | 'warning' | 'success';
  message: string;
  details?: Record<string, unknown>;
}

export interface WorkingMemory {
  key: string;
  value: string;
  timestamp: Date;
  source: string;
}

export interface Session {
  id: string;
  title: string;
  status: SessionStatus;
  selectedAgent: string;
  messages: Message[];
  plan?: Plan;
  planHistory: Plan[];
  traces: ExecutionTrace[];
  memory: WorkingMemory[];
  createdAt: Date;
  updatedAt: Date;
}

export interface EvalMetric {
  name: string;
  value: number;
  unit: string;
  status: 'good' | 'warning' | 'error';
}

export interface ApiAgent {
  id: string;
  name: string;
  description?: string;
}

export interface ApiSessionSummary {
  session_id: string;
  goal: string;
  status: string;
  current_plan_id?: string;
}

export interface ApiTaskPlan {
  task_id: string;
  description: string;
  agent_id?: string;
  dependencies?: string[];
  status?: string;
  expected_output?: string | null;
  error?: string | null;
}

export interface ApiPlanSummary {
  plan_id: string;
  goal?: string;
  summary?: string;
  tasks?: ApiTaskPlan[];
  status?: string;
  created_at?: string;
  updated_at?: string | null;
}

export interface ApiGoalEvaluation {
  goal_achieved: boolean;
  reason: string;
  missing_gaps: string[];
  next_action: string;
}

export interface ApiTraceStep {
  type?: 'llm_call' | 'tool_call' | 'sdk_run';
  iteration?: number;
  tool_name?: string;
  content_preview?: string;
  result_preview?: string;
  duration_ms?: number;
  note?: string;
}

export interface ApiTraceData {
  steps?: ApiTraceStep[];
  total_duration_ms?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
}

export interface ApiSessionDetail {
  session_id: string;
  status: string;
  goal: string;
  draft_source?: string;
  current_plan?: ApiPlanSummary | null;
  plan_history?: ApiPlanSummary[];
  progress?: Record<string, number> | null;
  goal_evaluation?: ApiGoalEvaluation;
  task_results?: Record<string, unknown>;
  task_traces?: Record<string, ApiTraceData>;
  current_task?: string | null;
  current_agent?: string | null;
  latest_error?: { task_id: string; error: string } | null;
  runtime_progress?: {
    completed_steps: number;
    total_steps: number;
    progress_percent: number;
  } | null;
}

export interface ApiWorkingMemoryPayload {
  agent_id: string;
  working_memory: {
    summary: string;
    metadata?: Record<string, unknown>;
    last_updated: string;
  } | null;
}

export interface ApiEvalAgent {
  agent_name: string;
  trace_count: number;
  latest_timestamp: string;
  latest_model: string;
  latest_status: string;
}

export interface ApiWorkspacePlan {
  plan_id: string;
  name?: string;
  description?: string;
}

export interface ApiWorkspaceArtifact {
  task_id: string;
  agent_name: string;
  artifact_type: 'json' | 'csv' | 'markdown' | 'pdf' | 'image' | 'directory' | 'other';
  label: string;
  path: string;
  name: string;
  size_bytes: number;
}

export interface ApiWorkspaceTaskSummary {
  task_id: string;
  agent_name: string;
  files: ApiWorkspaceArtifact[];
  primary_json?: string | null;
  parsed_json?: string | null;
  csv_files: string[];
  summary?: Record<string, unknown> | null;
  extraction_items: Array<{
    item_id: string;
    item_type: 'reaction' | 'vision_table' | 'vision_analysis';
    title: string;
    payload: Record<string, unknown>;
    anchors: Array<{
      line_number: number;
      snippet: string;
      excerpt: string;
      matched_terms: string[];
    }>;
  }>;
}

export interface ApiWorkspaceRunSummary {
  run_id: string;
  run_path: string;
  created_at: string;
  tasks: ApiWorkspaceTaskSummary[];
}

export interface ApiWorkspaceDocument {
  plan_id: string;
  workspace_root: string;
  document_name: string;
  document_dir: string;
  pdf_path?: string | null;
  markdown_path?: string | null;
  images_dir?: string | null;
  runs: ApiWorkspaceRunSummary[];
  selected_run_id?: string | null;
  selected_run_path?: string | null;
  available_plans: string[];
}

export interface ApiWorkspaceCsvFile {
  type: 'csv';
  columns: string[];
  rows: Record<string, string>[];
  raw: string;
}
