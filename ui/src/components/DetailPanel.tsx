import {
  Activity,
  BarChart3,
  CheckCircle2,
  Circle,
  Clock,
  Database,
  Loader2,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

import type { EvalMetric, Session } from '../types';

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

export function DetailPanel({ session, evalMetrics }: DetailPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('plan');
  const traceGroups = session.traces.reduce<Record<string, typeof session.traces>>((groups, trace) => {
    const key = trace.stepId || 'ungrouped';
    groups[key] = [...(groups[key] ?? []), trace];
    return groups;
  }, {});

  const tabs = [
    { id: 'plan' as const, label: '执行计划', icon: Activity },
    { id: 'traces' as const, label: '执行追踪', icon: Clock },
    { id: 'memory' as const, label: '工作记忆', icon: Database },
    { id: 'eval' as const, label: '评估指标', icon: BarChart3 },
  ];

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
                          width: `${(session.plan.currentStepIndex / session.plan.steps.length) * 100}%`,
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
              Object.entries(traceGroups).map(([taskId, traces]) => (
                <section key={taskId} className="detail-card trace-group-card">
                  <div className="trace-group-head">
                    <div>
                      <div className="trace-group-title">{taskId}</div>
                      <div className="detail-meta">{traces.length} 条事件</div>
                    </div>
                  </div>
                  <div className="trace-timeline">
                    {traces.map((trace) => (
                      <div key={trace.id} className="trace-event">
                        <div className={`trace-dot ${traceTones[trace.type]}`} />
                        <div className="trace-event-body">
                          <div className="trace-head">
                            <span className={`trace-badge ${traceTones[trace.type]}`}>
                              {trace.type}
                            </span>
                            <span className="detail-meta">
                              {new Date(trace.timestamp).toLocaleTimeString('zh-CN')}
                            </span>
                          </div>
                          <div className="trace-message">{trace.message}</div>
                          {trace.details && (
                            <pre className="trace-details">{JSON.stringify(trace.details, null, 2)}</pre>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              ))
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
              session.memory.map((memory) => (
                <section key={`${memory.key}-${memory.source}`} className="detail-card">
                  <div className="memory-head">
                    <span className="memory-chip">{memory.key}</span>
                    <span className="detail-meta">{memory.source}</span>
                  </div>
                  <div className="trace-message">{memory.value}</div>
                  <div className="detail-meta">
                    {new Date(memory.timestamp).toLocaleString('zh-CN')}
                  </div>
                </section>
              ))
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
