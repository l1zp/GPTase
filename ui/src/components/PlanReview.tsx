import { AlertTriangle, CheckCircle2, Edit3, XCircle } from 'lucide-react';

import type { Plan } from '../types';

interface PlanReviewProps {
  plan: Plan;
  onApprove: () => void;
  onReject: () => void;
  onRevise: () => void;
}

export function PlanReview({ plan, onApprove, onReject, onRevise }: PlanReviewProps) {
  return (
    <section className="plan-review">
      <div className="plan-review-head">
        <div className="plan-review-mark">
          <AlertTriangle size={20} />
        </div>
        <div>
          <h3>执行计划待审核</h3>
          <p>智能体已生成包含 {plan.steps.length} 个步骤的计划，请审核后批准执行。</p>
        </div>
      </div>

      <div className="plan-review-body">
        <div className="plan-review-goal">
          <span>目标:</span> {plan.goal}
        </div>
        <div className="plan-review-steps">
          {plan.steps.map((step, index) => (
            <div key={step.id} className="plan-review-step">
              <span className="plan-review-index">{index + 1}</span>
              <div>
                <div className="plan-review-title">{step.title}</div>
                <div className="plan-review-desc">{step.description}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="plan-review-actions">
        <button className="primary-button" onClick={onApprove}>
          <CheckCircle2 size={16} />
          批准执行
        </button>
        <button className="secondary-button icon-only" onClick={onRevise} aria-label="修改计划">
          <Edit3 size={16} />
        </button>
        <button className="secondary-button icon-only" onClick={onReject} aria-label="拒绝计划">
          <XCircle size={16} />
        </button>
      </div>
    </section>
  );
}
