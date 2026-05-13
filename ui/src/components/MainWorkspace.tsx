import { Send, Sparkles, Terminal } from 'lucide-react';
import { useLayoutEffect, useRef, useState } from 'react';

import type { Agent, EntryMode, Session } from '../types';
import { AgentSelector } from './AgentSelector';

interface MainWorkspaceProps {
  session: Session;
  agents: Agent[];
  onSendMessage: (content: string) => void;
  onSelectEntryMode: (mode: EntryMode) => void;
  onSelectAgent: (agentId: string) => void;
  loading?: boolean;
}

export function MainWorkspace({
  session,
  agents,
  onSendMessage,
  onSelectEntryMode,
  onSelectAgent,
  loading = false,
}: MainWorkspaceProps) {
  const [input, setInput] = useState('');
  const threadViewportRef = useRef<HTMLDivElement | null>(null);

  const handleSend = () => {
    if (!input.trim()) {
      return;
    }
    onSendMessage(input);
    setInput('');
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const visibleMessages = session.messages;
  const lastVisibleMessage = visibleMessages[visibleMessages.length - 1];
  const statusLabelMap = {
    draft: '草稿',
    planning: '规划中',
    reviewing: '待审核',
    executing: '执行中',
    completed: '已完成',
    failed: '失败',
  } as const;
  const entryModes: Array<{ id: EntryMode; label: string; hint: string }> = [
    { id: 'chat', label: 'Chat', hint: '使用默认 chat agent 直接对话' },
    { id: 'agent', label: 'Agent', hint: '直接运行 Worker' },
  ];

  useLayoutEffect(() => {
    const viewport = threadViewportRef.current;
    if (!viewport) {
      return;
    }

    const scrollToBottom = () => {
      viewport.scrollTop = viewport.scrollHeight;
    };

    scrollToBottom();
    const frameId = window.requestAnimationFrame(scrollToBottom);
    return () => window.cancelAnimationFrame(frameId);
  }, [
    session.id,
    visibleMessages.length,
    lastVisibleMessage?.id,
    lastVisibleMessage?.content,
    lastVisibleMessage?.timestamp,
    loading,
  ]);

  return (
    <main className="workspace">
      <header className="workspace-header">
        <div>
          <h1>{session.title}</h1>
          <p>Session ID: {session.id}</p>
        </div>
        <div className="workspace-count">{visibleMessages.length} 条消息</div>
        <div className="workspace-selector-stack">
          <div className="entry-mode-switch">
            {entryModes.map((mode) => (
              <button
                key={mode.id}
                className={`entry-mode-chip ${session.entryMode === mode.id ? 'is-active' : ''}`}
                onClick={() => onSelectEntryMode(mode.id)}
              >
                <span>{mode.label}</span>
                <small>{mode.hint}</small>
              </button>
            ))}
          </div>
          {session.entryMode === 'agent' && (
            <div className="workspace-selector">
              <AgentSelector
                agents={agents.filter((agent) => agent.id !== 'orchestrator' && agent.id !== 'chat')}
                selectedAgentId={session.selectedAgent}
                onSelectAgent={onSelectAgent}
              />
            </div>
          )}
        </div>
        <div className="workspace-summary">
          <div className="summary-card">
            <div className="summary-label">Session 状态</div>
            <div className={`summary-value tone-${session.status === 'completed' ? 'green' : session.status === 'failed' ? 'red' : session.status === 'executing' ? 'indigo' : session.status === 'reviewing' ? 'amber' : 'muted'}`}>
              {statusLabelMap[session.status]}
            </div>
          </div>
        </div>
      </header>

      <section className="workspace-body" ref={threadViewportRef}>
        {visibleMessages.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-mark">
              <Sparkles size={28} />
            </div>
            <h3>提交任务</h3>
            <p>
              Chat 入口使用默认 chat agent，Agent 入口直接运行 Worker。
            </p>
          </div>
        ) : (
          <div className="message-thread">
            {visibleMessages.map((message) => (
              <div
                key={message.id}
                className={`message-row ${message.role === 'user' ? 'is-user' : ''}`}
              >
                {message.role !== 'user' && (
                  <div className="message-avatar">
                    {message.role === 'agent' ? <Sparkles size={15} /> : <Terminal size={15} />}
                  </div>
                )}
                <div className={`message-card ${message.role === 'user' ? 'is-user' : ''}`}>
                  {message.metadata?.label && (
                    <div className={`message-badge badge-${message.metadata.tone ?? 'slate'}`}>
                      {message.metadata.label}
                    </div>
                  )}
                  <div className="message-role">
                    {message.role === 'user' && '用户'}
                    {message.role === 'agent' && '智能体'}
                    {message.role === 'system' && '系统'}
                    {message.role === 'tool' && '工具'}
                  </div>
                  <div className="message-content">{message.content}</div>
                  {message.metadata?.taskId && (
                    <div className="message-meta-inline">Task: {message.metadata.taskId}</div>
                  )}
                  <div className="message-time">
                    {new Date(message.timestamp).toLocaleString('zh-CN')}
                  </div>
                </div>
              </div>
            ))}
            <div className="message-thread-end" aria-hidden="true" />
          </div>
        )}
      </section>

      <footer className="composer">
        <div className="composer-inner">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                session.entryMode === 'chat'
                  ? '输入普通对话或任务请求，交给 chat agent 直接处理...'
                  : '描述要交给当前 Worker 的具体任务...'
              }
              className="composer-input"
            />
          <button
            className="primary-button composer-send"
            onClick={handleSend}
            disabled={!input.trim() || loading}
          >
            <Send size={16} />
            {loading ? '处理中' : '发送'}
          </button>
        </div>
      </footer>
    </main>
  );
}
