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
  Activity
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

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'sop' | 'history'>('chat');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sops, setSops] = useState<SOP[]>([]);
  const [selectedSop, setSelectedSop] = useState<string>('');
  const [sessions, setSessions] = useState<Session[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchAgents();
    fetchSops();
    fetchSessions();
  }, []);

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
