"use client";

import { Panel } from "@/components/Chrome";
import { generateResearchGaps } from "@/lib/research-validation";
import type { ResearchValidationInput } from "@/lib/research-validation";

interface ResearchGapsPanelProps {
  input: ResearchValidationInput;
}

export default function ResearchGapsPanel({ input }: ResearchGapsPanelProps) {
  const gaps = generateResearchGaps(input);

  return (
    <Panel title="Research gaps" hint="Deterministic gaps + suggested queries (no web browse)" id="research-gaps">
      {!gaps.length ? (
        <p className="text-sm text-[var(--sl-text-dim)]">
          No material gaps detected — artifacts meet study-ready thresholds.
        </p>
      ) : (
        <ul className="space-y-3">
          {gaps.map((gap) => (
            <li
              key={gap.id}
              className="rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] p-3"
            >
              <div className="mb-1 flex items-center gap-2">
                <span className="sl-pill sl-pill--neutral">{gap.category}</span>
                <span className="text-sm font-medium text-white">{gap.title}</span>
              </div>
              <p className="text-xs text-[var(--sl-text-dim)]">{gap.detail}</p>
              {gap.suggestedQueries.length > 0 && (
                <div className="mt-2">
                  <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
                    Suggested search queries
                  </div>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-[var(--sl-cyan)]">
                    {gap.suggestedQueries.map((query) => (
                      <li key={query}>{query}</li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
