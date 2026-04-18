import {
  Activity,
  BarChart3,
  Bot,
  CheckCircle2,
  Circle,
  Database,
  Loader2,
  Play,
  Wrench,
  XCircle,
} from 'lucide-react';
import { useMemo, useState } from 'react';

import type { EvalMetric, ExecutionTrace, Session } from '../types';

interface DetailPanelProps {
  session: Session;
  evalMetrics: EvalMetric[];
}

type TabType = 'plan' | 'traces' | 'memory' | 'eval';

const formatDuration = (ms?: number) => {
  if (!ms || ms <= 0) return null;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)}s`;
};

const stepIcon = (status: string) => {
  if (status === 'completed') return <CheckCircle2 size={14} />;
  if (status === 'running') return <Loader2 size={14} className="spin" />;
  if (status === 'failed') return <XCircle size={14} />;
  return <Circle size={14} />;
};

const traceKindIcon = (kind: ExecutionTrace['kind']) => {
  if (kind === 'llm_call') return <Bot size={12} />;
  if (kind === 'tool_call') return <Wrench size={12} />;
  if (kind === 'sdk_run') return <Play size={12} />;
  return <Activity size={12} />;
};

function PlanPane({
  plan,
  selectedStep,
  onSelectStep,
}: {
  plan: NonNullable<Session['plan']>;
  selectedStep: string | null;
  onSelectStep: (id: string) => void;
}) {
  const done = plan.steps.filter((s) => s.status === 'completed').length;
  const pct = plan.steps.length > 0 ? Math.round((done / plan.steps.length) * 100) : 0;

  return (
    <>
      <div className="plan-summary">
        <div className="kicker">Goal</div>
        <div className="goal">{plan.goal}</div>
        <div className="plan-progress">
          <div className="plan-progress-row">
            <span>{done}/{plan.steps.length} steps</span>
            <span>{pct}%</span>
          </div>
          <div className="plan-progress-bar">
            <div className="plan-progress-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
      <div className="plan-steps-list">
        {plan.steps.map((step, i) => (
          <div
            key={step.id}
            className="plan-step"
            aria-selected={selectedStep === step.id}
            onClick={() => onSelectStep(selectedStep === step.id ? '' : step.id)}
          >
            <div className={`step-icon ${step.status}`}>{stepIcon(step.status)}</div>
            <div className="step-content">
              <div className="title">
                <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10.5, marginRight: 6 }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                {step.title}
              </div>
              {step.description && <div className="desc">{step.description}</div>}
              {step.assignedAgent && <span className="agent">{step.assignedAgent}</span>}
            </div>
            {(step.startTime || step.endTime) && (
              <div className="step-duration">
                {step.endTime && step.startTime
                  ? formatDuration(step.endTime.getTime() - step.startTime.getTime()) ?? '—'
                  : '…'}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

function TracesPane({
  traces,
  plan,
  stepFilter,
  setStepFilter,
}: {
  traces: ExecutionTrace[];
  plan: Session['plan'] | undefined;
  stepFilter: string | null;
  setStepFilter: (id: string | null) => void;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number>(-1);
  const [typeFilter, setTypeFilter] = useState('all');

  const filtered = useMemo(() => {
    return traces.filter((t) => {
      if (typeFilter !== 'all' && t.kind !== typeFilter) return false;
      if (stepFilter && t.stepId !== stepFilter) return false;
      return true;
    });
  }, [traces, typeFilter, stepFilter]);

  return (
    <>
      <div className="trace-filter-bar">
        <span className="label">Type</span>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="all">all</option>
          <option value="llm_call">llm_call</option>
          <option value="tool_call">tool_call</option>
          <option value="sdk_run">sdk_run</option>
        </select>
        {plan && (
          <>
            <span className="label">Step</span>
            <select value={stepFilter ?? ''} onChange={(e) => setStepFilter(e.target.value || null)}>
              <option value="">all</option>
              {plan.steps.map((s, i) => (
                <option key={s.id} value={s.id}>{String(i + 1).padStart(2, '0')} · {s.title.slice(0, 28)}</option>
              ))}
            </select>
          </>
        )}
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--text-tertiary)' }}>
          {filtered.length}/{traces.length}
        </span>
        {(stepFilter || typeFilter !== 'all') && (
          <button
            className="btn-ghost"
            style={{ padding: '2px 6px', fontSize: 11, border: 0 }}
            onClick={() => { setStepFilter(null); setTypeFilter('all'); }}
          >
            clear
          </button>
        )}
      </div>
      <div className="trace-list">
        {filtered.length === 0 ? (
          <div className="empty">
            <h4>No matching traces</h4>
            <p>Adjust type or step filter to see events.</p>
          </div>
        ) : (
          filtered.map((row, i) => {
            const expanded = expandedIdx === i;
            const dur = formatDuration(row.meta.durationMs);
            return (
              <div key={row.id}>
                <div
                  className="trace-row"
                  aria-expanded={expanded}
                  onClick={() => setExpandedIdx(expanded ? -1 : i)}
                >
                  <span className="trace-time">
                    {new Date(row.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  <span className={`trace-kind ${row.kind}`}>{traceKindIcon(row.kind)}</span>
                  <span className="trace-type">{row.kind.replace('_', '·')}</span>
                  <span className="trace-summary">
                    {row.kind === 'tool_call' ? <code>{row.summary || row.meta.toolName}</code> : (row.summary || row.message)}
                  </span>
                  <span className="trace-duration">{dur ?? '—'}</span>
                </div>
                {expanded && (
                  <div className="trace-expanded">
                    <div className="grid">
                      {row.meta.toolName && (
                        <div className="trace-kv"><span className="k">tool</span><span className="v">{row.meta.toolName}</span></div>
                      )}
                      {row.meta.iteration != null && (
                        <div className="trace-kv"><span className="k">iteration</span><span className="v">{row.meta.iteration}</span></div>
                      )}
                      {row.meta.inputTokens != null && (
                        <div className="trace-kv"><span className="k">in_tokens</span><span className="v">{row.meta.inputTokens}</span></div>
                      )}
                      {row.meta.outputTokens != null && (
                        <div className="trace-kv"><span className="k">out_tokens</span><span className="v">{row.meta.outputTokens}</span></div>
                      )}
                      {dur && (
                        <div className="trace-kv"><span className="k">duration</span><span className="v">{dur}</span></div>
                      )}
                    </div>
                    {row.rawDetails && Object.keys(row.rawDetails).length > 0 && (
                      <pre className="trace-raw">{JSON.stringify(row.rawDetails, null, 2)}</pre>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </>
  );
}

function MemoryPane({
  memory,
  stepFilter,
}: {
  memory: Session['memory'];
  stepFilter: string | null;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const filtered = stepFilter
    ? memory.filter((m) => (m as { stepId?: string }).stepId === stepFilter)
    : memory;

  if (filtered.length === 0) {
    return (
      <div className="empty">
        <h4>{stepFilter ? 'No memory entries for this step' : 'No working memory'}</h4>
        {stepFilter && <p>Clear the step filter to see all keys.</p>}
      </div>
    );
  }

  return (
    <div>
      {filtered.map((m, i) => {
        const id = `${m.key}-${i}`;
        const long = m.value.length > 180;
        const open = expanded[id];
        return (
          <div key={id} className="memory-item">
            <div className="memory-head-row">
              <span className="memory-key">{m.key}</span>
              <span className="memory-source">{m.source}</span>
            </div>
            <div className={`memory-value ${long && !open ? 'truncated' : ''}`}>
              {m.value}
            </div>
            {long && (
              <button
                className="memory-expand"
                onClick={() => setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))}
              >
                {open ? 'Collapse' : 'Expand'}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

function EvalPane({ metrics }: { metrics: EvalMetric[] }) {
  if (metrics.length === 0) {
    return (
      <div className="empty">
        <h4>No eval metrics</h4>
        <p>Run a session to see evaluation data.</p>
      </div>
    );
  }
  return (
    <div className="eval-grid">
      {metrics.map((m) => (
        <div key={m.name} className="eval-card">
          <div className="k">{m.name}</div>
          <div className="v">
            {m.value}
            <small>{m.unit}</small>
          </div>
        </div>
      ))}
    </div>
  );
}

const DETAIL_TABS: Array<{ id: TabType; label: string; Icon: React.ElementType }> = [
  { id: 'plan', label: 'Plan', Icon: Activity },
  { id: 'traces', label: 'Traces', Icon: Wrench },
  { id: 'memory', label: 'Memory', Icon: Database },
  { id: 'eval', label: 'Eval', Icon: BarChart3 },
];

export function DetailPanel({ session, evalMetrics }: DetailPanelProps) {
  const [tab, setTab] = useState<TabType>('plan');
  const [selectedStep, setSelectedStep] = useState<string | null>(null);

  return (
    <aside className="panel">
      <header className="detail-head">
        <div className="detail-tabs" role="tablist">
          {DETAIL_TABS.map(({ id, label, Icon }) => {
            const count = id === 'plan' ? session.plan?.steps.length : id === 'traces' ? session.traces.length : id === 'memory' ? session.memory.length : undefined;
            return (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                className="detail-tab"
                onClick={() => setTab(id)}
              >
                <Icon size={12} />
                {label}
                {count != null && <span className="count">{count}</span>}
              </button>
            );
          })}
        </div>
      </header>

      <div className="detail-body">
        {tab === 'plan' && (
          session.plan ? (
            <PlanPane
              plan={session.plan}
              selectedStep={selectedStep}
              onSelectStep={(id) => setSelectedStep(id || null)}
            />
          ) : (
            <div className="empty">
              <h4>No active plan</h4>
              <p>Submit a Plan-mode task to see the execution steps here.</p>
            </div>
          )
        )}
        {tab === 'traces' && (
          <TracesPane
            traces={session.traces}
            plan={session.plan}
            stepFilter={selectedStep}
            setStepFilter={setSelectedStep}
          />
        )}
        {tab === 'memory' && (
          <MemoryPane memory={session.memory} stepFilter={selectedStep} />
        )}
        {tab === 'eval' && <EvalPane metrics={evalMetrics} />}
      </div>
    </aside>
  );
}
