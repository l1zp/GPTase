import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  Settings,
  Workflow,
  Search,
  Send,
  ChevronRight,
  CheckCircle2,
  Play,
  History,
  Info,
  Layers,
  Activity,
  FlaskConical,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';

// Types
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface Agent {
  id: string;
  name: string;
}

interface SOP {
  plan_id: string;
  name: string;
  version: string;
}

interface Session {
  session_id: string;
  plan_id: string;
  status: string;
  progress: number;
  completed_steps: number;
  total_steps: number;
  created_at: string;
}

interface EvalAgent {
  agent_name: string;
  trace_count: number;
  latest_timestamp: string;
  latest_model: string;
  latest_status: string;
}

interface TraceSummary {
  agent_name: string;
  timestamp: string;
  model: string;
  total_iterations: number | null;
  final_status: string;
  total_input_tokens?: number;
  total_output_tokens?: number;
  total_duration_ms?: number;
  filename: string;
  step_count: number;
}

interface TraceStep {
  type: 'llm_call' | 'tool_call' | 'sdk_run';
  iteration?: number;
  message_count?: number;
  content_preview?: string;
  tool_calls_requested?: Array<{ name: string; arguments: string }>;
  usage?: { prompt_tokens: number; completion_tokens: number };
  duration_ms?: number;
  tool_name?: string;
  arguments?: Record<string, unknown>;
  result_preview?: string;
  note?: string;
}

interface TraceData {
  summary: TraceSummary;
  steps: TraceStep[];
}

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'sop' | 'history' | 'evals'>('chat');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sops, setSops] = useState<SOP[]>([]);
  const [selectedSop, setSelectedSop] = useState<string>('');
  const [sessions, setSessions] = useState<Session[]>([]);
  const [evalAgents, setEvalAgents] = useState<EvalAgent[]>([]);
  const [selectedEvalAgent, setSelectedEvalAgent] = useState<string>('');
  const [evalTraces, setEvalTraces] = useState<TraceSummary[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceData | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchAgents();
    fetchSops();
    fetchSessions();
    fetchEvalAgents();
  }, []);

  useEffect(() => {
    if (selectedEvalAgent) {
      setSelectedTrace(null);
      setEvalTraces([]);
      fetchAgentTraces(selectedEvalAgent);
    }
  }, [selectedEvalAgent]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch('/api/agents');
      const data = await res.json();
      setAgents(data);
      if (data.length > 0) setSelectedAgent(data[0].id);
    } catch (e) {
      console.error('Failed to fetch agents', e);
    }
  };

  const fetchSops = async () => {
    try {
      const res = await fetch('/api/sops');
      const data = await res.json();
      setSops(data);
      if (data.length > 0) setSelectedSop(data[0].plan_id);
    } catch (e) {
      console.error('Failed to fetch SOPs', e);
    }
  };

  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/sessions');
      const data = await res.json();
      setSessions(data);
    } catch (e) {
      console.error('Failed to fetch sessions', e);
    }
  };

  const fetchEvalAgents = async () => {
    try {
      const res = await fetch('/api/evals');
      const data = await res.json();
      setEvalAgents(data);
      if (data.length > 0) setSelectedEvalAgent(data[0].agent_name);
    } catch (e) { console.error('Failed to fetch eval agents', e); }
  };

  const fetchAgentTraces = async (agentName: string) => {
    try {
      const res = await fetch(`/api/evals/${agentName}/traces`);
      const data = await res.json();
      setEvalTraces(data);
    } catch (e) { console.error('Failed to fetch traces', e); }
  };

  const fetchTrace = async (agentName: string, filename: string) => {
    try {
      const res = await fetch(`/api/evals/${agentName}/traces/${filename}`);
      const data = await res.json();
      setSelectedTrace(data);
      setExpandedSteps(new Set());
    } catch (e) { console.error('Failed to fetch trace', e); }
  };

  const toggleStep = (idx: number) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !selectedAgent) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgent,
          message: inputValue,
        }),
      });

      const data = await response.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.data?.content || data.error || 'No response',
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (e) {
      console.error('Failed to send message', e);
    } finally {
      setIsTyping(false);
    }
  };

  const startSopExecution = async () => {
    if (!selectedSop) return;

    // Switch to active view or show modal
    alert(`Starting execution of ${selectedSop}... This is a prototype.`);

    try {
      const response = await fetch('/api/sop/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan_id: selectedSop,
          input_data: { text: "Explain how to use this SOP" }
        }),
      });
      const data = await response.json();
      console.log('SOP Result', data);
      fetchSessions();
    } catch (e) {
      console.error('Failed to start SOP', e);
    }
  };

  return (
    <div className="app-container" style={{ display: 'flex', height: '100vh' }}>
      {/* Sidebar */}
      <div className="sidebar" style={{
        width: '260px',
        backgroundColor: '#1e293b',
        color: '#e2e8f0',
        display: 'flex',
        flexDirection: 'column',
        padding: '20px 0'
      }}>
        <div style={{ padding: '0 20px 20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Activity size={24} color="#3b82f6" />
          <h2 style={{ fontSize: '1.25rem', margin: 0 }}>GPTase</h2>
        </div>

        <nav style={{ flex: 1 }}>
          <div
            onClick={() => setActiveTab('chat')}
            style={{
              padding: '12px 20px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              backgroundColor: activeTab === 'chat' ? '#334155' : 'transparent',
              borderLeft: activeTab === 'chat' ? '4px solid #3b82f6' : '4px solid transparent'
            }}
          >
            <MessageSquare size={18} />
            Chat
          </div>
          <div
            onClick={() => setActiveTab('sop')}
            style={{
              padding: '12px 20px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              backgroundColor: activeTab === 'sop' ? '#334155' : 'transparent',
              borderLeft: activeTab === 'sop' ? '4px solid #3b82f6' : '4px solid transparent'
            }}
          >
            <Workflow size={18} />
            SOP Planning
          </div>
          <div
            onClick={() => setActiveTab('history')}
            style={{
              padding: '12px 20px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              backgroundColor: activeTab === 'history' ? '#334155' : 'transparent',
              borderLeft: activeTab === 'history' ? '4px solid #3b82f6' : '4px solid transparent'
            }}
          >
            <History size={18} />
            Sessions
          </div>
          <div
            onClick={() => setActiveTab('evals')}
            style={{
              padding: '12px 20px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              backgroundColor: activeTab === 'evals' ? '#334155' : 'transparent',
              borderLeft: activeTab === 'evals' ? '4px solid #3b82f6' : '4px solid transparent'
            }}
          >
            <FlaskConical size={18} />
            Evals
          </div>
        </nav>

        <div style={{ padding: '20px', borderTop: '1px solid #334155', fontSize: '0.85rem' }}>
          <div style={{ color: '#94a3b8', marginBottom: '10px' }}>Current Agent:</div>
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            style={{
              width: '100%',
              padding: '8px',
              backgroundColor: '#334155',
              color: '#fff',
              border: 'none',
              borderRadius: '4px'
            }}
          >
            {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
      </div>

      {/* Main Content */}
      <div className="main" style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#f8fafc' }}>
        {activeTab === 'chat' && (
          <>
            <header style={{ padding: '20px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fff' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h3 style={{ margin: 0 }}>{selectedAgent || 'AI Assistant'}</h3>
                <span style={{ fontSize: '0.75rem', padding: '2px 6px', backgroundColor: '#dcfce7', color: '#166534', borderRadius: '4px' }}>Online</span>
              </div>
              <Settings size={20} color="#64748b" style={{ cursor: 'pointer' }} />
            </header>

            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              {messages.length === 0 && (
                <div style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', color: '#94a3b8' }}>
                  <Activity size={48} style={{ marginBottom: '20px', opacity: 0.5 }} />
                  <p>Welcome to GPTase. Start a conversation with an agent.</p>
                </div>
              )}
              {messages.map((m) => (
                <div key={m.id} style={{
                  marginBottom: '20px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: m.role === 'user' ? 'flex-end' : 'flex-start'
                }}>
                  <div style={{
                    maxWidth: '80%',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    backgroundColor: m.role === 'user' ? '#3b82f6' : '#fff',
                    color: m.role === 'user' ? '#fff' : '#1e293b',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                    border: m.role === 'assistant' ? '1px solid #e2e8f0' : 'none'
                  }}>
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                  <span style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '4px' }}>{m.timestamp}</span>
                </div>
              ))}
              {isTyping && (
                <div style={{ display: 'flex', gap: '4px', padding: '8px' }}>
                  <div className="dot" style={{ width: '8px', height: '8px', backgroundColor: '#cbd5e1', borderRadius: '50%' }}></div>
                  <div className="dot" style={{ width: '8px', height: '8px', backgroundColor: '#cbd5e1', borderRadius: '50%' }}></div>
                  <div className="dot" style={{ width: '8px', height: '8px', backgroundColor: '#cbd5e1', borderRadius: '50%' }}></div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <footer style={{ padding: '20px', borderTop: '1px solid #e2e8f0', backgroundColor: '#fff' }}>
              <div style={{ display: 'flex', gap: '10px' }}>
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Type your message..."
                  style={{
                    flex: 1,
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                    outline: 'none'
                  }}
                />
                <button
                  onClick={handleSendMessage}
                  style={{
                    padding: '0 20px',
                    backgroundColor: '#3b82f6',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  <Send size={18} />
                </button>
              </div>
            </footer>
          </>
        )}

        {activeTab === 'sop' && (
          <div style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto', width: '100%' }}>
            <div style={{ marginBottom: '30px' }}>
              <h2 style={{ fontSize: '1.8rem', marginBottom: '10px' }}>SOP Visual Planner</h2>
              <p style={{ color: '#64748b' }}>Select a workflow and visualize its execution steps.</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '30px' }}>
              {/* Visual Plan Area */}
              <div style={{ backgroundColor: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '30px', minHeight: '400px' }}>
                {selectedSop ? (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                      <h3 style={{ margin: 0 }}>{selectedSop} Workflow</h3>
                      <button
                        onClick={startSopExecution}
                        style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', backgroundColor: '#22c55e', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
                        <Play size={16} /> Execute SOP
                      </button>
                    </div>

                    {/* Simplified Workflow Viz */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                      <div style={{ padding: '15px', border: '2px solid #3b82f6', borderRadius: '8px', backgroundColor: '#eff6ff', position: 'relative' }}>
                        <div style={{ fontWeight: 'bold' }}>Step 1: Document Analysis</div>
                        <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Agent: paper-structure-analyzer</div>
                        <div style={{ position: 'absolute', bottom: '-20px', left: '50%', color: '#3b82f6' }}><ChevronRight size={20} style={{ transform: 'rotate(90deg)' }} /></div>
                      </div>

                      <div style={{ display: 'flex', gap: '20px' }}>
                         <div style={{ flex: 1, padding: '15px', border: '1px solid #e2e8f0', borderRadius: '8px', backgroundColor: '#fff' }}>
                            <div style={{ fontWeight: 'bold' }}>Step 2a: Vision Extraction</div>
                            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Agent: vision-image-analyzer</div>
                         </div>
                         <div style={{ flex: 1, padding: '15px', border: '1px solid #e2e8f0', borderRadius: '8px', backgroundColor: '#fff' }}>
                            <div style={{ fontWeight: 'bold' }}>Step 2b: Text Extraction</div>
                            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Agent: enzyme-kinetics-extractor</div>
                         </div>
                      </div>

                      <div style={{ padding: '15px', border: '1px solid #e2e8f0', borderRadius: '8px', backgroundColor: '#fff', marginTop: '10px' }}>
                        <div style={{ fontWeight: 'bold' }}>Step 3: Synthesis</div>
                        <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Agent: literature-synthesis</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div style={{ height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', color: '#94a3b8' }}>
                    Select an SOP to visualize
                  </div>
                )}
              </div>

              {/* SOP List sidebar */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ backgroundColor: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '20px' }}>
                  <h4 style={{ marginTop: 0, marginBottom: '15px' }}>Available Workflows</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {sops.map(s => (
                      <div
                        key={s.plan_id}
                        onClick={() => setSelectedSop(s.plan_id)}
                        style={{
                          padding: '10px',
                          borderRadius: '6px',
                          border: '1px solid',
                          borderColor: selectedSop === s.plan_id ? '#3b82f6' : '#e2e8f0',
                          backgroundColor: selectedSop === s.plan_id ? '#eff6ff' : 'transparent',
                          cursor: 'pointer'
                        }}
                      >
                        <div style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>{s.name || s.plan_id}</div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>ID: {s.plan_id}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ backgroundColor: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '20px' }}>
                  <h4 style={{ marginTop: 0, marginBottom: '15px' }}>Recent Sessions</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.85rem' }}>
                    {sessions.slice(0, 5).map(s => (
                      <div key={s.session_id} style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#1e293b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px' }}>{s.session_id}</span>
                        <span style={{
                          color: s.status === 'completed' ? '#166534' : '#92400e',
                          padding: '2px 6px',
                          backgroundColor: s.status === 'completed' ? '#dcfce7' : '#fef3c7',
                          borderRadius: '4px',
                          fontSize: '0.7rem'
                        }}>{s.status}</span>
                      </div>
                    ))}
                    {sessions.length === 0 && <span style={{ color: '#94a3b8' }}>No recent sessions</span>}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'evals' && (
          <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
            {/* Agent list panel */}
            <div style={{ width: '200px', borderRight: '1px solid #e2e8f0', overflowY: 'auto', backgroundColor: '#fff', flexShrink: 0 }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Agents
              </div>
              {evalAgents.map(a => (
                <div
                  key={a.agent_name}
                  onClick={() => setSelectedEvalAgent(a.agent_name)}
                  style={{ padding: '12px 16px', cursor: 'pointer', borderBottom: '1px solid #f1f5f9', borderLeft: `3px solid ${selectedEvalAgent === a.agent_name ? '#3b82f6' : 'transparent'}`, backgroundColor: selectedEvalAgent === a.agent_name ? '#eff6ff' : 'transparent' }}
                >
                  <div style={{ fontSize: '0.82rem', fontWeight: 500, color: '#1e293b', wordBreak: 'break-all' }}>{a.agent_name}</div>
                  <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '2px' }}>{a.trace_count} trace{a.trace_count !== 1 ? 's' : ''}</div>
                </div>
              ))}
              {evalAgents.length === 0 && (
                <div style={{ padding: '16px', color: '#94a3b8', fontSize: '0.8rem' }}>
                  No traces yet. Run:<br /><code style={{ fontSize: '0.72rem' }}>gptase eval -a &lt;name&gt; --live --save-output</code>
                </div>
              )}
            </div>

            {/* Trace list panel */}
            <div style={{ width: '260px', borderRight: '1px solid #e2e8f0', overflowY: 'auto', backgroundColor: '#f8fafc', flexShrink: 0 }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {selectedEvalAgent || 'Traces'}
              </div>
              {evalTraces.map(t => (
                <div
                  key={t.filename}
                  onClick={() => fetchTrace(selectedEvalAgent, t.filename)}
                  style={{ padding: '12px 16px', cursor: 'pointer', borderBottom: '1px solid #e2e8f0', borderLeft: `3px solid ${selectedTrace?.summary.filename === t.filename ? '#3b82f6' : 'transparent'}`, backgroundColor: selectedTrace?.summary.filename === t.filename ? '#eff6ff' : 'transparent' }}
                >
                  <div style={{ fontSize: '0.8rem', fontWeight: 500, color: '#1e293b' }}>
                    {t.timestamp.replace(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/, '$1-$2-$3 $4:$5:$6')}
                  </div>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '999px', backgroundColor: t.final_status === 'success' ? '#dcfce7' : '#fee2e2', color: t.final_status === 'success' ? '#166534' : '#991b1b' }}>
                      {t.final_status}
                    </span>
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>{t.step_count} steps</span>
                    {t.total_duration_ms && <span style={{ fontSize: '0.7rem', color: '#64748b' }}>{(t.total_duration_ms / 1000).toFixed(1)}s</span>}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '2px' }}>{t.model}</div>
                </div>
              ))}
              {evalTraces.length === 0 && selectedEvalAgent && (
                <div style={{ padding: '16px', color: '#94a3b8', fontSize: '0.8rem' }}>No traces for this agent.</div>
              )}
            </div>

            {/* Trace detail panel */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px', backgroundColor: '#f8fafc' }}>
              {selectedTrace ? (
                <>
                  {/* Summary card */}
                  <div style={{ backgroundColor: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '20px', marginBottom: '24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                      <h3 style={{ margin: 0, fontSize: '1rem', color: '#1e293b' }}>{selectedTrace.summary.agent_name}</h3>
                      <span style={{ fontSize: '0.75rem', padding: '3px 8px', borderRadius: '999px', backgroundColor: selectedTrace.summary.final_status === 'success' ? '#dcfce7' : '#fee2e2', color: selectedTrace.summary.final_status === 'success' ? '#166534' : '#991b1b' }}>
                        {selectedTrace.summary.final_status}
                      </span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                      {[
                        { label: 'Model', value: selectedTrace.summary.model },
                        { label: 'Iterations', value: selectedTrace.summary.total_iterations ?? '—' },
                        { label: 'Total Tokens', value: ((selectedTrace.summary.total_input_tokens ?? 0) + (selectedTrace.summary.total_output_tokens ?? 0)).toLocaleString() },
                        { label: 'Duration', value: selectedTrace.summary.total_duration_ms ? `${(selectedTrace.summary.total_duration_ms / 1000).toFixed(1)}s` : '—' },
                      ].map(stat => (
                        <div key={stat.label} style={{ backgroundColor: '#f8fafc', borderRadius: '8px', padding: '12px' }}>
                          <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{stat.label}</div>
                          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#1e293b', marginTop: '4px' }}>{stat.value}</div>
                        </div>
                      ))}
                    </div>
                    {selectedTrace.summary.total_input_tokens !== undefined && (
                      <div style={{ marginTop: '10px', fontSize: '0.78rem', color: '#64748b' }}>
                        {selectedTrace.summary.total_input_tokens?.toLocaleString()} input / {selectedTrace.summary.total_output_tokens?.toLocaleString()} output tokens
                      </div>
                    )}
                  </div>

                  {/* Steps timeline */}
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>
                    Execution Steps ({selectedTrace.steps.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {selectedTrace.steps.map((step, idx) => {
                      const isExpanded = expandedSteps.has(idx);
                      const isLlm = step.type === 'llm_call';
                      const isTool = step.type === 'tool_call';
                      const borderColor = isLlm ? '#3b82f6' : isTool ? '#22c55e' : '#94a3b8';
                      const badgeBg = isLlm ? '#eff6ff' : isTool ? '#f0fdf4' : '#f1f5f9';
                      const badgeColor = isLlm ? '#1d4ed8' : isTool ? '#15803d' : '#475569';
                      const badgeLabel = isLlm ? `LLM Call #${step.iteration}` : isTool ? `Tool: ${step.tool_name}` : 'SDK Run';
                      return (
                        <div key={idx} style={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', borderLeft: `4px solid ${borderColor}`, overflow: 'hidden' }}>
                          <div onClick={() => toggleStep(idx)} style={{ padding: '12px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                              <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '999px', backgroundColor: badgeBg, color: badgeColor, fontWeight: 600, whiteSpace: 'nowrap' }}>
                                {badgeLabel}
                              </span>
                              {isLlm && (
                                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                                  {step.message_count} msgs · {step.usage?.prompt_tokens?.toLocaleString()} in / {step.usage?.completion_tokens?.toLocaleString()} out tokens
                                </span>
                              )}
                              {isTool && (
                                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>iter {step.iteration}</span>
                              )}
                              {step.type === 'sdk_run' && step.note && (
                                <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{step.note}</span>
                              )}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                              {step.duration_ms !== undefined && (
                                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{step.duration_ms}ms</span>
                              )}
                              {isExpanded ? <ChevronUp size={14} color="#94a3b8" /> : <ChevronDown size={14} color="#94a3b8" />}
                            </div>
                          </div>
                          {isExpanded && (
                            <div style={{ borderTop: '1px solid #f1f5f9', padding: '14px 16px', backgroundColor: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                              {isLlm && step.content_preview && (
                                <div>
                                  <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>Response Preview</div>
                                  <pre style={{ margin: 0, fontSize: '0.78rem', color: '#1e293b', whiteSpace: 'pre-wrap', wordBreak: 'break-word', backgroundColor: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0', maxHeight: '200px', overflowY: 'auto' }}>
                                    {step.content_preview}
                                  </pre>
                                </div>
                              )}
                              {isLlm && step.tool_calls_requested && step.tool_calls_requested.length > 0 && (
                                <div>
                                  <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>Tool Calls Requested</div>
                                  {step.tool_calls_requested.map((tc, i) => (
                                    <div key={i} style={{ fontSize: '0.8rem', padding: '6px 10px', backgroundColor: '#fff', borderRadius: '4px', border: '1px solid #e2e8f0', marginBottom: '4px' }}>
                                      <span style={{ fontWeight: 600, color: '#1d4ed8' }}>{tc.name}</span>
                                      <span style={{ color: '#64748b', marginLeft: '8px' }}>{tc.arguments.slice(0, 100)}{tc.arguments.length > 100 ? '…' : ''}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              {isTool && step.arguments && (
                                <div>
                                  <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>Arguments</div>
                                  <pre style={{ margin: 0, fontSize: '0.78rem', color: '#1e293b', whiteSpace: 'pre-wrap', wordBreak: 'break-word', backgroundColor: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                                    {JSON.stringify(step.arguments, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {isTool && step.result_preview && (
                                <div>
                                  <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>Result Preview</div>
                                  <pre style={{ margin: 0, fontSize: '0.78rem', color: '#1e293b', whiteSpace: 'pre-wrap', wordBreak: 'break-word', backgroundColor: '#fff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0', maxHeight: '150px', overflowY: 'auto' }}>
                                    {step.result_preview}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : (
                <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', flexDirection: 'column', gap: '12px' }}>
                  <FlaskConical size={40} style={{ opacity: 0.3 }} />
                  <span>Select a trace to view execution details</span>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto', width: '100%' }}>
            <h2 style={{ fontSize: '1.8rem', marginBottom: '20px' }}>Execution History</h2>
            <div style={{ backgroundColor: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead style={{ backgroundColor: '#f1f5f9' }}>
                  <tr>
                    <th style={{ padding: '15px', borderBottom: '1px solid #e2e8f0' }}>Session ID</th>
                    <th style={{ padding: '15px', borderBottom: '1px solid #e2e8f0' }}>SOP Plan</th>
                    <th style={{ padding: '15px', borderBottom: '1px solid #e2e8f0' }}>Status</th>
                    <th style={{ padding: '15px', borderBottom: '1px solid #e2e8f0' }}>Progress</th>
                    <th style={{ padding: '15px', borderBottom: '1px solid #e2e8f0' }}>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map(s => (
                    <tr key={s.session_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '15px', fontSize: '0.9rem', color: '#3b82f6', cursor: 'pointer' }}>{s.session_id}</td>
                      <td style={{ padding: '15px', fontSize: '0.9rem' }}>{s.plan_id}</td>
                      <td style={{ padding: '15px' }}>
                        <span style={{
                          padding: '4px 8px',
                          borderRadius: '999px',
                          fontSize: '0.75rem',
                          backgroundColor: s.status === 'completed' ? '#dcfce7' : s.status === 'failed' ? '#fee2e2' : '#fef3c7',
                          color: s.status === 'completed' ? '#166534' : s.status === 'failed' ? '#991b1b' : '#92400e'
                        }}>
                          {s.status}
                        </span>
                      </td>
                      <td style={{ padding: '15px' }}>
                        <div style={{ width: '100%', height: '8px', backgroundColor: '#e2e8f0', borderRadius: '4px', position: 'relative' }}>
                          <div style={{ width: `${s.progress}%`, height: '100%', backgroundColor: '#3b82f6', borderRadius: '4px' }}></div>
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>{s.progress}% ({s.completed_steps}/{s.total_steps})</div>
                      </td>
                      <td style={{ padding: '15px', fontSize: '0.8rem', color: '#64748b' }}>{new Date(s.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                  {sessions.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>No execution history found</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
