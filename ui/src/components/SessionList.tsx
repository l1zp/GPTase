import { ExternalLink, LayoutGrid, Plus, Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import type { Agent, EntryMode, Session } from '../types';

interface SessionListProps {
  sessions: Session[];
  currentSessionId: string;
  currentPlanId: string | null;
  activeMode: EntryMode;
  agents: Agent[];
  onSelectSession: (id: string) => void;
  onSelectPlan: (sessionId: string, planId: string) => void;
  onCreateSession: () => void;
}

const formatAgo = (date: Date) => {
  const diff = Date.now() - new Date(date).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(diff / 3600000);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
};

const MODES: Array<{ id: EntryMode; label: string }> = [
  { id: 'chat', label: 'Chat' },
  { id: 'agent', label: 'Agent' },
  { id: 'plan', label: 'Plan' },
];

const statusDotClass = (status: Session['status']) => {
  if (status === 'executing' || status === 'planning') return 'running';
  if (status === 'completed') return 'completed';
  if (status === 'failed') return 'failed';
  if (status === 'reviewing') return 'reviewing';
  return '';
};

export function SessionList({
  sessions,
  currentSessionId,
  currentPlanId,
  agents,
  onSelectSession,
  onSelectPlan,
  onCreateSession,
}: SessionListProps) {
  const [query, setQuery] = useState('');
  const [modeFilter, setModeFilter] = useState<EntryMode>('plan');

  const counts = useMemo(() => {
    const c: Record<string, number> = { chat: 0, agent: 0, plan: 0 };
    sessions.forEach((s) => { c[s.entryMode] = (c[s.entryMode] ?? 0) + 1; });
    return c;
  }, [sessions]);

  const filtered = useMemo(() => {
    return sessions.filter((s) => {
      if (s.entryMode !== modeFilter) return false;
      if (query && !s.title.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [sessions, modeFilter, query]);

  const groups = useMemo(() => {
    const now = Date.now();
    const buckets: Record<string, Session[]> = { Today: [], Yesterday: [], Earlier: [] };
    filtered.forEach((s) => {
      const diffH = (now - new Date(s.updatedAt).getTime()) / 3600000;
      if (diffH < 12) buckets.Today.push(s);
      else if (diffH < 36) buckets.Yesterday.push(s);
      else buckets.Earlier.push(s);
    });
    return buckets;
  }, [filtered]);


  return (
    <aside className="panel">
      <div className="sidebar-head">
        <div className="brand">
          <div className="brand-mark">G</div>
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
            <span>GPTase</span>
            <span className="brand-sub">workspace</span>
          </div>
        </div>
        <button className="icon-btn" title="Settings" onClick={onCreateSession}>
          <Plus size={14} />
        </button>
      </div>

      <div className="mode-tabs" role="tablist">
        {MODES.map(({ id, label }) => (
          <button
            key={id}
            role="tab"
            aria-selected={modeFilter === id}
            className="mode-tab"
            onClick={() => setModeFilter(id)}
          >
            {label}
            <span className="count">{counts[id] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-actions">
        <label className="search-box">
          <Search size={13} />
          <input
            placeholder="Search sessions…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <button className="btn-new" onClick={onCreateSession}>
          <Plus size={13} />
          New
        </button>
      </div>

      <div className="session-list">
        {Object.entries(groups).map(([label, items]) =>
          items.length === 0 ? null : (
            <div key={label}>
              <div className="session-group-label">{label}</div>
              {items.map((s) => {
                const agent = agents.find((a) => a.id === s.selectedAgent);
                const active = s.id === currentSessionId;
                return (
                  <div key={s.id}>
                    <button
                      className="session-card"
                      aria-selected={active}
                      onClick={() => onSelectSession(s.id)}
                    >
                      <div className="session-top">
                        <span className={`session-mode-pill mode-${s.entryMode}`}>
                          {s.entryMode}
                        </span>
                        <span className={`session-status-dot ${statusDotClass(s.status)}`} />
                        <span className="session-title" style={{ flex: 1 }}>{s.title}</span>
                      </div>
                      <div className="session-meta">
                        <span className="agent">{agent?.name ?? s.selectedAgent}</span>
                        <span className="dot">·</span>
                        <span>{formatAgo(s.updatedAt)}</span>
                        <span className="dot">·</span>
                        <span>{s.messages.length} msg</span>
                      </div>
                    </button>
                    {active && s.entryMode === 'plan' && s.planHistory.length > 0 && (
                      <div className="plan-nest">
                        {s.planHistory.map((plan, i) => (
                          <button
                            key={plan.id}
                            aria-selected={currentPlanId === plan.id}
                            onClick={() => onSelectPlan(s.id, plan.id)}
                          >
                            <span>
                              <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginRight: 6 }}>
                                {String(i + 1).padStart(2, '0')}
                              </span>
                              {plan.id}
                            </span>
                            <span className="run-id">{plan.steps.length} tasks</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ),
        )}
        {filtered.length === 0 && (
          <div className="empty">
            <h4>No {modeFilter} sessions</h4>
            <p>Create a new session to get started.</p>
          </div>
        )}
      </div>

      <div className="sidebar-foot">
        <a href="/workspace">
          <LayoutGrid size={12} />
          Workspace explorer
        </a>
        <a href="https://github.com/l1zp/GPTase" target="_blank" rel="noreferrer">
          <ExternalLink size={12} />
          Docs
        </a>
      </div>
    </aside>
  );
}
