import { AlertCircle, CheckCircle2, Clock, Loader2, Plus, Search } from 'lucide-react';
import { useState } from 'react';

import type { Agent, Session } from '../types';

interface SessionListProps {
  sessions: Session[];
  currentSessionId: string;
  currentPlanId: string | null;
  agents: Agent[];
  onSelectSession: (id: string) => void;
  onSelectPlan: (sessionId: string, planId: string) => void;
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
  currentPlanId,
  agents,
  onSelectSession,
  onSelectPlan,
  onCreateSession,
}: SessionListProps) {
  const [search, setSearch] = useState('');
  const filteredSessions = search.trim()
    ? sessions.filter((s) => s.title.toLowerCase().includes(search.toLowerCase()))
    : sessions;

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <div>
            <div className="sidebar-title">GPTase</div>
            <div className="sidebar-subtitle">Agent Workspace</div>
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
          placeholder="搜索会话..."
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

          return (
            <div key={session.id}>
              <button
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
                  <span>{agent?.name ?? '未选择智能体'}</span>
                  <span>{formatTime(session.updatedAt)}</span>
                </div>
              </button>
              {active && session.planHistory.length > 0 && (
                <div className="plan-nav">
                  <button
                    className={`plan-nav-item ${currentPlanId === null ? 'is-active' : ''}`}
                    onClick={() => onSelectSession(session.id)}
                  >
                    <span className="plan-nav-name">会话总览</span>
                    <span className="plan-nav-meta">{session.messages.length} 条消息</span>
                  </button>
                  {session.planHistory.map((plan) => (
                    <button
                      key={plan.id}
                      className={`plan-nav-item ${currentPlanId === plan.id ? 'is-active' : ''}`}
                      onClick={() => onSelectPlan(session.id, plan.id)}
                    >
                      <span className="plan-nav-name">{plan.id}</span>
                      <span className="plan-nav-meta">{plan.steps.length} 个任务</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="sidebar-stats">
        <div>
          <div className="stat-value">{sessions.length}</div>
          <div className="stat-label">总会话</div>
        </div>
        <div>
          <div className="stat-value tone-indigo">
            {sessions.filter((session) => session.status === 'executing').length}
          </div>
          <div className="stat-label">执行中</div>
        </div>
        <div>
          <div className="stat-value tone-green">
            {sessions.filter((session) => session.status === 'completed').length}
          </div>
          <div className="stat-label">已完成</div>
        </div>
      </div>

      <div className="sidebar-nav-footer">
        <a className="sidebar-nav-link" href="/workspace">
          抽取结果可视化
        </a>
      </div>
    </aside>
  );
}
