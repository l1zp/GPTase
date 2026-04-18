import { ExternalLink, MoreHorizontal, Send } from 'lucide-react';
import { useLayoutEffect, useMemo, useRef, useState } from 'react';

import type { Agent, ApiWorkspacePlan, EntryMode, Message, Session } from '../types';
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

const statusLabel: Record<Session['status'], string> = {
  draft: 'Draft',
  planning: 'Planning',
  reviewing: 'Awaiting review',
  executing: 'Executing',
  completed: 'Completed',
  failed: 'Failed',
};

function WorkspaceHeader({ session }: { session: Session }) {
  const progress = session.plan
    ? { done: session.plan.steps.filter((s) => s.status === 'completed').length, total: session.plan.steps.length }
    : null;

  return (
    <header className="workspace-header">
      <div className="ws-title-block">
        <span className="ws-title">{session.title}</span>
        <span className="ws-id">{session.id}</span>
        <span className={`status-chip ${session.status}`}>
          <span className="dot" />
          {statusLabel[session.status]}
          {progress && progress.total > 0 && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, marginLeft: 4, opacity: 0.75 }}>
              {progress.done}/{progress.total}
            </span>
          )}
        </span>
      </div>
      <div className="ws-header-actions">
        <button className="icon-btn" title="Open in explorer" onClick={() => { window.location.href = '/workspace'; }}>
          <ExternalLink size={13} />
        </button>
        <button className="icon-btn" title="More">
          <MoreHorizontal size={13} />
        </button>
      </div>
    </header>
  );
}

function TurnMessage({ msg }: { msg: Message }) {
  const roleClass = msg.role === 'user' ? 'turn-user' : msg.role === 'agent' ? 'turn-agent' : msg.role === 'tool' ? 'turn-tool' : 'turn-system';
  const roleName = msg.role === 'user' ? 'You' : msg.role === 'agent' ? 'Agent' : msg.role === 'tool' ? 'Tool' : 'System';
  const time = new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const metaChips: string[] = [];
  if (msg.metadata?.label) metaChips.push(msg.metadata.label);
  if (msg.metadata?.toolName) metaChips.push(msg.metadata.toolName);

  return (
    <article className={`turn ${roleClass}`}>
      <div className="turn-main">
        <header className="turn-head">
          <span className="turn-role">{roleName}</span>
          <time className="turn-time">{time}</time>
        </header>
        <div className="turn-body">{msg.content}</div>
        {metaChips.length > 0 && (
          <div className="turn-meta">
            {metaChips.map((chip) => (
              <span key={chip} className="turn-meta-chip">{chip}</span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
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

  const showPlanReview = activePlan?.status === 'draft';
  const visibleMessages = selectedPlanId
    ? session.messages.filter(
        (msg) => !msg.metadata?.planId || msg.metadata.planId === selectedPlanId,
      )
    : session.messages;
  const lastMsg = visibleMessages[visibleMessages.length - 1];

  useLayoutEffect(() => {
    const vp = threadViewportRef.current;
    if (!vp) return;
    const scroll = () => { vp.scrollTop = vp.scrollHeight; };
    scroll();
    const id = window.requestAnimationFrame(scroll);
    return () => window.cancelAnimationFrame(id);
  }, [session.id, selectedPlanId, visibleMessages.length, lastMsg?.id, lastMsg?.content, loading]);

  const handleSend = () => {
    if (!input.trim()) return;
    onSendMessage(input);
    setInput('');
  };

  const workerAgents = useMemo(
    () => agents.filter((a) => a.id !== 'orchestrator' && a.id !== 'chat'),
    [agents],
  );

  const placeholder =
    session.entryMode === 'chat'
      ? 'Ask anything about the paper, the schema, or prior runs…'
      : session.entryMode === 'agent'
        ? 'Describe the task — the agent decides how to run it.'
        : 'Describe a goal — the planner drafts steps for your review before executing.';

  return (
    <section className="panel workspace">
      <WorkspaceHeader session={session} />

      <div className="thread" ref={threadViewportRef}>
        {visibleMessages.length === 0 && !showPlanReview ? (
          <div className="empty">
            <h4>
              {session.entryMode === 'chat'
                ? 'Start a conversation'
                : session.entryMode === 'agent'
                  ? 'Describe a task for the agent'
                  : 'Submit a goal to generate a plan'}
            </h4>
            <p>{placeholder}</p>
          </div>
        ) : (
          <div className="thread-inner">
            {visibleMessages.map((msg) => (
              <TurnMessage key={msg.id} msg={msg} />
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
      </div>

      <div className="composer">
        <div className="composer-modes">
          {(['chat', 'agent', 'plan'] as EntryMode[]).map((mode) => (
            <button
              key={mode}
              className="mode-chip"
              aria-selected={session.entryMode === mode}
              onClick={() => onSelectEntryMode(mode)}
            >
              {mode === 'chat' ? 'Chat' : mode === 'agent' ? 'Agent' : 'Plan'}
            </button>
          ))}
          <div className="mode-side-config">
            {session.entryMode === 'agent' && workerAgents.length > 0 && (
              <>
                <span>Agent</span>
                <select
                  value={session.selectedAgent}
                  onChange={(e) => onSelectAgent(e.target.value)}
                >
                  {workerAgents.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </>
            )}
            {session.entryMode === 'plan' && availablePlans.length > 0 && (
              <>
                <span>Plan</span>
                <select
                  value={session.selectedPlanTemplateId ?? availablePlans[0]?.plan_id ?? ''}
                  onChange={(e) => onSelectPlanTemplate(e.target.value)}
                >
                  {availablePlans.map((p) => (
                    <option key={p.plan_id} value={p.plan_id}>{p.name ?? p.plan_id}</option>
                  ))}
                </select>
              </>
            )}
          </div>
        </div>

        <div className="composer-input-wrap">
          <textarea
            rows={3}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleSend(); } }}
            placeholder={placeholder}
          />
          <button
            className="btn btn-primary"
            onClick={handleSend}
            disabled={!input.trim() || loading}
          >
            <Send size={13} />
            {session.entryMode === 'plan' ? 'Submit' : 'Send'}
          </button>
        </div>

        <div className="composer-hint">
          <kbd>⌘</kbd><kbd>↵</kbd>
          <span>to send</span>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)' }}>
            {visibleMessages.length} msg
          </span>
        </div>
      </div>
    </section>
  );
}
