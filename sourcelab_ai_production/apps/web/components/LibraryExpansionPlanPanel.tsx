"use client";

import { Panel } from "@/components/Chrome";
import type { LibraryExpansionPlanArtifact } from "@/lib/types";

interface LibraryExpansionPlanPanelProps {
  plan: LibraryExpansionPlanArtifact | null;
}

export default function LibraryExpansionPlanPanel({ plan }: LibraryExpansionPlanPanelProps) {
  if (!plan) {
    return null;
  }

  return (
    <Panel title="Library expansion plan" hint="Collector commands and promotion targets" id="research-expansion-plan">
      {(plan.recommended_collectors ?? []).length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {(plan.recommended_collectors ?? []).map((collector) => (
            <span key={collector} className="sl-pill sl-pill--neutral text-xs font-mono">
              {collector}
            </span>
          ))}
        </div>
      )}

      {(plan.collector_queries ?? []).length > 0 && (
        <div className="space-y-2 text-xs text-[var(--sl-text-dim)]">
          {(plan.collector_queries ?? []).map((entry) => (
            <div key={`${entry.collector}-${entry.query}`} className="rounded border border-[var(--sl-border)] p-2">
              <div className="font-mono text-white">
                {entry.collector} <span className="text-[var(--sl-text-faint)]">({entry.priority})</span>
              </div>
              <div className="mt-1">Query: {entry.query}</div>
              <div className="mt-1 font-mono text-[0.65rem] text-[var(--sl-text-faint)]">{entry.example_command}</div>
            </div>
          ))}
        </div>
      )}

      {(plan.promotion_targets ?? []).length > 0 && (
        <div className="mt-3 border-t border-[var(--sl-border)] pt-3">
          <div className="mb-2 text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
            Promotion targets
          </div>
          <ul className="space-y-1 font-mono text-[0.65rem] text-[var(--sl-text-dim)]">
            {(plan.promotion_targets ?? []).map((target) => (
              <li key={target}>{target}</li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}
