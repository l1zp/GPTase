import { useEffect, useMemo, useRef, useState } from 'react';

import './App.css';
import { DetailPanel } from './components/DetailPanel';
import { MainWorkspace } from './components/MainWorkspace';
import { SessionList } from './components/SessionList';
import { apiFetch, createAppWebSocket } from './lib/api';
import type {
  Agent,
  ApiAgent,
  ApiEvalAgent,
  ApiSessionDetail,
  ApiSessionSummary,
  ApiWorkingMemoryPayload,
  EntryMode,
  EvalMetric,
  ExecutionTrace,
  Message,
  Session,
  SessionStatus,
  WorkingMemory,
} from './types';

const ORCHESTRATOR_AGENT_ID = 'orchestrator';
const CHAT_AGENT_ID = 'chat';

export default function App() {
  return <ChatApp />;
}

function ChatApp() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState('');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [evalMetrics, setEvalMetrics] = useState<EvalMetric[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeDetail, setActiveDetail] = useState<ApiSessionDetail | null>(null);
  const [evalAgentsSummary, setEvalAgentsSummary] = useState<ApiEvalAgent[]>([]);
  const memoryCacheRef = useRef<Record<string, WorkingMemory[]>>({});

  const emptySession = useMemo<Session>(
    () => ({
      id: 'session-empty',
      title: '新会话',
      status: 'draft' as const,
      selectedAgent:
        agents.find((agent) => agent.id === CHAT_AGENT_ID)?.id ??
        agents[0]?.id ??
        CHAT_AGENT_ID,
      entryMode: 'chat' as const,
      messages: [],
      traces: [],
      memory: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [agents.length === 0],
  );
  const currentSession =
    sessions.find((session) => session.id === currentSessionId) ??
    sessions[0] ??
    emptySession;

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initializeData = async () => {
    setLoading(true);
    try {
      const [agentRes, sessionRes, evalRes] = await Promise.all([
        apiFetch('/agents'),
        apiFetch('/sessions'),
        apiFetch('/evals'),
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
      setCurrentSessionId((prev) =>
        prev && mapped.some((session) => session.id === prev) ? prev : mapped[0]?.id ?? prev,
      );
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

  const applySessionDetail = async (detail: ApiSessionDetail) => {
    setActiveDetail(detail);

    const primaryAgentId = getPrimaryAgentId(detail);
    let memory: WorkingMemory[] | null = null;

    if (primaryAgentId && primaryAgentId !== ORCHESTRATOR_AGENT_ID) {
      const memoryRes = await apiFetch(`/memory/${primaryAgentId}`);
      if (memoryRes.ok) {
        const memoryPayload = (await memoryRes.json()) as ApiWorkingMemoryPayload;
        memory = mapWorkingMemory(memoryPayload);
        memoryCacheRef.current[primaryAgentId] = memory;
      } else {
        memory = memoryCacheRef.current[primaryAgentId] ?? null;
      }
    }

    setSessions((prev) => {
      const existing = prev.find((session) => session.id === detail.session_id);
      const nextSession = mapSessionDetail(detail, memory ?? existing?.memory ?? [], agents, {
        entryMode: existing?.entryMode,
        selectedAgent: existing?.selectedAgent,
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
      setActiveDetail(null);
      setEvalMetrics(mapEvalMetrics(evalAgentsSummary));
      return;
    }

    const newSession = createDraftSession('chat', agents);
    setSessions((prev) => normalizeDraftSessions([newSession, ...prev]));
    setCurrentSessionId(newSession.id);
  };

  const handleSelectSession = (id: string) => {
    setCurrentSessionId(id);
    setActiveDetail(null);
    setEvalMetrics(mapEvalMetrics(evalAgentsSummary));
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
      targetSession.id.startsWith('chat_') ||
      targetSession.id.startsWith('agent_');

    if (hasConversationContext && targetSession.entryMode !== mode) {
      const reusableDraft = sessions.find((session) => isReusableDraftSession(session, mode));
      if (reusableDraft) {
        setCurrentSessionId(reusableDraft.id);
      } else {
        const newSession = createDraftSession(mode, agents);
        setSessions((prev) => normalizeDraftSessions([newSession, ...prev]));
        setCurrentSessionId(newSession.id);
      }
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
          updatedAt: new Date(),
        };
      }),
    );
  };

  const handleSendMessage = (content: string) => {
    const entryMode = currentSession?.entryMode ?? 'chat';
    void sendDirectAgentMessage(content, entryMode);
  };

  const sendDirectAgentMessage = async (content: string, mode: EntryMode) => {
    const selectedAgent =
      mode === 'chat'
        ? CHAT_AGENT_ID
        : currentSession?.selectedAgent ?? CHAT_AGENT_ID;
    const existingSession = sessions.find((session) => session.id === currentSessionId);
    const workingSessionId = existingSession?.id ?? createDirectSessionId(mode);
    const msgTs = Date.now();
    const userMessage: Message = {
      id: `msg-${msgTs}-u`,
      role: 'user',
      content,
      timestamp: new Date(),
      metadata: {
        label: mode === 'chat' ? '任务提交' : 'Worker 任务',
        tone: mode === 'chat' ? 'blue' : 'purple',
      },
    };
    const pendingAssistantId = `msg-${msgTs}-a`;
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
            messages: mode === 'chat' ? [userMessage, pendingAssistant] : [userMessage],
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
            void applySessionDetail(payload.data as ApiSessionDetail);
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
            query: content,
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
          query: content,
          session_id: workingSessionId,
          session_type: mode,
          auto_execute: false,
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const detail = (await response.json()) as ApiSessionDetail;
      await applySessionDetail(detail);
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

  return (
    <div className="app-shell">
      <SessionList
        sessions={sessions}
        currentSessionId={currentSessionId}
        activeMode={currentSession.entryMode}
        agents={agents}
        onSelectSession={handleSelectSession}
        onCreateSession={handleCreateSession}
      />
      <MainWorkspace
        session={currentSession}
        agents={agents}
        onSendMessage={handleSendMessage}
        onSelectEntryMode={handleSelectEntryMode}
        onSelectAgent={handleSelectAgent}
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

const createDraftSession = (mode: EntryMode, agents: Agent[]): Session => {
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
      mode === 'chat' ? defaultChatAgentId : defaultWorkerAgentId,
    entryMode: mode,
    messages: [],
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
  session.traces.length === 0 &&
  session.memory.length === 0;

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
      ? 'Harness 运行时入口，负责创建 session 并调度 worker'
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
  messages: [],
  traces: [],
  memory: [],
  createdAt: summary.updated_at ? new Date(summary.updated_at) : new Date(),
  updatedAt: summary.updated_at ? new Date(summary.updated_at) : new Date(),
});

const mergeSessionSummaryIntoExisting = (existing: Session, incoming: Session): Session => {
  if (
    existing.title === incoming.title &&
    existing.status === incoming.status &&
    existing.entryMode === incoming.entryMode &&
    existing.selectedAgent === incoming.selectedAgent &&
    existing.updatedAt.getTime() === incoming.updatedAt.getTime()
  ) {
    return existing;
  }
  return {
    ...existing,
    title: incoming.title,
    status: incoming.status,
    entryMode: incoming.entryMode,
    selectedAgent: incoming.selectedAgent,
    updatedAt: incoming.updatedAt,
  };
};

const mergeSessions = (existing: Session[], incoming: Session[]) => {
  const incomingIds = new Set(incoming.map((session) => session.id));
  const localDrafts = existing.filter(
    (session) => isReusableDraftSession(session, session.entryMode) && !incomingIds.has(session.id),
  );
  const detailMap = new Map(existing.map((session) => [session.id, session]));
  const mergedRemote = incoming.map((session) => {
    const current = detailMap.get(session.id);
    return current ? mergeSessionSummaryIntoExisting(current, session) : session;
  });
  const seen = new Set<string>();
  const merged: Session[] = [];
  for (const session of [...localDrafts, ...mergedRemote]) {
    if (seen.has(session.id)) {
      continue;
    }
    seen.add(session.id);
    merged.push(session);
  }
  // Skip downstream re-renders when merge produced no observable change.
  if (
    merged.length === existing.length &&
    merged.every((session, index) => session === existing[index])
  ) {
    return existing;
  }
  return merged;
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
        label: '任务目标',
        tone: 'blue',
      },
    },
  ];

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
        label: '最新错误',
        tone: 'red',
      },
    });
  }

  return messages;
};

const formatTraceSummary = (
  kind: ExecutionTrace['kind'],
  message: string,
  step: {
    tool_name?: string;
    content_preview?: string;
    result_preview?: string;
    note?: string;
  },
) => {
  const summary =
    step.result_preview?.trim() ||
    step.content_preview?.trim() ||
    step.note?.trim() ||
    message.trim();

  if (summary) {
    return summary;
  }

  if (kind === 'tool_call') {
    return step.tool_name ? `调用工具 ${step.tool_name}` : '执行了一次工具调用';
  }

  if (kind === 'sdk_run') {
    return '执行已完成并返回结果';
  }

  if (kind === 'llm_call') {
    return '模型完成了一次响应生成';
  }

  return '系统记录了一条执行事件';
};

const isPlaceholderTraceSummary = (value: string) => /^Trace\s+\d+$/i.test(value.trim());

const getTraceEmptyReason = (
  kind: ExecutionTrace['kind'],
  message: string,
  step: {
    tool_name?: string;
    content_preview?: string;
    result_preview?: string;
    note?: string;
  },
) => {
  const hasStructuredPreview =
    Boolean(step.result_preview?.trim()) ||
    Boolean(step.content_preview?.trim()) ||
    Boolean(step.note?.trim());
  const normalizedMessage = message.trim();
  const hasMeaningfulMessage =
    Boolean(normalizedMessage) && !isPlaceholderTraceSummary(normalizedMessage);

  if (hasStructuredPreview || hasMeaningfulMessage) {
    return undefined;
  }

  if (kind === 'tool_call') {
    return step.tool_name ? `工具 ${step.tool_name} 没有返回可展示摘要` : '工具调用没有返回可展示摘要';
  }

  if (kind === 'llm_call') {
    return '本轮 LLM 调用没有返回可展示摘要';
  }

  if (kind === 'sdk_run') {
    return '本次执行完成，但没有可展示的摘要内容';
  }

  return '系统只记录了事件元信息，没有摘要文本';
};

const toTraceKind = (
  rawType: string | undefined,
  fallbackType: ExecutionTrace['type'],
): ExecutionTrace['kind'] => {
  if (rawType === 'tool_call' || rawType === 'sdk_run' || rawType === 'llm_call') {
    return rawType;
  }

  return fallbackType === 'success' ? 'sdk_run' : 'system';
};

const toTraceTone = (
  kind: ExecutionTrace['kind'],
  fallbackType: ExecutionTrace['type'],
): ExecutionTrace['statusTone'] => {
  if (fallbackType === 'error' || fallbackType === 'warning') {
    return fallbackType;
  }
  if (kind === 'sdk_run') {
    return 'success';
  }
  if (kind === 'tool_call') {
    return 'warning';
  }
  return 'log';
};

const toTraceTitle = (kind: ExecutionTrace['kind'], toolName?: string) => {
  if (kind === 'tool_call') {
    return toolName ? `调用 ${toolName}` : '调用工具（未记录名称）';
  }
  if (kind === 'sdk_run') {
    return '执行完成';
  }
  if (kind === 'llm_call') {
    return 'LLM 调用';
  }
  return '系统事件';
};

const getCommandPreview = (toolName: string | undefined, details: Record<string, unknown>) => {
  if (toolName?.toLowerCase() === 'bash') {
    if (typeof details.cmd === 'string' && details.cmd.trim()) {
      return details.cmd.trim();
    }
    const args =
      typeof details.arguments === 'object' && details.arguments
        ? (details.arguments as Record<string, unknown>)
        : undefined;
    if (typeof args?.cmd === 'string' && args.cmd.trim()) {
      return args.cmd.trim();
    }
  }

  const args =
    typeof details.arguments === 'object' && details.arguments
      ? (details.arguments as Record<string, unknown>)
      : undefined;

  if (typeof args?.path === 'string' && args.path.trim()) {
    return args.path.trim();
  }
  if (typeof args?.q === 'string' && args.q.trim()) {
    return args.q.trim();
  }
  if (typeof args?.command === 'string' && args.command.trim()) {
    return args.command.trim();
  }

  return undefined;
};

const normalizeTrace = ({
  id,
  stepId,
  timestamp,
  fallbackType,
  message,
  rawDetails,
}: {
  id: string;
  stepId: string;
  timestamp: Date;
  fallbackType: ExecutionTrace['type'];
  message: string;
  rawDetails?: Record<string, unknown>;
}): ExecutionTrace => {
  const details = rawDetails ?? {};
  const rawType =
    typeof details.type === 'string'
      ? details.type
      : undefined;
  const kind = toTraceKind(rawType, fallbackType);
  const toolName =
    typeof details.tool_name === 'string'
      ? details.tool_name
      : undefined;
  const usage =
    typeof details.usage === 'object' && details.usage
      ? (details.usage as { input_tokens?: number; output_tokens?: number })
      : undefined;
  const commandPreview = getCommandPreview(toolName, details);
  const previewFields = {
    tool_name: toolName,
    content_preview:
      typeof details.content_preview === 'string' ? details.content_preview : undefined,
    result_preview:
      typeof details.result_preview === 'string' ? details.result_preview : undefined,
    note: typeof details.note === 'string' ? details.note : undefined,
  };
  const summary = formatTraceSummary(kind, message, previewFields);
  const emptyReason = getTraceEmptyReason(kind, message, previewFields);

  return {
    id,
    stepId,
    timestamp,
    type: fallbackType,
    kind,
    statusTone: toTraceTone(kind, fallbackType),
    title: toTraceTitle(kind, toolName),
    summary: emptyReason ? '' : summary,
    summaryEmpty: Boolean(emptyReason),
    emptyReason,
    message,
    meta: {
      durationMs:
        typeof details.duration_ms === 'number' ? details.duration_ms : undefined,
      iteration:
        typeof details.iteration === 'number' ? details.iteration : undefined,
      toolName,
      commandPreview,
      inputTokens:
        typeof usage?.input_tokens === 'number' ? usage.input_tokens : undefined,
      outputTokens:
        typeof usage?.output_tokens === 'number' ? usage.output_tokens : undefined,
      messageCount:
        typeof details.message_count === 'number' ? details.message_count : undefined,
      resultChars:
        typeof details.result_chars === 'number' ? details.result_chars : undefined,
    },
    rawDetails: details,
  };
};

const mergeToolDecisionTraces = (traces: ExecutionTrace[]) => {
  const merged: ExecutionTrace[] = [];

  for (let index = 0; index < traces.length; index += 1) {
    const current = traces[index];
    const next = traces[index + 1];

    const shouldMerge =
      current.kind === 'llm_call' &&
      current.summaryEmpty &&
      next?.kind === 'tool_call' &&
      current.stepId === next.stepId &&
      current.meta.iteration !== undefined &&
      current.meta.iteration === next.meta.iteration;

    if (!shouldMerge || !next) {
      merged.push(current);
      continue;
    }

    merged.push({
      ...next,
      timestamp: current.timestamp,
      title: next.meta.toolName ? `模型决定调用 ${next.meta.toolName}` : '模型决定调用工具',
      summary: next.meta.commandPreview
        ? `准备执行: ${next.meta.commandPreview}`
        : next.summary,
      summaryEmpty: false,
      emptyReason: undefined,
      meta: {
        ...next.meta,
        durationMs: (current.meta.durationMs ?? 0) + (next.meta.durationMs ?? 0) || undefined,
        messageCount: current.meta.messageCount ?? next.meta.messageCount,
      },
      rawDetails: {
        llm_call: current.rawDetails ?? {},
        tool_call: next.rawDetails ?? {},
      },
    });
    index += 1;
  }

  return merged;
};

const mapTraces = (detail: ApiSessionDetail): ExecutionTrace[] =>
  mergeToolDecisionTraces(
    detail.traces && detail.traces.length > 0
      ? detail.traces.map((trace) =>
          normalizeTrace({
            id: trace.id,
            stepId: trace.step_id,
            timestamp: new Date(trace.timestamp),
            fallbackType: trace.type,
            message: trace.message,
            rawDetails: trace.details,
          }),
        )
      : Object.entries(detail.task_traces ?? {}).flatMap(([taskId, trace]) =>
          (trace.steps ?? []).map((step, index) =>
            normalizeTrace({
              id: `${taskId}-${index}`,
              stepId: taskId,
              timestamp: new Date(),
              fallbackType:
                step.type === 'sdk_run'
                  ? 'success'
                  : step.type === 'tool_call'
                    ? 'warning'
                    : 'log',
              message:
                step.result_preview ??
                step.content_preview ??
                step.note ??
                step.tool_name ??
                '',
              rawDetails: {
                type: step.type,
                duration_ms: step.duration_ms,
                iteration: step.iteration,
                tool_name: step.tool_name,
                arguments: step.arguments,
                content_preview: step.content_preview,
                result_preview: step.result_preview,
                note: step.note,
                message_count: step.message_count,
                result_chars: step.result_chars,
                usage: step.usage,
              },
            }),
          ),
        ),
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
  (detail.session_type === 'chat' ? CHAT_AGENT_ID : ORCHESTRATOR_AGENT_ID);

const mapSessionDetail = (
  detail: ApiSessionDetail,
  memory: WorkingMemory[],
  agents: Agent[],
  options?: {
    entryMode?: EntryMode;
    selectedAgent?: string;
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
    messages: mapMessages(detail),
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
  const { traceSteps, totalDurationMs, totalInputTokens, totalOutputTokens } = Object.values(
    detail.task_traces ?? {},
  ).reduce(
    (acc, trace) => ({
      traceSteps: acc.traceSteps + (trace.steps?.length ?? 0),
      totalDurationMs: acc.totalDurationMs + (trace.total_duration_ms ?? 0),
      totalInputTokens: acc.totalInputTokens + (trace.total_input_tokens ?? 0),
      totalOutputTokens: acc.totalOutputTokens + (trace.total_output_tokens ?? 0),
    }),
    { traceSteps: 0, totalDurationMs: 0, totalInputTokens: 0, totalOutputTokens: 0 },
  );
  const resultCount = Object.keys(detail.task_results ?? {}).length;
  const completedCount =
    detail.runtime_progress?.completed_steps ?? detail.progress?.completed ?? 0;
  const totalCount =
    detail.runtime_progress?.total_steps ?? detail.progress?.total ?? 0;

  const sessionMetrics: EvalMetric[] = [
    {
      name: '任务完成率',
      value: totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0,
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
