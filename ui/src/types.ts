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

export type EntryMode = 'chat' | 'agent';

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
    label?: string;
    tone?: 'slate' | 'blue' | 'green' | 'amber' | 'red' | 'purple';
  };
}

export interface ExecutionTrace {
  id: string;
  stepId: string;
  timestamp: Date;
  type: 'log' | 'error' | 'warning' | 'success';
  kind: 'llm_call' | 'tool_call' | 'sdk_run' | 'system';
  statusTone: 'log' | 'success' | 'warning' | 'error';
  title: string;
  summary: string;
  summaryEmpty: boolean;
  emptyReason?: string;
  message: string;
  meta: {
    durationMs?: number;
    iteration?: number;
    toolName?: string;
    commandPreview?: string;
    inputTokens?: number;
    outputTokens?: number;
    messageCount?: number;
    resultChars?: number;
  };
  rawDetails?: Record<string, unknown>;
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
  entryMode: EntryMode;
  selectedAgent: string;
  messages: Message[];
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
  session_type: EntryMode;
  goal: string;
  status: string;
  selected_agent_id?: string;
  updated_at?: string;
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
  message_count?: number;
  result_chars?: number;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
  };
  arguments?: Record<string, unknown>;
}

export interface ApiTraceData {
  steps?: ApiTraceStep[];
  total_duration_ms?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
}

export interface ApiSessionDetail {
  session_id: string;
  session_type: EntryMode;
  status: string;
  goal: string;
  selected_agent_id?: string;
  messages?: Array<{
    id: string;
    role: MessageRole;
    content: string;
    timestamp: string;
    metadata?: Message['metadata'];
  }>;
  traces?: Array<{
    id: string;
    step_id: string;
    timestamp: string;
    type: ExecutionTrace['type'];
    message: string;
    details?: Record<string, unknown>;
  }>;
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
  created_at?: string;
  updated_at?: string;
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
