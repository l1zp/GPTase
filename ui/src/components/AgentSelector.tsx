import { ChevronDown, Cpu, Sparkles } from 'lucide-react';
import { useState } from 'react';

import type { Agent } from '../types';

interface AgentSelectorProps {
  agents: Agent[];
  selectedAgentId: string;
  onSelectAgent: (agentId: string) => void;
}

const toneMap = {
  general: 'badge-slate',
  research: 'badge-blue',
  biochem: 'badge-purple',
  'data-analysis': 'badge-green',
  'code-expert': 'badge-amber',
} as const;

export function AgentSelector({ agents, selectedAgentId, onSelectAgent }: AgentSelectorProps) {
  const [open, setOpen] = useState(false);
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];

  return (
    <div className="agent-selector">
      <button className="agent-trigger" onClick={() => setOpen((prev) => !prev)}>
        <div className={`agent-mark ${toneMap[selectedAgent?.type ?? 'general']}`}>
          <Cpu size={18} />
        </div>
        <div className="agent-copy">
          <div className="agent-name">{selectedAgent?.name}</div>
          <div className="agent-description">{selectedAgent?.description}</div>
        </div>
        <ChevronDown size={16} className={open ? 'rotated' : ''} />
      </button>

      {open && (
        <>
          <button className="select-backdrop" aria-label="关闭" onClick={() => setOpen(false)} />
          <div className="agent-menu">
            {agents.map((agent) => (
              <button
                key={agent.id}
                className={`agent-option ${agent.id === selectedAgentId ? 'is-selected' : ''}`}
                onClick={() => {
                  onSelectAgent(agent.id);
                  setOpen(false);
                }}
              >
                <div className={`agent-mark ${toneMap[agent.type]}`}>
                  <Cpu size={18} />
                </div>
                <div className="agent-option-copy">
                  <div className="agent-option-head">
                    <span>{agent.name}</span>
                    {agent.status === 'active' && (
                      <span className="agent-active">
                        <Sparkles size={12} />
                        活跃
                      </span>
                    )}
                  </div>
                  <p>{agent.description}</p>
                  <div className="agent-caps">
                    {agent.capabilities.slice(0, 3).map((capability) => (
                      <span key={capability} className="cap-chip">
                        {capability}
                      </span>
                    ))}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
