"use client";

import Link from "next/link";

import { Panel } from "@/components/Chrome";
import {
  computeResearchVerdict,
  orderResearchActions,
} from "@/lib/research-validation";
import type { ResearchValidationInput } from "@/lib/research-validation";
import { buildAttemptQuery } from "@/lib/attempt-url";

interface NextResearchActionsPanelProps {
  input: ResearchValidationInput;
  runId: string;
}

export default function NextResearchActionsPanel({ input, runId }: NextResearchActionsPanelProps) {
  const verdict = computeResearchVerdict(input);
  const actions = orderResearchActions(input, verdict);

  return (
    <Panel title="Next research actions" hint="Prioritized checklist" glow="cyan" id="research-next-actions">
      {!actions.length ? (
        <p className="text-sm text-[var(--sl-text-faint)]">No actions recommended.</p>
      ) : (
        <ol className="space-y-2">
          {actions.map((action, index) => {
            const href = action.tab
              ? `/runs/${runId}?${buildAttemptQuery("", { tab: action.tab }).toString()}`
              : `/runs/${runId}${action.anchor.startsWith("#") ? "" : ""}`;
            const onPageAnchor = action.anchor.startsWith("#") ? action.anchor : undefined;
            return (
              <li
                key={action.id}
                className="flex gap-3 rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] p-3"
              >
                <span className="font-mono text-sm text-[var(--sl-violet)]">{index + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-white">{action.title}</div>
                  <p className="mt-0.5 text-xs text-[var(--sl-text-dim)]">{action.detail}</p>
                  <div className="mt-2">
                    {action.tab ? (
                      <Link href={href} className="sl-btn text-xs">
                        Open {action.tab} tab
                      </Link>
                    ) : onPageAnchor ? (
                      <a href={onPageAnchor} className="sl-btn text-xs">
                        Jump to section
                      </a>
                    ) : (
                      <Link href={`/runs/${runId}`} className="sl-btn text-xs">
                        Open run
                      </Link>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
