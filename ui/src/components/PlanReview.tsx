import { CheckCircle2, LayoutList } from 'lucide-react';

import type { Plan } from '../types';

interface PlanReviewProps {
  plan: Plan;
  onApprove: () => void;
  onReject: () => void;
  onRevise: () => void;
}

export function PlanReview({ plan, onApprove, onReject, onRevise }: PlanReviewProps) {
  return (
    <div className="plan-review">
      <div className="plan-review-head">
        <LayoutList size={14} />
        Draft plan · awaiting approval
      </div>
      <div className="plan-review-sub">
        {plan.steps.length} steps · writes to workspace
      </div>
      <div className="plan-review-steps">
        {plan.steps.map((step, i) => (
          <div key={step.id} className="plan-step-row">
            <div className="plan-step-idx">{String(i + 1).padStart(2, '0')}</div>
            <div className="plan-step-body">
              <div className="title">{step.title}</div>
              {step.description && <div className="desc">{step.description}</div>}
            </div>
            {step.assignedAgent && (
              <div className="plan-step-agent">{step.assignedAgent}</div>
            )}
          </div>
        ))}
      </div>
      <div className="plan-review-actions">
        <button className="btn btn-primary" onClick={onApprove}>
          <CheckCircle2 size={13} /> Approve &amp; run
        </button>
        <button className="btn" onClick={onRevise}>Revise plan</button>
        <button className="btn btn-ghost" onClick={onReject}>Discard</button>
      </div>
    </div>
  );
}
