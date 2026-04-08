import {
  Activity,
  BarChart3,
  CheckCircle2,
  Circle,
  Clock,
  Database,
  ChevronDown,
  Loader2,
  Wrench,
  Sparkles,
  Bot,
  XCircle,
} from 'lucide-react';
import { useMemo, useState } from 'react';

import type { EvalMetric, ExecutionTrace, Session } from '../types';

interface DetailPanelProps {
  session: Session;
  evalMetrics: EvalMetric[];
}

type TabType = 'plan' | 'traces' | 'memory' | 'eval';

const stepIcons = {
  pending: Circle,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  skipped: Circle,
} as const;

const stepTones = {
  pending: 'tone-muted',
  running: 'tone-indigo',
  completed: 'tone-green',
  failed: 'tone-red',
  skipped: 'tone-muted',
} as const;

const traceTones = {
  log: 'trace-log',
  success: 'trace-success',
  warning: 'trace-warning',
  error: 'trace-error',
} as const;

const traceKindIcons = {
  llm_call: Sparkles,
  tool_call: Wrench,
  sdk_run: CheckCircle2,
  system: Bot,
} as const;

const formatDuration = (durationMs?: number) => {
  if (!durationMs || durationMs <= 0) {
    return null;
  }
  if (durationMs < 1000) {
    return `${durationMs}ms`;
  }
  return `${(durationMs / 1000).toFixed(durationMs >= 10000 ? 0 : 1)}s`;
};

const formatTraceTime = (timestamp: Date) => timestamp.toLocaleTimeString('zh-CN');

const formatTraceGroupTitle = (session: Session, stepId: string) => {
  const matchedStep = session.plan?.steps.find((step) => step.id === stepId);
  if (matchedStep) {
    return matchedStep.title;
  }
  if (stepId === 'ungrouped') {
    return session.selectedAgent || '系统';
  }
  return stepId;
};

const getTraceMetaChips = (trace: ExecutionTrace) => {
  const chips: string[] = [];
  if (trace.meta.iteration) {
    chips.push(`第 ${trace.meta.iteration} 轮`);
  }
  const duration = formatDuration(trace.meta.durationMs);
  if (duration) {
    chips.push(duration);
  }
  if (trace.meta.toolName) {
    chips.push(`工具 ${trace.meta.toolName}`);
  } else if (trace.kind === 'tool_call') {
    chips.push('工具名未记录');
  }
  if (trace.meta.commandPreview) {
    chips.push(`命令 ${trace.meta.commandPreview}`);
  }
  if (trace.meta.inputTokens || trace.meta.outputTokens) {
    chips.push(`tok ${trace.meta.inputTokens ?? 0}/${trace.meta.outputTokens ?? 0}`);
  }
  if (trace.meta.messageCount) {
    chips.push(`${trace.meta.messageCount} 条消息`);
  }
  if (trace.meta.resultChars) {
    chips.push(`${trace.meta.resultChars} chars`);
  }
  return chips;
};

const getTraceDetailRows = (trace: ExecutionTrace) => {
  const rows: Array<{ label: string; value: string }> = [];
  if (trace.meta.toolName) {
    rows.push({ label: '工具', value: trace.meta.toolName });
  } else if (trace.kind === 'tool_call') {
    rows.push({ label: '工具', value: '未记录名称' });
  }
  if (trace.meta.commandPreview) {
    rows.push({ label: '命令', value: trace.meta.commandPreview });
  }
  if (trace.meta.iteration) {
    rows.push({ label: '轮次', value: String(trace.meta.iteration) });
  }
  const duration = formatDuration(trace.meta.durationMs);
  if (duration) {
    rows.push({ label: '耗时', value: duration });
  }
  if (trace.meta.messageCount) {
    rows.push({ label: '消息数', value: String(trace.meta.messageCount) });
  }
  if (trace.meta.inputTokens) {
    rows.push({ label: '输入 Tokens', value: String(trace.meta.inputTokens) });
  }
  if (trace.meta.outputTokens) {
    rows.push({ label: '输出 Tokens', value: String(trace.meta.outputTokens) });
  }
  if (trace.meta.resultChars) {
    rows.push({ label: '结果字符数', value: String(trace.meta.resultChars) });
  }
  return rows;
};

export function DetailPanel({ session, evalMetrics }: DetailPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('plan');
  const [expandedTraceIds, setExpandedTraceIds] = useState<Record<string, boolean>>({});
  const [expandedMemoryIds, setExpandedMemoryIds] = useState<Record<string, boolean>>({});
  const traceGroups = useMemo(
    () =>
      session.traces.reduce<Record<string, typeof session.traces>>((groups, trace) => {
        const key = trace.stepId || 'ungrouped';
        if (!groups[key]) {
          groups[key] = [];
        }
        groups[key].push(trace);
        return groups;
      }, {}),
    [session.traces],
  );

  const tabs = [
    { id: 'plan' as const, label: '执行计划', icon: Activity },
    { id: 'traces' as const, label: '执行追踪', icon: Clock },
    { id: 'memory' as const, label: '工作记忆', icon: Database },
    { id: 'eval' as const, label: '评估指标', icon: BarChart3 },
  ];

  const toggleTrace = (traceId: string) => {
    setExpandedTraceIds((prev) => ({
      ...prev,
      [traceId]: !prev[traceId],
    }));
  };

  const toggleMemory = (memoryId: string) => {
    setExpandedMemoryIds((prev) => ({
      ...prev,
      [memoryId]: !prev[memoryId],
    }));
  };

  const hasTraceRawDetails = (trace: ExecutionTrace) =>
    Boolean(trace.rawDetails && Object.keys(trace.rawDetails).length > 0);

  return (
    <aside className="detail-panel">
      <div className="detail-tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={`detail-tab ${activeTab === tab.id ? 'is-active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={15} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      <div className="detail-content">
        {activeTab === 'plan' && (
          <div className="detail-stack">
            {session.plan ? (
              <>
                <section className="detail-card">
                  <div className="detail-label">目标</div>
                  <div className="detail-goal">{session.plan.goal}</div>
                  <div className="progress-row">
                    <span>进度</span>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{
                          width: `${session.plan.steps.length > 0 ? (session.plan.currentStepIndex / session.plan.steps.length) * 100 : 0}%`,
                        }}
                      />
                    </div>
                    <span>
                      {session.plan.currentStepIndex}/{session.plan.steps.length}
                    </span>
                  </div>
                </section>
                {session.plan.steps.map((step, index) => {
                  const Icon = stepIcons[step.status];
                  return (
                    <section
                      key={step.id}
                      className={`detail-card ${index === session.plan?.currentStepIndex ? 'is-focused' : ''}`}
                    >
                      <div className="step-head">
                        <Icon
                          size={16}
                          className={`${stepTones[step.status]} ${
                            step.status === 'running' ? 'is-spinning' : ''
                          }`}
                        />
                        <div>
                          <div className="step-title">{step.title}</div>
                          <div className="step-desc">{step.description}</div>
                        </div>
                      </div>
                      {step.output && <div className="detail-note">{step.output}</div>}
                      {step.error && <div className="detail-error">{step.error}</div>}
                      {step.startTime && (
                        <div className="detail-meta">
                          {step.endTime
                            ? `耗时 ${Math.round(
                                (step.endTime.getTime() - step.startTime.getTime()) / 1000,
                              )}s`
                            : '运行中...'}
                        </div>
                      )}
                    </section>
                  );
                })}
              </>
            ) : (
              <div className="detail-empty">
                <Activity size={28} />
                <p>暂无执行计划</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'traces' && (
          <div className="detail-stack">
            {session.traces.length > 0 ? (
              Object.entries(traceGroups).map(([taskId, traces]) => {
                const totalDuration = formatDuration(
                  traces.reduce((sum, trace) => sum + (trace.meta.durationMs ?? 0), 0),
                );

                return (
                  <section key={taskId} className="detail-card trace-group-card">
                    <div className="trace-group-head">
                      <div className="trace-group-copy">
                        <div className="trace-group-title">{formatTraceGroupTitle(session, taskId)}</div>
                        <div className="detail-meta trace-group-subtitle">{taskId}</div>
                      </div>
                      <div className="trace-group-summary">
                        <span className="trace-meta-chip">{traces.length} 条事件</span>
                        {totalDuration && <span className="trace-meta-chip">总耗时 {totalDuration}</span>}
                      </div>
                    </div>
                    <div className="trace-timeline">
                      {traces.map((trace) => {
                        const Icon = traceKindIcons[trace.kind];
                        const metaChips = getTraceMetaChips(trace);
                        const detailRows = getTraceDetailRows(trace);

                        return (
                          <div key={trace.id} className="trace-event">
                            <div className="trace-rail">
                              <div className={`trace-dot ${traceTones[trace.statusTone]}`} />
                            </div>
                            <div className="trace-event-body">
                              <div className="trace-head">
                                <div className="trace-head-main">
                                  <span className={`trace-badge ${traceTones[trace.statusTone]}`}>
                                    {trace.title}
                                  </span>
                                  <span className="detail-meta">{formatTraceTime(trace.timestamp)}</span>
                                </div>
                                <button
                                  type="button"
                                  className={`trace-expand ${expandedTraceIds[trace.id] ? 'is-open' : ''}`}
                                  onClick={() => toggleTrace(trace.id)}
                                >
                                  <ChevronDown size={14} />
                                  <span>{expandedTraceIds[trace.id] ? '收起' : '详情'}</span>
                                </button>
                              </div>
                              <div className="trace-summary-row">
                                <Icon size={16} className="trace-kind-icon" />
                                <div className={`trace-summary ${trace.summaryEmpty ? 'is-empty' : ''}`}>
                                  {trace.summaryEmpty ? (
                                    <>
                                      <span className="trace-empty-label">摘要为空</span>
                                      {trace.emptyReason && (
                                        <span className="trace-empty-reason">{trace.emptyReason}</span>
                                      )}
                                    </>
                                  ) : (
                                    trace.summary
                                  )}
                                </div>
                              </div>
                              {metaChips.length > 0 && (
                                <div className="trace-meta-list">
                                  {metaChips.map((chip) => (
                                    <span key={chip} className="trace-meta-chip">
                                      {chip}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {expandedTraceIds[trace.id] && (
                                <div className="trace-details-panel">
                                  {detailRows.length > 0 && (
                                    <div className="trace-details-grid">
                                      {detailRows.map((row) => (
                                        <div key={row.label} className="trace-detail-row">
                                          <span className="trace-detail-label">{row.label}</span>
                                          <span className="trace-detail-value">{row.value}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                  {trace.message &&
                                    trace.message !== trace.summary &&
                                    !trace.summaryEmpty && (
                                    <div className="trace-detail-block">
                                      <div className="trace-detail-heading">原始消息</div>
                                      <div className="trace-detail-text">{trace.message}</div>
                                    </div>
                                    )}
                                  {hasTraceRawDetails(trace) && (
                                    <div className="trace-detail-block">
                                      <div className="trace-detail-heading">原始字段</div>
                                      <pre className="trace-details">
                                        {JSON.stringify(trace.rawDetails, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                );
              })
            ) : (
              <div className="detail-empty">
                <Clock size={28} />
                <p>暂无执行追踪</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'memory' && (
          <div className="detail-stack">
            {session.memory.length > 0 ? (
              session.memory.map((memory) => {
                const memoryId = `${memory.key}-${memory.source}`;
                const isSummary = memory.key === 'summary';
                const isExpanded = Boolean(expandedMemoryIds[memoryId]);

                return (
                  <section key={memoryId} className="detail-card">
                    <div className="memory-head">
                      <span className="memory-chip">{memory.key}</span>
                      <span className="detail-meta">{memory.source}</span>
                    </div>
                    {isSummary ? (
                      <>
                        <div className="memory-status-row">
                          <div className="memory-status-copy">
                            <div className="memory-status-title">Memory available</div>
                            <div className="detail-meta">{memory.value.length} chars stored</div>
                          </div>
                          <button
                            type="button"
                            className="memory-link"
                            onClick={() => toggleMemory(memoryId)}
                          >
                            {isExpanded ? 'Hide full memory' : 'View full memory'}
                          </button>
                        </div>
                        {isExpanded && <pre className="memory-full-text">{memory.value}</pre>}
                      </>
                    ) : (
                      <div className="trace-message">{memory.value}</div>
                    )}
                    <div className="detail-meta">
                      {new Date(memory.timestamp).toLocaleString('zh-CN')}
                    </div>
                  </section>
                );
              })
            ) : (
              <div className="detail-empty">
                <Database size={28} />
                <p>暂无工作记忆</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'eval' && (
          <div className="detail-stack">
            {evalMetrics.length > 0 ? (
              evalMetrics.map((metric) => (
                <section key={metric.name} className="detail-card">
                  <div className="metric-head">
                    <span>{metric.name}</span>
                    <span className={`metric-badge metric-${metric.status}`}>
                      {metric.status === 'good' && '正常'}
                      {metric.status === 'warning' && '警告'}
                      {metric.status === 'error' && '异常'}
                    </span>
                  </div>
                  <div className="metric-value">
                    {metric.value}
                    <span>{metric.unit}</span>
                  </div>
                </section>
              ))
            ) : (
              <div className="detail-empty">
                <BarChart3 size={28} />
                <p>暂无评估指标</p>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
