import { AlertCircle, CheckCircle2, Clock, Loader2, Plus, Search } from 'lucide-react';
import { useState } from 'react';

import type { Agent, EntryMode, Session } from '../types';

interface SessionListProps {
  sessions: Session[];
  currentSessionId: string;
  activeMode: EntryMode;
  agents: Agent[];
  onSelectSession: (id: string) => void;
  onCreateSession: () => void;
}

const statusConfig = {
  draft: { icon: Clock, label: '草稿', tone: 'muted' },
  planning: { icon: Loader2, label: '规划中', tone: 'blue' },
  reviewing: { icon: AlertCircle, label: '待审核', tone: 'amber' },
  executing: { icon: Loader2, label: '执行中', tone: 'indigo' },
  completed: { icon: CheckCircle2, label: '已完成', tone: 'green' },
  failed: { icon: AlertCircle, label: '失败', tone: 'red' },
} as const;

const entryModeLabel = {
  chat: 'Chat',
  agent: 'Agent',
} as const;

const formatTime = (date: Date) => {
  const diff = Date.now() - new Date(date).getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  if (hours < 24) return `${hours}小时前`;
  return `${days}天前`;
};

export function SessionList({
  sessions,
  currentSessionId,
  activeMode,
  agents,
  onSelectSession,
  onCreateSession,
}: SessionListProps) {
  const [search, setSearch] = useState('');
  const modeSessions = sessions.filter((session) => session.entryMode === activeMode);
  const filteredSessions = search.trim()
    ? modeSessions.filter((session) => session.title.toLowerCase().includes(search.toLowerCase()))
    : modeSessions;

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <div>
            <div className="sidebar-title">GPTase</div>
            <div className="sidebar-subtitle">Harness Workspace</div>
          </div>
        </div>
        <button className="primary-button" onClick={onCreateSession}>
          <Plus size={16} />
          新建会话
        </button>
      </div>

      <div className="search-wrap">
        <Search className="search-icon" size={15} />
        <input
          className="search-input"
          type="text"
          placeholder={`搜索${entryModeLabel[activeMode]}会话...`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="session-list">
        {filteredSessions.map((session) => {
          const status = statusConfig[session.status];
          const StatusIcon = status.icon;
          const agent = agents.find((item) => item.id === session.selectedAgent);
          const active = session.id === currentSessionId;
          const modeLabel = entryModeLabel[session.entryMode];
          const modeDetail =
            session.entryMode === 'agent' ? agent?.name ?? 'Worker' : 'chat';

          return (
            <button
              key={session.id}
              className={`session-card ${active ? 'is-active' : ''}`}
              onClick={() => onSelectSession(session.id)}
            >
              <div className="session-card-top">
                <StatusIcon
                  size={16}
                  className={`status-icon tone-${status.tone} ${
                    session.status === 'executing' || session.status === 'planning'
                      ? 'is-spinning'
                      : ''
                  }`}
                />
                <div className="session-card-copy">
                  <div className="session-card-title">{session.title}</div>
                  <div className="session-card-status">{status.label}</div>
                </div>
              </div>
              <div className="session-card-meta">
                <span>{modeLabel}</span>
                <span>{modeDetail}</span>
                <span>{formatTime(session.updatedAt)}</span>
              </div>
            </button>
          );
        })}
      </div>

      <div className="sidebar-stats">
        <div>
          <div className="stat-value">{modeSessions.length}</div>
          <div className="stat-label">当前模式</div>
        </div>
        <div>
          <div className="stat-value tone-indigo">
            {modeSessions.filter((session) => session.status === 'executing').length}
          </div>
          <div className="stat-label">执行中</div>
        </div>
        <div>
          <div className="stat-value tone-green">
            {modeSessions.filter((session) => session.status === 'completed').length}
          </div>
          <div className="stat-label">已完成</div>
        </div>
      </div>
    </aside>
  );
}
