import { Send, Sparkles, Terminal } from 'lucide-react';
import { useLayoutEffect, useRef, useState } from 'react';

import type { Agent, ApiWorkspacePlan, EntryMode, Session } from '../types';
import { AgentSelector } from './AgentSelector';
import { PlanReview } from './PlanReview';

interface MainWorkspaceProps {
  session: Session;
  selectedPlanId: string | null;
  agents: Agent[];
  availablePlans: ApiWorkspacePlan[];
  onSendMessage: (content: string) => void;
  onSelectEntryMode: (mode: EntryMode) => void;
  onSelectAgent: (agentId: string) => void;
  onSelectPlanTemplate: (planId: string) => void;
  onApprovePlan: () => void;
  onRejectPlan: () => void;
  onRevisePlan: () => void;
  loading?: boolean;
}

export function MainWorkspace({
  session,
  selectedPlanId,
  agents,
  availablePlans,
  onSendMessage,
  onSelectEntryMode,
  onSelectAgent,
  onSelectPlanTemplate,
  onApprovePlan,
  onRejectPlan,
  onRevisePlan,
  loading = false,
}: MainWorkspaceProps) {
  const [input, setInput] = useState('');
  const threadViewportRef = useRef<HTMLDivElement | null>(null);
  const activePlan =
    (selectedPlanId
      ? session.planHistory.find((plan) => plan.id === selectedPlanId)
      : undefined) ?? session.plan;

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

  const showPlanReview = activePlan?.status === 'draft';
  const completedSteps = activePlan?.steps.filter((step) => step.status === 'completed').length ?? 0;
  const runningSteps = activePlan?.steps.filter((step) => step.status === 'running').length ?? 0;
  const totalSteps = activePlan?.steps.length ?? 0;
  const visibleMessages = selectedPlanId
    ? session.messages.filter(
        (message) => !message.metadata?.planId || message.metadata.planId === selectedPlanId,
      )
    : session.messages;
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
    { id: 'plan', label: 'Plan', hint: '运行预定义工作流' },
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
    selectedPlanId,
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
          <p>
            Session ID: {session.id}
            {selectedPlanId ? ` · Plan: ${selectedPlanId}` : ''}
          </p>
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
          {session.entryMode === 'plan' && (
            <div className="plan-template-picker">
              <label className="plan-template-label" htmlFor="plan-template-select">
                预定义 Plan
              </label>
              <select
                id="plan-template-select"
                className="plan-template-select"
                value={session.selectedPlanTemplateId ?? availablePlans[0]?.plan_id ?? ''}
                onChange={(event) => onSelectPlanTemplate(event.target.value)}
              >
                {availablePlans.map((plan) => (
                  <option key={plan.plan_id} value={plan.plan_id}>
                    {plan.name ?? plan.plan_id}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        {session.entryMode !== 'chat' && (
          <div className="workspace-summary">
            <div className="summary-card">
              <div className="summary-label">Session 状态</div>
              <div className={`summary-value tone-${session.status === 'completed' ? 'green' : session.status === 'failed' ? 'red' : session.status === 'executing' ? 'indigo' : session.status === 'reviewing' ? 'amber' : 'muted'}`}>
                {statusLabelMap[session.status]}
              </div>
            </div>
            <div className="summary-card">
              <div className="summary-label">当前计划</div>
              <div className="summary-value">{activePlan?.id ?? '暂无计划'}</div>
            </div>
            {session.entryMode === 'plan' && (
              <div className="summary-card">
                <div className="summary-label">步骤进度</div>
                <div className="summary-value">
                  {totalSteps > 0 ? `${completedSteps}/${totalSteps}` : '0/0'}
                </div>
                {runningSteps > 0 && <div className="summary-subtle">有 {runningSteps} 个步骤正在执行</div>}
              </div>
            )}
          </div>
        )}
      </header>

      <section className="workspace-body" ref={threadViewportRef}>
        {visibleMessages.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-mark">
              <Sparkles size={28} />
            </div>
            <h3>提交任务</h3>
            <p>
              Chat 入口使用默认 chat agent，Agent 入口直接运行 Worker，Plan 入口执行预定义工作流。
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

            {showPlanReview && activePlan && (
              <PlanReview
                plan={activePlan}
                onApprove={onApprovePlan}
                onReject={onRejectPlan}
                onRevise={onRevisePlan}
              />
            )}
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
                  : session.entryMode === 'agent'
                    ? '描述要交给当前 Worker 的具体任务...'
                    : '描述这次 Plan 运行的输入内容...'
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
