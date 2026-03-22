import React, { useEffect, useRef, useState } from 'react';
import {
  Activity,
  Bot,
  CheckCircle2,
  Clock3,
  GitBranch,
  History,
  Play,
  RefreshCw,
  Send,
  Square,
  User,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';

type Agent = {
  id: string;
  name: string;
  description?: string;
};

type PlanSummary = {
  plan_id: string;
  goal?: string;
  summary?: string;
  tasks?: TaskPlan[];
};

type TaskPlan = {
  task_id: string;
  description: string;
  agent_id?: string;
  dependencies?: string[];
  status?: string;
  expected_output?: string;
};

type GoalEvaluation = {
  goal_achieved: boolean;
  reason: string;
  missing_gaps: string[];
  next_action: string;
};

type SessionSummary = {
  session_id: string;
  goal: string;
  status: string;
  current_plan_id?: string;
};

type TraceStep = {
  type: 'llm_call' | 'tool_call' | 'sdk_run';
  iteration?: number;
  tool_name?: string;
  content_preview?: string;
  result_preview?: string;
  duration_ms?: number;
  arguments?: Record<string, unknown>;
  tool_calls_requested?: Array<{ name: string; arguments: string }>;
  usage?: { prompt_tokens?: number; completion_tokens?: number };
  note?: string;
};

type TraceData = {
  steps?: TraceStep[];
  total_duration_ms?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
};

type SessionDetail = {
  session_id: string;
  status: string;
  goal: string;
  draft_source?: string;
  current_plan?: PlanSummary | null;
  plan_history?: PlanSummary[];
  progress?: Record<string, number> | null;
  goal_evaluation?: GoalEvaluation;
  task_results?: Record<string, unknown>;
  task_traces?: Record<string, TraceData>;
  current_task?: string | null;
  current_agent?: string | null;
  latest_error?: { task_id: string; error: string } | null;
  runtime_progress?: {
    completed_steps: number;
    total_steps: number;
    progress_percent: number;
  } | null;
};

type EvalAgent = {
  agent_name: string;
  trace_count: number;
  latest_timestamp: string;
  latest_model: string;
  latest_status: string;
};

type TraceSummary = {
  filename: string;
  agent_name: string;
  timestamp: string;
  model: string;
  final_status: string;
  total_iterations?: number | null;
  total_input_tokens?: number;
  total_output_tokens?: number;
  total_duration_ms?: number;
};

type StoredTrace = {
  summary: TraceSummary;
  steps: TraceStep[];
};

type ChatBubble = {
  id: string;
  role: 'user' | 'assistant';
  title?: string;
  content: string;
  sessionId?: string;
  kind?: 'chat' | 'draft' | 'status';
};

const shell = {
  bg: '#f3efe6',
  panel: '#fffaf2',
  ink: '#1f2937',
  muted: '#6b7280',
  line: '#e7dbc7',
  accent: '#bd5d38',
  accentSoft: '#f4dfd1',
  accentDark: '#893e20',
  green: '#166534',
  red: '#991b1b',
  gold: '#9a6b19',
};

const statusTone = (status: string) => {
  if (status === 'completed') return { bg: '#dcfce7', fg: shell.green };
  if (status === 'failed' || status === 'blocked') return { bg: '#fee2e2', fg: shell.red };
  if (status === 'awaiting_approval' || status === 'awaiting_user_input') {
    return { bg: '#fef3c7', fg: shell.gold };
  }
  return { bg: '#e0f2fe', fg: '#0c4a6e' };
};

const cardStyle: React.CSSProperties = {
  background: shell.panel,
  border: `1px solid ${shell.line}`,
  borderRadius: 18,
  boxShadow: '0 16px 40px rgba(97, 63, 22, 0.08)',
};

const App: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<SessionDetail | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [reviewFeedback, setReviewFeedback] = useState('');
  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [loading, setLoading] = useState(false);
  const [storedEvalAgents, setStoredEvalAgents] = useState<EvalAgent[]>([]);
  const [selectedEvalAgent, setSelectedEvalAgent] = useState('');
  const [storedTraces, setStoredTraces] = useState<TraceSummary[]>([]);
  const [selectedStoredTrace, setSelectedStoredTrace] = useState<StoredTrace | null>(null);
  const [activeTaskId, setActiveTaskId] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void Promise.all([fetchAgents(), fetchSessions(), fetchEvalAgents()]);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!activeSession) return;
    const timer = window.setInterval(() => {
      void fetchSession(activeSession.session_id);
      void fetchSessions();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeSession?.session_id]);

  useEffect(() => {
    if (!selectedEvalAgent) return;
    void fetchStoredTraces(selectedEvalAgent);
  }, [selectedEvalAgent]);

  useEffect(() => {
    const taskIds = Object.keys(activeSession?.task_traces ?? {});
    if (!activeTaskId && taskIds.length > 0) {
      setActiveTaskId(taskIds[0]);
    }
    if (activeTaskId && !taskIds.includes(activeTaskId)) {
      setActiveTaskId(taskIds[0] ?? '');
    }
  }, [activeSession?.task_traces, activeTaskId]);

  const fetchAgents = async () => {
    const res = await fetch('/api/agents');
    const data = (await res.json()) as Agent[];
    setAgents(data);
  };

  const fetchSessions = async () => {
    const res = await fetch('/api/sessions');
    const data = (await res.json()) as SessionSummary[];
    setSessions(data);
  };

  const fetchSession = async (sessionId: string) => {
    const res = await fetch(`/api/sessions/${sessionId}`);
    if (!res.ok) return;
    const data = (await res.json()) as SessionDetail;
    setActiveSession(data);
  };

  const fetchEvalAgents = async () => {
    const res = await fetch('/api/evals');
    const data = (await res.json()) as EvalAgent[];
    setStoredEvalAgents(data);
    if (!selectedEvalAgent && data[0]) setSelectedEvalAgent(data[0].agent_name);
  };

  const fetchStoredTraces = async (agentName: string) => {
    const res = await fetch(`/api/evals/${agentName}/traces`);
    const data = (await res.json()) as TraceSummary[];
    setStoredTraces(data);
  };

  const fetchStoredTrace = async (agentName: string, filename: string) => {
    const res = await fetch(`/api/evals/${agentName}/traces/${filename}`);
    const data = (await res.json()) as StoredTrace;
    setSelectedStoredTrace(data);
  };

  const pushMessage = (message: ChatBubble) => {
    setMessages((prev) => [...prev, message]);
  };

  const summarizeSession = (session: SessionDetail) => {
    const planId = session.current_plan?.plan_id ?? 'draft';
    const taskCount = session.current_plan?.tasks?.length ?? 0;
    return [
      `Session: \`${session.session_id}\``,
      `Status: **${session.status}**`,
      `Current plan: \`${planId}\` with ${taskCount} tasks`,
      session.goal_evaluation?.reason ? `Goal evaluation: ${session.goal_evaluation.reason}` : '',
    ].filter(Boolean).join('\n\n');
  };

  const handleSubmitGoal = async () => {
    if (!chatInput.trim() || loading) return;
    const message = chatInput.trim();
    setChatInput('');
    pushMessage({
      id: `${Date.now()}_user`,
      role: 'user',
      content: message,
    });
    setLoading(true);
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: 'auto',
          message,
          auto_execute: false,
        }),
      });
      const data = (await res.json()) as SessionDetail;
      setActiveSession(data);
      pushMessage({
        id: `${Date.now()}_assistant`,
        role: 'assistant',
        title: 'Draft Plan Ready',
        kind: 'draft',
        sessionId: data.session_id,
        content: summarizeSession(data),
      });
      void fetchSessions();
    } finally {
      setLoading(false);
    }
  };

  const approveCurrentPlan = async () => {
    if (!activeSession || loading) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/sessions/${activeSession.session_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: reviewFeedback.trim() || undefined,
        }),
      });
      const data = (await res.json()) as SessionDetail;
      setActiveSession(data);
      setReviewFeedback('');
      pushMessage({
        id: `${Date.now()}_approve`,
        role: 'assistant',
        title: 'Plan Approved',
        kind: 'status',
        sessionId: data.session_id,
        content: summarizeSession(data),
      });
      void fetchSessions();
    } finally {
      setLoading(false);
    }
  };

  const sendSessionFeedback = async () => {
    if (!activeSession || !reviewFeedback.trim() || loading) return;
    const feedback = reviewFeedback.trim();
    pushMessage({
      id: `${Date.now()}_feedback_user`,
      role: 'user',
      content: feedback,
    });
    setLoading(true);
    try {
      const res = await fetch(`/api/sessions/${activeSession.session_id}/input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      });
      const data = (await res.json()) as SessionDetail;
      setActiveSession(data);
      setReviewFeedback('');
      pushMessage({
        id: `${Date.now()}_feedback_assistant`,
        role: 'assistant',
        title: 'Session Updated',
        kind: 'status',
        sessionId: data.session_id,
        content: summarizeSession(data),
      });
      void fetchSessions();
    } finally {
      setLoading(false);
    }
  };

  const selectSession = async (sessionId: string) => {
    await fetchSession(sessionId);
  };

  const currentTrace = activeSession?.task_traces?.[activeTaskId];
  const currentPlanTasks = activeSession?.current_plan?.tasks ?? [];
  const runtimeProgress = activeSession?.runtime_progress;
  const progressPercent = Math.max(
    0,
    Math.min(100, runtimeProgress?.progress_percent ?? 0),
  );
  const currentTask = activeSession?.current_task;
  const currentAgent = activeSession?.current_agent;
  const latestError = activeSession?.latest_error;

  return (
    <div style={{
      minHeight: '100vh',
      background: `linear-gradient(135deg, ${shell.bg} 0%, #f8f3eb 45%, #efe2d3 100%)`,
      color: shell.ink,
      fontFamily: '"Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif',
      padding: 20,
    }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: '280px minmax(420px, 1.4fr) minmax(360px, 1fr)',
        gap: 18,
        alignItems: 'start',
      }}>
        <aside style={{ ...cardStyle, padding: 18, position: 'sticky', top: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
            <div style={{
              width: 42,
              height: 42,
              borderRadius: 12,
              background: shell.accentSoft,
              display: 'grid',
              placeItems: 'center',
              color: shell.accentDark,
            }}>
              <GitBranch size={20} />
            </div>
            <div>
              <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', color: shell.muted }}>
                GPTase
              </div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>Harness Console</div>
            </div>
          </div>

          <section style={{ marginBottom: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ fontWeight: 700 }}>Agents</div>
              <span style={{ color: shell.muted, fontSize: 13 }}>{agents.length}</span>
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {agents.slice(0, 6).map((agent) => (
                <div key={agent.id} style={{
                  padding: '10px 12px',
                  borderRadius: 12,
                  background: agent.id === 'auto' ? shell.accentSoft : '#fff',
                  border: `1px solid ${shell.line}`,
                }}>
                  <div style={{ fontWeight: 700 }}>{agent.name}</div>
                  {agent.description && (
                    <div style={{ fontSize: 12, color: shell.muted, marginTop: 4 }}>{agent.description}</div>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ fontWeight: 700 }}>Recent Sessions</div>
              <button onClick={() => void fetchSessions()} style={miniButtonStyle}>
                <RefreshCw size={14} />
              </button>
            </div>
            <div style={{ display: 'grid', gap: 8, maxHeight: '55vh', overflow: 'auto' }}>
              {sessions.map((session) => {
                const tone = statusTone(session.status);
                const selected = activeSession?.session_id === session.session_id;
                return (
                  <button
                    key={session.session_id}
                    onClick={() => void selectSession(session.session_id)}
                    style={{
                      textAlign: 'left',
                      padding: 12,
                      borderRadius: 14,
                      border: `1px solid ${selected ? shell.accent : shell.line}`,
                      background: selected ? '#fff2e8' : '#fff',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ fontSize: 12, color: shell.muted }}>{session.session_id}</div>
                    <div style={{ fontWeight: 700, margin: '6px 0' }}>{session.goal || 'Untitled goal'}</div>
                    <span style={{
                      display: 'inline-block',
                      padding: '4px 8px',
                      borderRadius: 999,
                      background: tone.bg,
                      color: tone.fg,
                      fontSize: 12,
                      fontWeight: 700,
                    }}>
                      {session.status}
                    </span>
                  </button>
                );
              })}
              {sessions.length === 0 && (
                <div style={{ color: shell.muted, fontSize: 13 }}>No sessions yet.</div>
              )}
            </div>
          </section>
        </aside>

        <main style={{ display: 'grid', gap: 18 }}>
          <section style={{
            ...cardStyle,
            padding: 18,
            background: latestError
              ? 'linear-gradient(135deg, #fff6f4 0%, #fffaf2 100%)'
              : 'linear-gradient(135deg, #fff4eb 0%, #fffaf2 100%)',
            border: `1px solid ${latestError ? '#efc6bf' : shell.line}`,
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: 16,
              marginBottom: 14,
              flexWrap: 'wrap',
            }}>
              <div>
                <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', color: shell.muted }}>
                  Runtime Status
                </div>
                <div style={{ fontSize: 28, fontWeight: 700 }}>
                  {currentTask ? `Running ${currentTask}` : 'Waiting For Next Step'}
                </div>
                <div style={{ color: shell.muted, fontSize: 15, marginTop: 6 }}>
                  Agent: <strong style={{ color: shell.accentDark }}>{currentAgent || 'unknown'}</strong>
                </div>
              </div>
              {activeSession && (
                <span style={{
                  padding: '6px 10px',
                  borderRadius: 999,
                  background: statusTone(activeSession.status).bg,
                  color: statusTone(activeSession.status).fg,
                  fontWeight: 700,
                  fontSize: 13,
                }}>
                  {activeSession.status}
                </span>
              )}
            </div>

            <div style={{ display: 'grid', gap: 10 }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: 13,
                color: shell.muted,
              }}>
                <span>
                  Progress {runtimeProgress
                    ? `${runtimeProgress.completed_steps}/${runtimeProgress.total_steps}`
                    : '0/0'}
                </span>
                <span>{progressPercent.toFixed(0)}%</span>
              </div>
              <div style={{
                width: '100%',
                height: 10,
                borderRadius: 999,
                background: '#f0e3d2',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${progressPercent}%`,
                  height: '100%',
                  borderRadius: 999,
                  background: `linear-gradient(90deg, ${shell.accent} 0%, ${shell.accentDark} 100%)`,
                  transition: 'width 180ms ease-out',
                }} />
              </div>
            </div>

            {latestError && (
              <div style={{
                marginTop: 14,
                padding: 14,
                borderRadius: 14,
                background: '#fff1ef',
                border: '1px solid #efc6bf',
                color: shell.red,
              }}>
                <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>
                  Latest Error
                </div>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>{latestError.task_id}</div>
                <div style={{ fontSize: 14, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {latestError.error}
                </div>
              </div>
            )}
          </section>

          <section style={{ ...cardStyle, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', color: shell.muted }}>
                  Conversation
                </div>
                <div style={{ fontSize: 26, fontWeight: 700 }}>Goal Chat</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: shell.muted, fontSize: 13 }}>
                <Bot size={16} />
                `auto`
              </div>
            </div>

            <div style={{
              minHeight: 360,
              maxHeight: 480,
              overflow: 'auto',
              display: 'grid',
              gap: 12,
              paddingRight: 6,
            }}>
              {messages.length === 0 && (
                <div style={{
                  borderRadius: 16,
                  border: `1px dashed ${shell.line}`,
                  padding: 18,
                  background: '#fff',
                  color: shell.muted,
                }}>
                  Start with a goal. The orchestrator will create a draft plan first, then you can revise or approve it from the same thread.
                </div>
              )}
              {messages.map((message) => (
                <div key={message.id} style={{
                  justifySelf: message.role === 'user' ? 'end' : 'start',
                  maxWidth: '88%',
                  borderRadius: 18,
                  padding: 14,
                  background: message.role === 'user' ? shell.accentDark : '#fff',
                  color: message.role === 'user' ? '#fff7ed' : shell.ink,
                  border: message.role === 'user' ? 'none' : `1px solid ${shell.line}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    {message.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                    <strong>{message.title || (message.role === 'user' ? 'You' : 'Orchestrator')}</strong>
                    {message.sessionId && (
                      <span style={{ fontSize: 12, opacity: 0.8 }}>{message.sessionId}</span>
                    )}
                  </div>
                  <div style={{ fontSize: 15, lineHeight: 1.6 }}>
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            <div style={{
              marginTop: 14,
              display: 'grid',
              gap: 10,
              borderTop: `1px solid ${shell.line}`,
              paddingTop: 14,
            }}>
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Describe the goal, desired output, and any constraints..."
                rows={4}
                style={textAreaStyle}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                <div style={{ color: shell.muted, fontSize: 13 }}>
                  Initial send creates a draft plan for review.
                </div>
                <button onClick={() => void handleSubmitGoal()} disabled={loading} style={primaryButtonStyle}>
                  <Send size={16} />
                  Submit Goal
                </button>
              </div>
            </div>
          </section>

          <section style={{ ...cardStyle, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', color: shell.muted }}>
                  Draft Review
                </div>
                <div style={{ fontSize: 24, fontWeight: 700 }}>
                  {activeSession?.current_plan?.plan_id ?? 'No Active Plan'}
                </div>
              </div>
              {activeSession && (
                <span style={{
                  padding: '6px 10px',
                  borderRadius: 999,
                  background: statusTone(activeSession.status).bg,
                  color: statusTone(activeSession.status).fg,
                  fontWeight: 700,
                  fontSize: 13,
                }}>
                  {activeSession.status}
                </span>
              )}
            </div>

            {activeSession?.current_plan ? (
              <div style={{ display: 'grid', gap: 14 }}>
                <div style={{ color: shell.muted, fontSize: 14 }}>{activeSession.goal}</div>
                <div style={{ display: 'grid', gap: 10 }}>
                  {currentPlanTasks.map((task) => {
                    const isCurrentTask = task.task_id === currentTask;
                    return (
                    <div key={task.task_id} style={{
                      border: `1px solid ${isCurrentTask ? shell.accent : shell.line}`,
                      borderRadius: 14,
                      padding: 12,
                      background: isCurrentTask ? '#fff3e8' : '#fff',
                      boxShadow: isCurrentTask ? '0 8px 24px rgba(137, 62, 32, 0.12)' : 'none',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                        <div>
                          <div style={{ fontWeight: 700 }}>
                            {task.task_id}. {task.description}
                            {isCurrentTask && (
                              <span style={{
                                marginLeft: 8,
                                padding: '3px 8px',
                                borderRadius: 999,
                                background: shell.accentDark,
                                color: '#fff7ed',
                                fontSize: 11,
                                verticalAlign: 'middle',
                              }}>
                                running
                              </span>
                            )}
                          </div>
                          <div style={{ color: shell.muted, fontSize: 13, marginTop: 4 }}>
                            Agent: {task.agent_id || 'auto'}
                          </div>
                        </div>
                        {task.status && (
                          <span style={{ fontSize: 12, color: shell.muted }}>{task.status}</span>
                        )}
                      </div>
                      {task.dependencies && task.dependencies.length > 0 && (
                        <div style={{ marginTop: 8, fontSize: 12, color: shell.muted }}>
                          Depends on: {task.dependencies.join(', ')}
                        </div>
                      )}
                    </div>
                  )})}
                </div>

                <textarea
                  value={reviewFeedback}
                  onChange={(e) => setReviewFeedback(e.target.value)}
                  rows={3}
                  placeholder="Add revision notes, approval comments, or follow-up instructions..."
                  style={textAreaStyle}
                />

                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button onClick={() => void approveCurrentPlan()} disabled={loading || !activeSession} style={primaryButtonStyle}>
                    <Play size={16} />
                    Approve And Run
                  </button>
                  <button onClick={() => void sendSessionFeedback()} disabled={loading || !activeSession || !reviewFeedback.trim()} style={secondaryButtonStyle}>
                    <Square size={16} />
                    Revise / Continue
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ color: shell.muted }}>No active session selected.</div>
            )}
          </section>
        </main>

        <aside style={{ display: 'grid', gap: 18 }}>
          <section style={{ ...cardStyle, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', color: shell.muted }}>
                  Live Monitor
                </div>
                <div style={{ fontSize: 24, fontWeight: 700 }}>Agent Trajectories</div>
              </div>
              <Activity size={18} color={shell.accentDark} />
            </div>

            {activeSession ? (
              <div style={{ display: 'grid', gap: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                  <MetricCard icon={<History size={16} />} label="Plans" value={String(activeSession.plan_history?.length ?? 0)} />
                  <MetricCard icon={<CheckCircle2 size={16} />} label="Tasks" value={String(Object.keys(activeSession.task_results ?? {}).length)} />
                  <MetricCard icon={<Clock3 size={16} />} label="Now Running" value={activeSession.current_task ?? 'Idle'} />
                </div>

                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: 10,
                }}>
                  <MetricCard icon={<Bot size={16} />} label="Current Agent" value={activeSession.current_agent ?? 'Unknown'} />
                  <MetricCard icon={<Clock3 size={16} />} label="Goal" value={activeSession.goal_evaluation?.goal_achieved ? 'Met' : 'Open'} />
                </div>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {Object.keys(activeSession.task_traces ?? {}).map((taskId) => (
                    <button
                      key={taskId}
                      onClick={() => setActiveTaskId(taskId)}
                      style={{
                        padding: '8px 10px',
                        borderRadius: 999,
                        border: `1px solid ${activeTaskId === taskId ? shell.accent : shell.line}`,
                        background: activeTaskId === taskId ? shell.accentSoft : '#fff',
                        cursor: 'pointer',
                      }}
                    >
                      {taskId}
                    </button>
                  ))}
                </div>

                {currentTrace ? (
                  <div style={{ display: 'grid', gap: 10, maxHeight: 420, overflow: 'auto' }}>
                    {(currentTrace.steps ?? []).map((step, index) => (
                      <div key={`${activeTaskId}_${index}`} style={{
                        border: `1px solid ${shell.line}`,
                        borderRadius: 14,
                        padding: 12,
                        background: '#fff',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                          <strong>{step.type}</strong>
                          <span style={{ color: shell.muted, fontSize: 12 }}>
                            {step.duration_ms ? `${(step.duration_ms / 1000).toFixed(2)}s` : '—'}
                          </span>
                        </div>
                        {step.tool_name && <div style={{ fontSize: 13, color: shell.accentDark }}>Tool: {step.tool_name}</div>}
                        {step.content_preview && <div style={tracePreviewStyle}>{step.content_preview}</div>}
                        {step.result_preview && <div style={tracePreviewStyle}>{step.result_preview}</div>}
                        {step.note && <div style={tracePreviewStyle}>{step.note}</div>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: shell.muted, fontSize: 14 }}>
                    No live task traces yet for this session.
                  </div>
                )}
              </div>
            ) : (
              <div style={{ color: shell.muted }}>Pick a session to inspect its live plan and agent traces.</div>
            )}
          </section>

          <section style={{ ...cardStyle, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.12em', color: shell.muted }}>
                  Stored Traces
                </div>
                <div style={{ fontSize: 24, fontWeight: 700 }}>Agent Archive</div>
              </div>
            </div>

            <select
              value={selectedEvalAgent}
              onChange={(e) => setSelectedEvalAgent(e.target.value)}
              style={selectStyle}
            >
              <option value="">Select agent</option>
              {storedEvalAgents.map((agent) => (
                <option key={agent.agent_name} value={agent.agent_name}>
                  {agent.agent_name} ({agent.trace_count})
                </option>
              ))}
            </select>

            <div style={{ display: 'grid', gap: 8, marginTop: 12, maxHeight: 180, overflow: 'auto' }}>
              {storedTraces.map((trace) => (
                <button
                  key={trace.filename}
                  onClick={() => void fetchStoredTrace(trace.agent_name, trace.filename)}
                  style={{
                    textAlign: 'left',
                    padding: 10,
                    borderRadius: 12,
                    border: `1px solid ${shell.line}`,
                    background: selectedStoredTrace?.summary.filename === trace.filename ? '#fff2e8' : '#fff',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: 700 }}>{trace.timestamp}</div>
                  <div style={{ fontSize: 12, color: shell.muted }}>{trace.model}</div>
                </button>
              ))}
            </div>

            {selectedStoredTrace && (
              <div style={{ marginTop: 14, borderTop: `1px solid ${shell.line}`, paddingTop: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <Bot size={16} />
                  <strong>{selectedStoredTrace.summary.agent_name}</strong>
                </div>
                <div style={{ color: shell.muted, fontSize: 13, marginBottom: 10 }}>
                  {selectedStoredTrace.steps.length} steps
                </div>
                <div style={{ display: 'grid', gap: 8, maxHeight: 220, overflow: 'auto' }}>
                  {selectedStoredTrace.steps.map((step, index) => (
                    <div key={`${selectedStoredTrace.summary.filename}_${index}`} style={{
                      padding: 10,
                      borderRadius: 12,
                      background: '#fff',
                      border: `1px solid ${shell.line}`,
                    }}>
                      <div style={{ fontWeight: 700, marginBottom: 4 }}>{step.type}</div>
                      {step.content_preview && <div style={tracePreviewStyle}>{step.content_preview}</div>}
                      {step.result_preview && <div style={tracePreviewStyle}>{step.result_preview}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
};

const MetricCard: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({
  icon,
  label,
  value,
}) => (
  <div style={{
    borderRadius: 14,
    border: `1px solid ${shell.line}`,
    padding: 12,
    background: '#fff',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: shell.muted, fontSize: 12 }}>
      {icon}
      {label}
    </div>
    <div style={{ marginTop: 8, fontWeight: 700, fontSize: 22 }}>{value}</div>
  </div>
);

const primaryButtonStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  padding: '10px 14px',
  borderRadius: 12,
  border: 'none',
  background: shell.accentDark,
  color: '#fff7ed',
  cursor: 'pointer',
  fontWeight: 700,
};

const secondaryButtonStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  padding: '10px 14px',
  borderRadius: 12,
  border: `1px solid ${shell.line}`,
  background: '#fff',
  color: shell.ink,
  cursor: 'pointer',
  fontWeight: 700,
};

const miniButtonStyle: React.CSSProperties = {
  width: 30,
  height: 30,
  display: 'grid',
  placeItems: 'center',
  borderRadius: 10,
  border: `1px solid ${shell.line}`,
  background: '#fff',
  cursor: 'pointer',
};

const textAreaStyle: React.CSSProperties = {
  width: '100%',
  resize: 'vertical',
  borderRadius: 14,
  border: `1px solid ${shell.line}`,
  background: '#fff',
  color: shell.ink,
  padding: 12,
  fontSize: 15,
  lineHeight: 1.5,
  fontFamily: 'inherit',
  boxSizing: 'border-box',
};

const selectStyle: React.CSSProperties = {
  width: '100%',
  borderRadius: 12,
  border: `1px solid ${shell.line}`,
  padding: '10px 12px',
  background: '#fff',
  color: shell.ink,
  fontFamily: 'inherit',
};

const tracePreviewStyle: React.CSSProperties = {
  marginTop: 8,
  padding: 10,
  borderRadius: 10,
  background: '#faf6ef',
  color: shell.ink,
  fontSize: 13,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
};

export default App;
