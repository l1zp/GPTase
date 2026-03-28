import { useEffect, useMemo, useRef, useState } from 'react';

import './App.css';
import { PlanWorkspaceExplorer } from './components/PlanWorkspaceExplorer';
import { DetailPanel } from './components/DetailPanel';
import { MainWorkspace } from './components/MainWorkspace';
import { SessionList } from './components/SessionList';
import { apiFetch, createAppWebSocket } from './lib/api';
import type {
  Agent,
  ApiAgent,
  ApiEvalAgent,
  ApiWorkspacePlan,
  ApiSessionDetail,
  ApiSessionSummary,
  ApiWorkingMemoryPayload,
  ApiTraceData,
  EntryMode,
  EvalMetric,
  ExecutionTrace,
  Message,
  Plan,
  Session,
  SessionStatus,
  WorkingMemory,
} from './types';

const ORCHESTRATOR_AGENT_ID = 'orchestrator';

export default function App() {
  if (
    window.location.pathname === '/workspace' ||
    window.location.pathname.startsWith('/workspace/')
  ) {
    return <PlanWorkspaceExplorer />;
  }
  return <ChatApp />;
}

function ChatApp() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState('');
  const [currentPlanId, setCurrentPlanId] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [availablePlans, setAvailablePlans] = useState<ApiWorkspacePlan[]>([]);
  const [evalMetrics, setEvalMetrics] = useState<EvalMetric[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeDetail, setActiveDetail] = useState<ApiSessionDetail | null>(null);
  const [evalAgentsSummary, setEvalAgentsSummary] = useState<ApiEvalAgent[]>([]);
  const memoryAgentRef = useRef<string | null>(null);
  const memoryCacheRef = useRef<Record<string, WorkingMemory[]>>({});

  const currentSession = sessions.find((session) => session.id === currentSessionId) ?? sessions[0];

  useEffect(() => {
    void initializeData();
  }, []);

  useEffect(() => {
    if (!currentSessionId) {
      return;
    }
    void loadSessionDetail(currentSessionId);
  }, [currentSessionId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshSessionSummaries();
    }, 10000);

    return () => window.clearInterval(timer);
  }, [currentSessionId]);

  useEffect(() => {
    if (!currentSessionId.startsWith('goal_')) {
      return;
    }

    const socket = createAppWebSocket(`/plan/${currentSessionId}`);

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { type?: string; data?: ApiSessionDetail | string };
        if (payload.type === 'update' && payload.data && typeof payload.data === 'object') {
          void applySessionDetail(payload.data);
        }
      } catch {
        // Ignore malformed websocket payloads.
      }
    };

    return () => {
      socket.close();
    };
  }, [currentSessionId]);

  const selectedAgentId = useMemo(() => {
    if (!activeDetail) {
      return currentSession?.selectedAgent ?? '';
    }
    return getPrimaryAgentId(activeDetail) ?? currentSession?.selectedAgent ?? '';
  }, [activeDetail, currentSession]);

  const initializeData = async () => {
    setLoading(true);
    try {
      const [agentRes, sessionRes, evalRes, planRes] = await Promise.all([
        apiFetch('/agents'),
        apiFetch('/sessions'),
        apiFetch('/evals'),
        apiFetch('/plans'),
      ]);

      if (agentRes.ok) {
        const rawAgents = (await agentRes.json()) as ApiAgent[];
        if (rawAgents.length > 0) {
          setAgents(rawAgents.map(mapAgent));
        }
      }

      if (sessionRes.ok) {
        const rawSessions = (await sessionRes.json()) as ApiSessionSummary[];
        if (rawSessions.length > 0) {
          const mapped = rawSessions.slice(0, 20).map(mapSessionSummary);
          setSessions((prev) => mergeSessions(prev, mapped));
          setCurrentSessionId((prev) => prev || mapped[0]?.id || '');
        }
      }

      if (evalRes.ok) {
        const rawEvals = (await evalRes.json()) as ApiEvalAgent[];
        setEvalAgentsSummary(rawEvals);
        setEvalMetrics(mapEvalMetrics(rawEvals));
      }

      if (planRes.ok) {
        const rawPlans = (await planRes.json()) as ApiWorkspacePlan[];
        setAvailablePlans(rawPlans);
      }
    } finally {
      setLoading(false);
    }
  };

  const refreshSessionSummaries = async () => {
    try {
      const sessionRes = await apiFetch('/sessions');
      if (!sessionRes.ok) {
        return;
      }
      const rawSessions = (await sessionRes.json()) as ApiSessionSummary[];
      if (rawSessions.length === 0) {
        return;
      }
      const mapped = rawSessions.slice(0, 20).map(mapSessionSummary);
      setSessions((prev) => mergeSessions(prev, mapped));
      if (
        currentSessionId.startsWith('goal_') &&
        !mapped.some((session) => session.id === currentSessionId) &&
        mapped[0]?.id
      ) {
        setCurrentSessionId(mapped[0].id);
      }
    } catch {
      // Ignore background refresh failures.
    }
  };

  const loadSessionDetail = async (sessionId: string) => {
    try {
      const detailRes = await apiFetch(`/sessions/${sessionId}`);
      if (!detailRes.ok) {
        return;
      }
      const detail = (await detailRes.json()) as ApiSessionDetail;
      await applySessionDetail(detail);
    } catch {
      // Keep mock/fallback session state if the detail fetch fails.
    }
  };

  const applySessionDetail = async (
    detail: ApiSessionDetail,
    options?: {
      entryMode?: EntryMode;
      selectedPlanTemplateId?: string;
    },
  ) => {
    setActiveDetail(detail);

    const primaryAgentId = getPrimaryAgentId(detail);
    let memory: WorkingMemory[] | null = null;

    if (
      primaryAgentId &&
      primaryAgentId !== ORCHESTRATOR_AGENT_ID &&
      primaryAgentId !== memoryAgentRef.current
    ) {
      const memoryRes = await apiFetch(`/memory/${primaryAgentId}`);
      if (memoryRes.ok) {
        const memoryPayload = (await memoryRes.json()) as ApiWorkingMemoryPayload;
        memory = mapWorkingMemory(memoryPayload);
        memoryCacheRef.current[primaryAgentId] = memory;
      }
    } else if (primaryAgentId && primaryAgentId !== ORCHESTRATOR_AGENT_ID) {
      memory = memoryCacheRef.current[primaryAgentId] ?? null;
    }
    memoryAgentRef.current =
      primaryAgentId && primaryAgentId !== ORCHESTRATOR_AGENT_ID ? primaryAgentId : null;

    setSessions((prev) => {
      const existing = prev.find((session) => session.id === detail.session_id);
      const nextSession = mapSessionDetail(detail, memory ?? existing?.memory ?? [], agents, {
        entryMode: options?.entryMode ?? existing?.entryMode,
        selectedAgent: existing?.selectedAgent,
        selectedPlanTemplateId:
          options?.selectedPlanTemplateId ?? existing?.selectedPlanTemplateId,
      });
      return existing
        ? prev.map((session) => (session.id === detail.session_id ? nextSession : session))
        : [nextSession, ...prev];
    });
    setEvalMetrics(buildSessionEvalMetrics(detail, evalAgentsSummary));
  };

  const handleCreateSession = () => {
    const defaultAgentId =
      agents.find((agent) => agent.id === ORCHESTRATOR_AGENT_ID)?.id ??
      agents[0]?.id ??
      'agent-general';
    const newSession: Session = {
      id: `session-${Date.now()}`,
      title: '新会话',
      status: 'draft',
      selectedAgent: defaultAgentId,
      entryMode: 'chat',
      selectedPlanTemplateId: availablePlans[0]?.plan_id,
      messages: [],
      planHistory: [],
      traces: [],
      memory: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    setSessions((prev) => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
  };

  const handleSelectSession = (id: string) => {
    setCurrentSessionId(id);
    setCurrentPlanId(null);
    if (!id.startsWith('goal_')) {
      setActiveDetail(null);
      setEvalMetrics(mapEvalMetrics(evalAgentsSummary));
    }
  };

  const handleSelectPlan = (sessionId: string, planId: string) => {
    setCurrentSessionId(sessionId);
    setCurrentPlanId(planId);
  };

  const handleSelectAgent = (agentId: string) => {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === currentSessionId
          ? {
              ...session,
              selectedAgent: agentId,
              updatedAt: new Date(),
            }
          : session,
      ),
    );
  };

  const handleSelectEntryMode = (mode: EntryMode) => {
    setSessions((prev) =>
      prev.map((session) => {
        if (session.id !== currentSessionId) {
          return session;
        }
        let nextSelectedAgent = session.selectedAgent;
        if (mode === 'chat') {
          nextSelectedAgent = ORCHESTRATOR_AGENT_ID;
        }
        if (mode === 'agent' && nextSelectedAgent === ORCHESTRATOR_AGENT_ID) {
          nextSelectedAgent =
            agents.find((agent) => agent.id !== ORCHESTRATOR_AGENT_ID)?.id ?? nextSelectedAgent;
        }
        return {
          ...session,
          entryMode: mode,
          selectedAgent: nextSelectedAgent,
          selectedPlanTemplateId:
            mode === 'plan'
              ? session.selectedPlanTemplateId ?? availablePlans[0]?.plan_id
              : session.selectedPlanTemplateId,
          updatedAt: new Date(),
        };
      }),
    );
  };

  const handleSelectPlanTemplate = (planId: string) => {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === currentSessionId
          ? {
              ...session,
              selectedPlanTemplateId: planId,
              updatedAt: new Date(),
            }
          : session,
      ),
    );
  };

  const handleSendMessage = (content: string) => {
    const entryMode = currentSession?.entryMode ?? 'chat';
    if (entryMode === 'plan') {
      void submitPlanRun(content);
      return;
    }
    if (entryMode === 'chat' || currentSessionId.startsWith('goal_')) {
      void submitGoal(content);
      return;
    }
    void sendDirectAgentMessage(content);
  };

  const sendDirectAgentMessage = async (content: string, agentOverride?: string) => {
    const selectedAgent = agentOverride ?? currentSession?.selectedAgent ?? ORCHESTRATOR_AGENT_ID;
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
      metadata: {
        label: selectedAgent === ORCHESTRATOR_AGENT_ID ? '任务提交' : 'Worker 任务',
        tone: selectedAgent === ORCHESTRATOR_AGENT_ID ? 'blue' : 'purple',
      },
    };

    setSessions((prev) =>
      prev.map((session) =>
        session.id === currentSessionId
          ? {
              ...session,
              selectedAgent,
              title:
                session.messages.length === 0
                  ? summarizeGoal(content)
                  : session.title,
              messages: [...session.messages, userMessage],
              status: 'planning',
              updatedAt: new Date(),
            }
          : session,
      ),
    );

    setLoading(true);
    try {
      const response = await apiFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgent,
          message: content,
          auto_execute: false,
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const result = (await response.json()) as {
        status?: string;
        error?: string;
        data?: { content?: string };
        trace?: ApiTraceData;
      };

      const agentMessage: Message = {
        id: `msg-${Date.now() + 1}`,
        role: result.status === 'error' ? 'system' : 'agent',
        content:
          result.status === 'error'
            ? result.error ?? 'Agent 调用失败。'
            : result.data?.content ?? 'Agent 已完成，但没有返回文本内容。',
        timestamp: new Date(),
        metadata: {
          agentId: selectedAgent,
          label: result.status === 'error' ? 'Worker Error' : 'Worker Result',
          tone: result.status === 'error' ? 'red' : 'green',
        },
      };

      const traces = (result.trace?.steps ?? []).map((step, index) => ({
        id: `${currentSessionId}-direct-${index}-${Date.now()}`,
        stepId: selectedAgent,
        timestamp: new Date(),
        type:
          step.type === 'sdk_run'
            ? 'success'
            : step.type === 'tool_call'
              ? 'log'
              : 'log',
        message:
          step.result_preview ??
          step.content_preview ??
          step.note ??
          step.tool_name ??
          `Trace ${index + 1}`,
        details: {
          type: step.type,
          duration_ms: step.duration_ms,
          iteration: step.iteration,
        },
      })) satisfies ExecutionTrace[];

      setSessions((prev) =>
        prev.map((session) =>
          session.id === currentSessionId
            ? {
                ...session,
                status: result.status === 'error' ? 'failed' : 'completed',
                messages: [...session.messages, agentMessage],
                traces: [...session.traces, ...traces],
                updatedAt: new Date(),
              }
            : session,
        ),
      );
    } catch (error) {
      setSessions((prev) =>
        prev.map((session) =>
          session.id === currentSessionId
            ? {
                ...session,
                status: 'failed',
                messages: [
                  ...session.messages,
                  {
                    id: `msg-${Date.now() + 2}`,
                    role: 'system',
                    content: `Agent 调用失败：${error instanceof Error ? error.message : 'unknown error'}`,
                    timestamp: new Date(),
                    metadata: {
                      agentId: selectedAgent,
                      label: 'Worker Error',
                      tone: 'red',
                    },
                  },
                ],
                updatedAt: new Date(),
              }
            : session,
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  const submitGoal = async (content: string) => {
    setLoading(true);
    try {
      const response = await apiFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: ORCHESTRATOR_AGENT_ID,
          message: content,
          auto_execute: false,
        }),
      });
      if (!response.ok) {
        return;
      }
      const payload = (await response.json()) as ApiSessionDetail | {
        status?: string;
        error?: string;
        data?: { content?: string };
        agent_id?: string;
        trace?: ApiTraceData;
      };
      if ('session_id' in payload) {
        await applySessionDetail(payload);
        setCurrentSessionId(payload.session_id);
        return;
      }

      const directAgentId = payload.agent_id ?? 'orchestrator';
      const directReply: Message = {
        id: `msg-${Date.now() + 1}`,
        role: payload.status === 'error' ? 'system' : 'agent',
        content:
          payload.status === 'error'
            ? payload.error ?? 'Agent 调用失败。'
            : payload.data?.content ?? 'Agent 已完成，但没有返回文本内容。',
        timestamp: new Date(),
        metadata: {
          agentId: directAgentId,
          label: payload.status === 'error' ? '运行时错误' : '运行时结果',
          tone: payload.status === 'error' ? 'red' : 'green',
        },
      };

      const directTraces = (payload.trace?.steps ?? []).map((step, index) => ({
        id: `${currentSessionId}-orchestrator-direct-${index}-${Date.now()}`,
        stepId: directAgentId,
        timestamp: new Date(),
        type:
          step.type === 'sdk_run'
            ? 'success'
            : step.type === 'tool_call'
              ? 'log'
              : 'log',
        message:
          step.result_preview ??
          step.content_preview ??
          step.note ??
          step.tool_name ??
          `Trace ${index + 1}`,
        details: {
          type: step.type,
          duration_ms: step.duration_ms,
          iteration: step.iteration,
        },
      })) satisfies ExecutionTrace[];

      setSessions((prev) =>
        prev.map((session) =>
          session.id === currentSessionId
            ? {
                ...session,
                selectedAgent: directAgentId,
                title: session.messages.length === 0 ? summarizeGoal(content) : session.title,
                status: payload.status === 'error' ? 'failed' : 'completed',
                messages: [
                  ...session.messages,
                  {
                    id: `msg-${Date.now()}`,
                    role: 'user',
                    content,
                    timestamp: new Date(),
                    metadata: {
                      label: '任务提交',
                      tone: 'purple',
                    },
                  },
                  directReply,
                ],
                traces: [...session.traces, ...directTraces],
                updatedAt: new Date(),
              }
            : session,
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  const submitPlanRun = async (content: string) => {
    const selectedPlanTemplateId =
      currentSession?.selectedPlanTemplateId ?? availablePlans[0]?.plan_id ?? '';
    if (!selectedPlanTemplateId) {
      return;
    }

    setLoading(true);
    try {
      const response = await apiFetch('/plan/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan_id: selectedPlanTemplateId,
          input_data: {
            text: content,
          },
          auto_execute: false,
          auto_replan: false,
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = (await response.json()) as ApiSessionDetail;
      await applySessionDetail(payload, {
        entryMode: 'plan',
        selectedPlanTemplateId,
      });
      setCurrentSessionId(payload.session_id);
    } finally {
      setLoading(false);
    }
  };

  const handleApprovePlan = () => {
    if (currentSessionId.startsWith('goal_')) {
      void approveRealPlan();
      return;
    }
    setSessions((prev) =>
      prev.map((session) => {
        if (session.id !== currentSessionId || !session.plan) {
          return session;
        }
        const agentMessage: Message = {
          id: `msg-${Date.now()}`,
          role: 'agent',
          content: '计划已批准，开始执行。系统将持续更新追踪、记忆和评估指标。',
          timestamp: new Date(),
          metadata: { agentId: session.selectedAgent },
        };
        return {
          ...session,
          messages: [...session.messages, agentMessage],
          plan: {
            ...session.plan,
            status: 'executing',
            updatedAt: new Date(),
          },
          status: 'executing',
          updatedAt: new Date(),
        };
      }),
    );

    window.setTimeout(() => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== currentSessionId || !session.plan) {
            return session;
          }
          const updatedSteps = session.plan.steps.map((step, index) =>
            index === 0
              ? {
                  ...step,
                  status: 'running' as const,
                  startTime: new Date(),
                }
              : step,
          );
          return {
            ...session,
            plan: {
              ...session.plan,
              steps: updatedSteps,
              currentStepIndex: 0,
              updatedAt: new Date(),
            },
          };
        }),
      );
    }, 1000);
  };

  const approveRealPlan = async () => {
    setLoading(true);
    try {
      const response = await apiFetch(`/sessions/${currentSessionId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        return;
      }
      const detail = (await response.json()) as ApiSessionDetail;
      await applySessionDetail(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleRejectPlan = () => {
    if (currentSessionId.startsWith('goal_')) {
      void reviseRealPlan('计划已拒绝，请重新生成。');
      return;
    }
    setSessions((prev) =>
      prev.map((session) => {
        if (session.id !== currentSessionId) {
          return session;
        }
        const systemMessage: Message = {
          id: `msg-${Date.now()}`,
          role: 'system',
          content: '计划已拒绝。请重新描述目标或补充约束条件。',
          timestamp: new Date(),
        };
        return {
          ...session,
          messages: [...session.messages, systemMessage],
          plan: undefined,
          status: 'draft',
          updatedAt: new Date(),
        };
      }),
    );
  };

  const handleRevisePlan = () => {
    if (currentSessionId.startsWith('goal_')) {
      void reviseRealPlan('请修改当前 draft plan。');
      return;
    }
    const systemMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'system',
      content: '请说明你希望调整的步骤、输入数据或输出格式。',
      timestamp: new Date(),
    };

    setSessions((prev) =>
      prev.map((session) =>
        session.id === currentSessionId
          ? {
              ...session,
              messages: [...session.messages, systemMessage],
              updatedAt: new Date(),
            }
          : session,
      ),
    );
  };

  const reviseRealPlan = async (feedback: string) => {
    setLoading(true);
    try {
      const response = await apiFetch(`/sessions/${currentSessionId}/input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      });
      if (!response.ok) {
        return;
      }
      const detail = (await response.json()) as ApiSessionDetail;
      await applySessionDetail(detail);
    } finally {
      setLoading(false);
    }
  };

  if (!currentSession) {
    return null;
  }

  return (
    <div className="app-shell">
      <SessionList
        sessions={sessions}
        currentSessionId={currentSessionId}
        currentPlanId={currentPlanId}
        agents={agents}
        onSelectSession={handleSelectSession}
        onSelectPlan={handleSelectPlan}
        onCreateSession={handleCreateSession}
      />
      <MainWorkspace
        session={currentSession}
        selectedPlanId={currentPlanId}
        agents={agents}
        availablePlans={availablePlans}
        onSendMessage={handleSendMessage}
        onSelectEntryMode={handleSelectEntryMode}
        onSelectAgent={handleSelectAgent}
        onSelectPlanTemplate={handleSelectPlanTemplate}
        onApprovePlan={handleApprovePlan}
        onRejectPlan={handleRejectPlan}
        onRevisePlan={handleRevisePlan}
        loading={loading}
      />
      <DetailPanel session={currentSession} evalMetrics={evalMetrics} />
    </div>
  );
}

const summarizeGoal = (goal: string) => {
  const clean = goal.replace(/\s+/g, ' ').trim();
  if (!clean) {
    return '未命名会话';
  }
  return clean.length > 30 ? `${clean.slice(0, 30)}...` : clean;
};

const mapStatus = (status: string): SessionStatus => {
  if (status === 'awaiting_approval') return 'reviewing';
  if (status === 'awaiting_user_input') return 'reviewing';
  if (status === 'in_progress') return 'executing';
  if (status === 'running') return 'executing';
  if (status === 'completed' || status === 'success') return 'completed';
  if (status === 'failed' || status === 'error' || status === 'blocked') return 'failed';
  if (status === 'planning') return 'planning';
  return 'draft';
};

const inferAgentType = (agent: ApiAgent): Agent['type'] => {
  if (agent.id === ORCHESTRATOR_AGENT_ID) return 'general';
  const text = `${agent.id} ${agent.name} ${agent.description ?? ''}`.toLowerCase();
  if (text.includes('biochem') || text.includes('enzyme') || text.includes('kinetics')) return 'biochem';
  if (text.includes('research') || text.includes('literature')) return 'research';
  if (text.includes('code') || text.includes('planner') || text.includes('orchestrator')) return 'code-expert';
  if (text.includes('data')) return 'data-analysis';
  return 'general';
};

const mapAgent = (agent: ApiAgent): Agent => ({
  id: agent.id,
  name: agent.name,
  type: inferAgentType(agent),
  description:
    agent.id === ORCHESTRATOR_AGENT_ID
      ? 'Harness 运行时入口，负责创建 session、draft plan 并调度 worker'
      : agent.description ?? 'GPTase worker agent',
  capabilities:
    agent.id === ORCHESTRATOR_AGENT_ID
      ? ['提交任务', '管理 session', '调度 worker']
      : (agent.description ?? '')
          .split(/[,.，、]/)
          .map((item) => item.trim())
          .filter(Boolean)
          .slice(0, 3),
  status: agent.id === ORCHESTRATOR_AGENT_ID ? 'active' : 'idle',
});

const mapSessionSummary = (summary: ApiSessionSummary): Session => ({
  id: summary.session_id,
  title: summarizeGoal(summary.goal),
  status: mapStatus(summary.status),
  entryMode: 'chat',
  selectedAgent: ORCHESTRATOR_AGENT_ID,
  selectedPlanTemplateId: undefined,
  messages: [
    {
      id: `${summary.session_id}-goal`,
      role: 'user',
      content: summary.goal,
      timestamp: new Date(),
    },
  ],
  planHistory: [],
  traces: [],
  memory: [],
  createdAt: new Date(),
  updatedAt: new Date(),
});

const mergeSessions = (existing: Session[], incoming: Session[]) => {
  const localDrafts = existing.filter((session) => !session.id.startsWith('goal_'));
  const detailMap = new Map(existing.map((session) => [session.id, session]));
  const mergedRemote = incoming.map((session) => detailMap.get(session.id) ?? session);
  return [...localDrafts, ...mergedRemote];
};

const toPlan = (plan: NonNullable<ApiSessionDetail['current_plan']>, detail: ApiSessionDetail): Plan => {
  return {
    id: plan.plan_id,
    goal: plan.goal ?? detail.goal,
    steps: (plan.tasks ?? []).map((task) => ({
      id: task.task_id,
      title: task.description,
      description: task.expected_output ?? task.agent_id ?? 'GPTase task',
      status:
        task.status === 'completed'
          ? 'completed'
          : task.status === 'failed'
            ? 'failed'
            : task.status === 'running' || task.status === 'in_progress'
              ? 'running'
              : 'pending',
      assignedAgent: task.agent_id,
      error: task.error ?? undefined,
    })),
    status:
      detail.status === 'completed'
        ? 'completed'
        : detail.status === 'failed'
          ? 'failed'
          : detail.status === 'in_progress'
            ? 'executing'
            : 'draft',
    createdAt: plan.created_at ? new Date(plan.created_at) : new Date(),
    updatedAt: plan.updated_at ? new Date(plan.updated_at) : new Date(),
    currentStepIndex:
      detail.runtime_progress?.completed_steps ??
      detail.progress?.completed ??
      0,
  };
};

const mapPlan = (detail: ApiSessionDetail): Plan | undefined =>
  detail.current_plan ? toPlan(detail.current_plan, detail) : undefined;

const mapPlanHistory = (detail: ApiSessionDetail): Plan[] => {
  const orderedPlans = [...(detail.plan_history ?? [])];
  if (detail.current_plan && !orderedPlans.some((plan) => plan.plan_id === detail.current_plan?.plan_id)) {
    orderedPlans.push(detail.current_plan);
  }
  const seen = new Set<string>();
  return orderedPlans
    .filter((plan) => {
      if (seen.has(plan.plan_id)) {
        return false;
      }
      seen.add(plan.plan_id);
      return true;
    })
    .map((plan) => toPlan(plan, detail));
};

const mapMessages = (detail: ApiSessionDetail): Message[] => {
  const messages: Message[] = [
    {
      id: `${detail.session_id}-goal`,
      role: 'user',
      content: detail.goal,
      timestamp: new Date(),
      metadata: {
        planId: detail.current_plan?.plan_id,
        label: '任务目标',
        tone: 'blue',
      },
    },
  ];

  (detail.plan_history ?? []).forEach((plan, index) => {
    messages.push({
      id: `${detail.session_id}-plan-history-${plan.plan_id}`,
      role: 'system',
      content: `${index === (detail.plan_history?.length ?? 1) - 1 ? '当前' : '历史'}计划 ${plan.plan_id}，包含 ${
        plan.tasks?.length ?? 0
      } 个任务。`,
      timestamp: new Date(plan.created_at ?? Date.now()),
      metadata: {
        planId: plan.plan_id,
        label: index === (detail.plan_history?.length ?? 1) - 1 ? '当前 Draft' : '历史 Draft',
        tone: index === (detail.plan_history?.length ?? 1) - 1 ? 'purple' : 'slate',
      },
    });
    (plan.tasks ?? []).forEach((task) => {
      messages.push({
        id: `${detail.session_id}-${plan.plan_id}-${task.task_id}`,
        role: 'system',
        content: `${task.description}${task.agent_id ? ` · agent: ${task.agent_id}` : ''}${
          task.expected_output ? ` · output: ${task.expected_output}` : ''
        }`,
        timestamp: new Date(plan.created_at ?? Date.now()),
        metadata: {
          taskId: task.task_id,
          planId: plan.plan_id,
          label: task.status ? `任务 ${task.status}` : '任务',
          tone:
            task.status === 'completed'
              ? 'green'
              : task.status === 'failed'
                ? 'red'
                : task.status === 'running' || task.status === 'in_progress'
                  ? 'blue'
                  : 'slate',
        },
      });
    });
  });

  if (detail.progress || detail.runtime_progress) {
    const completed =
      detail.runtime_progress?.completed_steps ?? detail.progress?.completed ?? 0;
    const total = detail.runtime_progress?.total_steps ?? detail.progress?.total ?? 0;
    messages.push({
      id: `${detail.session_id}-progress`,
      role: 'system',
      content: `执行进度 ${completed}/${total}，状态 ${detail.status}。`,
      timestamp: new Date(),
      metadata: {
        planId: detail.current_plan?.plan_id,
        label: '运行进度',
        tone: detail.status === 'completed' ? 'green' : 'amber',
      },
    });
  }

  if (detail.goal_evaluation?.reason) {
    messages.push({
      id: `${detail.session_id}-eval`,
      role: detail.goal_evaluation.goal_achieved ? 'agent' : 'system',
      content: detail.goal_evaluation.reason,
      timestamp: new Date(),
      metadata: {
        planId: detail.current_plan?.plan_id,
        label: detail.goal_evaluation.goal_achieved ? '目标达成' : '目标评估',
        tone: detail.goal_evaluation.goal_achieved ? 'green' : 'amber',
      },
    });
  }

  Object.entries(detail.task_traces ?? {}).forEach(([taskId, trace]) => {
    (trace.steps ?? []).forEach((step, index) => {
      messages.push({
        id: `${detail.session_id}-trace-${taskId}-${index}`,
        role: 'tool',
        content:
          step.result_preview ??
          step.content_preview ??
          step.note ??
          step.tool_name ??
          `Trace ${index + 1}`,
        timestamp: new Date(),
        metadata: {
          taskId,
          planId: detail.current_plan?.plan_id,
          label: step.type === 'tool_call' ? '工具调用' : step.type === 'sdk_run' ? 'SDK 运行' : 'LLM 步骤',
          tone: step.type === 'tool_call' ? 'amber' : step.type === 'sdk_run' ? 'green' : 'slate',
          toolName: step.tool_name,
          executionTime: step.duration_ms,
        },
      });
    });
  });

  Object.entries(detail.task_results ?? {}).forEach(([taskId, result]) => {
    const content =
      typeof result === 'string'
        ? result
        : typeof result === 'object' && result && 'content' in result
          ? String((result as Record<string, unknown>).content ?? '')
          : JSON.stringify(result, null, 2);
    messages.push({
      id: `${detail.session_id}-${taskId}`,
      role: 'agent',
      content: content || `任务 ${taskId} 已完成。`,
      timestamp: new Date(),
      metadata: {
        agentId: detail.current_agent ?? getPrimaryAgentId(detail) ?? undefined,
        taskId,
        planId: detail.current_plan?.plan_id,
        label: '任务结果',
        tone: 'green',
      },
    });
  });

  if (detail.latest_error) {
    messages.push({
      id: `${detail.session_id}-error`,
      role: 'system',
      content: `任务 ${detail.latest_error.task_id} 失败：${detail.latest_error.error}`,
      timestamp: new Date(),
      metadata: {
        taskId: detail.latest_error.task_id,
        planId: detail.current_plan?.plan_id,
        label: '最新错误',
        tone: 'red',
      },
    });
  }

  return messages;
};

const mapTraces = (detail: ApiSessionDetail): ExecutionTrace[] =>
  Object.entries(detail.task_traces ?? {}).flatMap(([taskId, trace]) =>
    (trace.steps ?? []).map((step, index) => ({
      id: `${taskId}-${index}`,
      stepId: taskId,
      timestamp: new Date(),
      type:
        step.type === 'tool_call'
          ? 'log'
          : step.type === 'sdk_run'
            ? 'success'
            : 'log',
      message:
        step.result_preview ??
        step.content_preview ??
        step.note ??
        step.tool_name ??
        `Trace step ${index + 1}`,
      details: {
        type: step.type,
        duration_ms: step.duration_ms,
        iteration: step.iteration,
      },
    })),
  );

const mapWorkingMemory = (payload: ApiWorkingMemoryPayload): WorkingMemory[] => {
  const workingMemory = payload.working_memory;
  if (!workingMemory) {
    return [];
  }
  return [
    {
      key: 'summary',
      value: workingMemory.summary,
      timestamp: new Date(workingMemory.last_updated),
      source: payload.agent_id,
    },
    ...Object.entries(workingMemory.metadata ?? {}).map(([key, value]) => ({
      key,
      value: typeof value === 'string' ? value : JSON.stringify(value),
      timestamp: new Date(workingMemory.last_updated),
      source: payload.agent_id,
    })),
  ];
};

const getPrimaryAgentId = (detail: ApiSessionDetail) =>
  detail.current_agent ?? detail.current_plan?.tasks?.[0]?.agent_id ?? ORCHESTRATOR_AGENT_ID;

const mapSessionDetail = (
  detail: ApiSessionDetail,
  memory: WorkingMemory[],
  agents: Agent[],
  options?: {
    entryMode?: EntryMode;
    selectedAgent?: string;
    selectedPlanTemplateId?: string;
  },
): Session => {
  const primaryAgent = getPrimaryAgentId(detail);
  const entryMode = options?.entryMode ?? 'chat';
  return {
    id: detail.session_id,
    title: summarizeGoal(detail.goal),
    status: mapStatus(detail.status),
    entryMode,
    selectedAgent:
      entryMode === 'agent' && agents.some((agent) => agent.id === primaryAgent)
        ? primaryAgent
        : options?.selectedAgent ?? ORCHESTRATOR_AGENT_ID,
    selectedPlanTemplateId:
      options?.selectedPlanTemplateId ?? detail.current_plan?.plan_id,
    messages: mapMessages(detail),
    plan: mapPlan(detail),
    planHistory: mapPlanHistory(detail),
    traces: mapTraces(detail),
    memory,
    createdAt: detail.current_plan?.created_at ? new Date(detail.current_plan.created_at) : new Date(),
    updatedAt: new Date(),
  };
};

const mapEvalMetrics = (agents: ApiEvalAgent[]): EvalMetric[] => {
  if (agents.length === 0) {
    return [];
  }
  const latest = agents[0];
  return [
    {
      name: '评估代理数',
      value: agents.length,
      unit: '个',
      status: 'good',
    },
    {
      name: '最新 Trace',
      value: latest.trace_count,
      unit: '条',
      status: latest.latest_status === 'success' ? 'good' : 'warning',
    },
    {
      name: '总 Trace 数',
      value: agents.reduce((sum, a) => sum + a.trace_count, 0),
      unit: '条',
      status: 'good',
    },
  ];
};

const buildSessionEvalMetrics = (
  detail: ApiSessionDetail,
  evalAgents: ApiEvalAgent[],
): EvalMetric[] => {
  const traceSteps = Object.values(detail.task_traces ?? {}).reduce(
    (count, trace) => count + (trace.steps?.length ?? 0),
    0,
  );
  const totalDurationMs = Object.values(detail.task_traces ?? {}).reduce(
    (sum, trace) => sum + (trace.total_duration_ms ?? 0),
    0,
  );
  const totalInputTokens = Object.values(detail.task_traces ?? {}).reduce(
    (sum, trace) => sum + (trace.total_input_tokens ?? 0),
    0,
  );
  const totalOutputTokens = Object.values(detail.task_traces ?? {}).reduce(
    (sum, trace) => sum + (trace.total_output_tokens ?? 0),
    0,
  );
  const resultCount = Object.keys(detail.task_results ?? {}).length;
  const taskCount = detail.current_plan?.tasks?.length ?? 0;
  const completedCount =
    detail.runtime_progress?.completed_steps ?? detail.progress?.completed ?? 0;

  const sessionMetrics: EvalMetric[] = [
    {
      name: '任务完成率',
      value: taskCount > 0 ? Math.round((completedCount / taskCount) * 100) : 0,
      unit: '%',
      status: detail.status === 'failed' ? 'error' : detail.status === 'completed' ? 'good' : 'warning',
    },
    {
      name: 'Trace Steps',
      value: traceSteps,
      unit: '步',
      status: traceSteps > 0 ? 'good' : 'warning',
    },
    {
      name: '结果产出',
      value: resultCount,
      unit: '项',
      status: resultCount > 0 ? 'good' : 'warning',
    },
    {
      name: '运行时长',
      value: Number((totalDurationMs / 1000).toFixed(1)),
      unit: 's',
      status: totalDurationMs > 0 ? 'good' : 'warning',
    },
  ];

  if (totalInputTokens > 0 || totalOutputTokens > 0) {
    sessionMetrics.push(
      {
        name: '输入 Tokens',
        value: totalInputTokens,
        unit: 'tok',
        status: 'good',
      },
      {
        name: '输出 Tokens',
        value: totalOutputTokens,
        unit: 'tok',
        status: 'good',
      },
    );
  }

  if (sessionMetrics.some((metric) => metric.value > 0)) {
    return sessionMetrics;
  }

  return mapEvalMetrics(evalAgents);
};
