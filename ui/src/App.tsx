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
const CHAT_AGENT_ID = 'chat';

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

  const currentSession =
    sessions.find((session) => session.id === currentSessionId) ??
    sessions[0] ?? {
      id: 'session-empty',
      title: '新会话',
      status: 'draft' as const,
      selectedAgent:
        agents.find((agent) => agent.id === CHAT_AGENT_ID)?.id ??
        agents[0]?.id ??
        CHAT_AGENT_ID,
      entryMode: 'chat' as const,
      selectedPlanTemplateId: availablePlans[0]?.plan_id,
      messages: [],
      planHistory: [],
      traces: [],
      memory: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };

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
    if (currentSession?.entryMode !== 'plan') {
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
  }, [currentSessionId, currentSession?.entryMode]);

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
      if (!mapped.some((session) => session.id === currentSessionId) && mapped[0]?.id) {
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
    const existingDraft = sessions.find((session) => isReusableDraftSession(session, 'chat'));
    if (existingDraft) {
      setCurrentSessionId(existingDraft.id);
      setCurrentPlanId(null);
      setActiveDetail(null);
      setEvalMetrics(mapEvalMetrics(evalAgentsSummary));
      return;
    }

    const newSession = createDraftSession('chat', agents, availablePlans);
    setSessions((prev) => normalizeDraftSessions([newSession, ...prev]));
    setCurrentSessionId(newSession.id);
  };

  const handleSelectSession = (id: string) => {
    setCurrentSessionId(id);
    setCurrentPlanId(null);
    const target = sessions.find((session) => session.id === id);
    if (target?.entryMode !== 'plan') {
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
    const targetSession = sessions.find((session) => session.id === currentSessionId);
    if (!targetSession) {
      return;
    }

    if (targetSession.entryMode === mode) {
      return;
    }

    const hasConversationContext =
      targetSession.messages.length > 0 ||
      targetSession.planHistory.length > 0 ||
      targetSession.id.startsWith('chat_') ||
      targetSession.id.startsWith('agent_') ||
      targetSession.id.startsWith('plan_');

    if (hasConversationContext && targetSession.entryMode !== mode) {
      const reusableDraft = sessions.find((session) => isReusableDraftSession(session, mode));
      if (reusableDraft) {
        setCurrentSessionId(reusableDraft.id);
      } else {
        const newSession = createDraftSession(mode, agents, availablePlans);
        setSessions((prev) => normalizeDraftSessions([newSession, ...prev]));
        setCurrentSessionId(newSession.id);
      }
      setCurrentPlanId(null);
      setActiveDetail(null);
      setEvalMetrics(mapEvalMetrics(evalAgentsSummary));
      return;
    }

    setSessions((prev) =>
      prev.map((session) => {
        if (session.id !== currentSessionId) {
          return session;
        }
        let nextSelectedAgent = session.selectedAgent;
        if (mode === 'chat') {
          nextSelectedAgent = CHAT_AGENT_ID;
        }
        if (mode === 'agent' &&
            (nextSelectedAgent === ORCHESTRATOR_AGENT_ID || nextSelectedAgent === CHAT_AGENT_ID)) {
          nextSelectedAgent =
            agents.find((agent) => agent.id !== ORCHESTRATOR_AGENT_ID && agent.id !== CHAT_AGENT_ID)
              ?.id ?? nextSelectedAgent;
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
    void sendDirectAgentMessage(content, entryMode);
  };

  const sendDirectAgentMessage = async (content: string, mode: EntryMode) => {
    const selectedAgent =
      mode === 'chat'
        ? CHAT_AGENT_ID
        : currentSession?.selectedAgent ?? CHAT_AGENT_ID;
    const existingSession = sessions.find((session) => session.id === currentSessionId);
    const workingSessionId = existingSession?.id ?? createDirectSessionId(mode);
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
      metadata: {
        label: mode === 'chat' ? '任务提交' : 'Worker 任务',
        tone: mode === 'chat' ? 'blue' : 'purple',
      },
    };
    const pendingAssistantId = `msg-${Date.now() + 1}`;
    const pendingAssistant: Message = {
      id: pendingAssistantId,
      role: 'agent',
      content: '正在回复...',
      timestamp: new Date(),
      metadata: {
        agentId: selectedAgent,
        label: '正在回复',
        tone: 'amber',
      },
    };

    setSessions((prev) =>
      prev.some((session) => session.id === workingSessionId)
        ? prev.map((session) =>
            session.id === workingSessionId
              ? {
                  ...session,
                  entryMode: mode,
                  selectedAgent,
                  title: session.messages.length === 0 ? summarizeGoal(content) : session.title,
                  status: 'planning',
                  messages:
                    mode === 'chat'
                      ? [...session.messages, userMessage, pendingAssistant]
                      : [...session.messages, userMessage],
                  updatedAt: new Date(),
                }
              : session,
          )
        : [{
            id: workingSessionId,
            title: summarizeGoal(content),
            status: 'planning',
            selectedAgent,
            entryMode: mode,
            selectedPlanTemplateId: availablePlans[0]?.plan_id,
            messages: mode === 'chat' ? [userMessage, pendingAssistant] : [userMessage],
            planHistory: [],
            traces: [],
            memory: [],
            createdAt: new Date(),
            updatedAt: new Date(),
          }, ...prev],
    );
    setCurrentSessionId(workingSessionId);

    if (mode === 'chat') {
      const socket = createAppWebSocket('/chat');
      let settled = false;
      const fallbackToHttp = () => {
        if (settled) {
          return;
        }
        settled = true;
        void completeDirectAgentMessageViaHttp(
          workingSessionId,
          selectedAgent,
          content,
          mode,
          pendingAssistantId,
        );
      };
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as {
            type?: 'session' | 'chunk' | 'done' | 'error';
            data?: ApiSessionDetail | { session_id?: string; delta?: string; error?: string };
          };
          if (payload.type === 'chunk' && payload.data && 'delta' in payload.data) {
            const chunkData = payload.data as { session_id?: string; delta?: string };
            setSessions((prev) =>
              prev.map((session) =>
                session.id === workingSessionId
                  ? {
                      ...session,
                      messages: session.messages.map((message) =>
                        message.id === pendingAssistantId
                          ? {
                              ...message,
                              content:
                                message.content === '正在回复...'
                                  ? String(chunkData.delta ?? '')
                                  : `${message.content}${String(chunkData.delta ?? '')}`,
                              metadata: {
                                ...message.metadata,
                                label: '正在回复',
                                tone: 'amber',
                              },
                            }
                          : message,
                      ),
                    }
                  : session,
              ),
            );
          } else if (payload.type === 'done' && payload.data && 'session_id' in payload.data) {
            settled = true;
            void applySessionDetail(payload.data as ApiSessionDetail, { entryMode: mode });
            setCurrentSessionId((payload.data as ApiSessionDetail).session_id);
            socket.close();
            setLoading(false);
          } else if (payload.type === 'error') {
            socket.close();
            fallbackToHttp();
          }
        } catch {
          socket.close();
          fallbackToHttp();
        }
      };
      socket.onerror = () => {
        socket.close();
        fallbackToHttp();
      };
      socket.onclose = () => {
        if (!settled) {
          fallbackToHttp();
        }
      };
      socket.onopen = () => {
        socket.send(
          JSON.stringify({
            agent_id: selectedAgent,
            message: content,
            session_id: workingSessionId,
            session_type: mode,
          }),
        );
      };
      setLoading(true);
      return;
    }

    setLoading(true);
    void completeDirectAgentMessageViaHttp(
      workingSessionId,
      selectedAgent,
      content,
      mode,
    );
  };

  const completeDirectAgentMessageViaHttp = async (
    workingSessionId: string,
    selectedAgent: string,
    content: string,
    mode: EntryMode,
    pendingAssistantId?: string,
  ) => {
    setLoading(true);
    try {
      const response = await apiFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgent,
          message: content,
          session_id: workingSessionId,
          session_type: mode,
          auto_execute: false,
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const detail = (await response.json()) as ApiSessionDetail;
      await applySessionDetail(detail, { entryMode: mode });
      setCurrentSessionId(detail.session_id);
    } catch (error) {
      setSessions((prev) =>
        prev.map((session) =>
          session.id === workingSessionId
            ? {
                ...session,
                status: 'failed',
                messages: session.messages.map((message) =>
                  message.id === pendingAssistantId
                    ? {
                        ...message,
                        role: 'system',
                        content: `Agent 调用失败：${error instanceof Error ? error.message : 'unknown error'}`,
                        metadata: {
                          agentId: selectedAgent,
                          label: 'Worker Error',
                          tone: 'red',
                        },
                      }
                    : message,
                ),
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
    if (currentSession?.entryMode === 'plan') {
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
    if (currentSession?.entryMode === 'plan') {
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
    if (currentSession?.entryMode === 'plan') {
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

  return (
    <div className="app-shell">
      <SessionList
        sessions={sessions}
        currentSessionId={currentSessionId}
        currentPlanId={currentPlanId}
        activeMode={currentSession.entryMode}
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

const createDirectSessionId = (mode: EntryMode) => {
  const timestamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
  const suffix = Math.random().toString(16).slice(2, 10);
  return `${mode}_${timestamp}_${suffix}`;
};

const createDraftSession = (
  mode: EntryMode,
  agents: Agent[],
  availablePlans: ApiWorkspacePlan[],
): Session => {
  const defaultChatAgentId =
    agents.find((agent) => agent.id === CHAT_AGENT_ID)?.id ??
    agents[0]?.id ??
    CHAT_AGENT_ID;
  const defaultWorkerAgentId =
    agents.find((agent) => agent.id !== ORCHESTRATOR_AGENT_ID && agent.id !== CHAT_AGENT_ID)?.id ??
    defaultChatAgentId;

  return {
    id: `session-${Date.now()}`,
    title: '新会话',
    status: 'draft',
    selectedAgent:
      mode === 'chat'
        ? defaultChatAgentId
        : mode === 'agent'
          ? defaultWorkerAgentId
          : ORCHESTRATOR_AGENT_ID,
    entryMode: mode,
    selectedPlanTemplateId: availablePlans[0]?.plan_id,
    messages: [],
    planHistory: [],
    traces: [],
    memory: [],
    createdAt: new Date(),
    updatedAt: new Date(),
  };
};

const isReusableDraftSession = (session: Session, mode: EntryMode) =>
  session.id.startsWith('session-') &&
  session.entryMode === mode &&
  session.status === 'draft' &&
  session.messages.length === 0 &&
  session.planHistory.length === 0 &&
  session.traces.length === 0 &&
  session.memory.length === 0 &&
  !session.plan;

const normalizeDraftSessions = (sessions: Session[]) => {
  const seenDraftModes = new Set<EntryMode>();
  return sessions.filter((session) => {
    if (!isReusableDraftSession(session, session.entryMode)) {
      return true;
    }
    if (seenDraftModes.has(session.entryMode)) {
      return false;
    }
    seenDraftModes.add(session.entryMode);
    return true;
  });
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
  entryMode: summary.session_type,
  selectedAgent:
    summary.session_type === 'chat'
      ? CHAT_AGENT_ID
      : summary.selected_agent_id ?? ORCHESTRATOR_AGENT_ID,
  selectedPlanTemplateId: undefined,
  messages: [],
  planHistory: [],
  traces: [],
  memory: [],
  createdAt: summary.updated_at ? new Date(summary.updated_at) : new Date(),
  updatedAt: summary.updated_at ? new Date(summary.updated_at) : new Date(),
});

const mergeSessions = (existing: Session[], incoming: Session[]) => {
  const localDrafts = existing.filter((session) => session.id.startsWith('session-'));
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
  if (detail.messages && detail.messages.length > 0) {
    return detail.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      timestamp: new Date(message.timestamp),
      metadata: message.metadata,
    }));
  }

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
  detail.traces && detail.traces.length > 0
    ? detail.traces.map((trace) => ({
        id: trace.id,
        stepId: trace.step_id,
        timestamp: new Date(trace.timestamp),
        type: trace.type,
        message: trace.message,
        details: trace.details,
      }))
    : Object.entries(detail.task_traces ?? {}).flatMap(([taskId, trace]) =>
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
  detail.selected_agent_id ??
  detail.current_agent ??
  detail.current_plan?.tasks?.[0]?.agent_id ??
  (detail.session_type === 'chat' ? CHAT_AGENT_ID : ORCHESTRATOR_AGENT_ID);

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
  const entryMode = detail.session_type ?? options?.entryMode ?? 'chat';
  return {
    id: detail.session_id,
    title: summarizeGoal(detail.goal),
    status: mapStatus(detail.status),
    entryMode,
    selectedAgent:
      entryMode === 'agent' && agents.some((agent) => agent.id === primaryAgent)
        ? primaryAgent
        : entryMode === 'chat'
          ? CHAT_AGENT_ID
          : options?.selectedAgent ?? primaryAgent ?? ORCHESTRATOR_AGENT_ID,
    selectedPlanTemplateId:
      options?.selectedPlanTemplateId ?? detail.current_plan?.plan_id,
    messages: mapMessages(detail),
    plan: mapPlan(detail),
    planHistory: mapPlanHistory(detail),
    traces: mapTraces(detail),
    memory,
    createdAt: detail.created_at ? new Date(detail.created_at) : new Date(),
    updatedAt: detail.updated_at ? new Date(detail.updated_at) : new Date(),
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
