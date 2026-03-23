import { Send, Sparkles, Terminal, Zap } from 'lucide-react';
import { useState } from 'react';

import type { Agent, Session } from '../types';
import { AgentSelector } from './AgentSelector';
import { PlanReview } from './PlanReview';

interface MainWorkspaceProps {
  session: Session;
  selectedPlanId: string | null;
  agents: Agent[];
  onSendMessage: (content: string) => void;
  onSelectAgent: (agentId: string) => void;
  onApprovePlan: () => void;
  onRejectPlan: () => void;
  onRevisePlan: () => void;
  loading?: boolean;
}

export function MainWorkspace({
  session,
  selectedPlanId,
  agents,
  onSendMessage,
  onSelectAgent,
  onApprovePlan,
  onRejectPlan,
  onRevisePlan,
  loading = false,
}: MainWorkspaceProps) {
  const [input, setInput] = useState('');
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
  const statusLabelMap = {
    draft: '草稿',
    planning: '规划中',
    reviewing: '待审核',
    executing: '执行中',
    completed: '已完成',
    failed: '失败',
  } as const;

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
        <div className="workspace-selector">
          <AgentSelector
            agents={agents}
            selectedAgentId={session.selectedAgent}
            onSelectAgent={onSelectAgent}
          />
        </div>
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
          <div className="summary-card">
            <div className="summary-label">步骤进度</div>
            <div className="summary-value">
              {totalSteps > 0 ? `${completedSteps}/${totalSteps}` : '0/0'}
            </div>
            {runningSteps > 0 && <div className="summary-subtle">有 {runningSteps} 个步骤正在执行</div>}
          </div>
        </div>
      </header>

      <section className="workspace-body">
        {visibleMessages.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-mark">
              <Sparkles size={28} />
            </div>
            <h3>开始新任务</h3>
            <p>描述你的目标，GPTase 会生成 draft plan 并协调多个智能体执行。</p>
            <div className="example-list">
              <div className="example-card">
                <Terminal size={18} />
                <div>
                  <div className="example-title">示例 1</div>
                  <div className="example-copy">分析蛋白质序列的同源性并预测功能域</div>
                </div>
              </div>
              <div className="example-card">
                <Zap size={18} />
                <div>
                  <div className="example-title">示例 2</div>
                  <div className="example-copy">生成近期关于 CRISPR 技术的文献综述</div>
                </div>
              </div>
            </div>
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
          </div>
        )}
      </section>

      <footer className="composer">
        <div className="composer-inner">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="描述您的任务目标... (Enter 发送，Shift+Enter 换行)"
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
        <div className="composer-hints">
          <span>自动生成执行计划</span>
          <span>支持多智能体协作</span>
          <span>保留完整执行追踪</span>
        </div>
      </footer>
    </main>
  );
}
