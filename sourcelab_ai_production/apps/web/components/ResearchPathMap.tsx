"use client";

import StatusPill from "@/components/StatusPill";
import type { StudyPathStep } from "@/lib/library-theme";

interface ResearchPathMapProps {
  steps: StudyPathStep[];
  title?: string;
  compact?: boolean;
}

const STATUS_TONE: Record<StudyPathStep["status"], "pass" | "info" | "missing" | "blocked"> = {
  complete: "pass",
  active: "info",
  pending: "missing",
  blocked: "blocked",
};

const STATUS_LABEL: Record<StudyPathStep["status"], string> = {
  complete: "Done",
  active: "Now",
  pending: "Next",
  blocked: "Blocked",
};

export default function ResearchPathMap({
  steps,
  title = "Study Path",
  compact = false,
}: ResearchPathMapProps) {
  if (!steps.length) {
    return null;
  }

  return (
    <div className={`sl-study-path ${compact ? "sl-study-path--compact" : ""}`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-[var(--sl-parchment-dim)]">
          {title}
        </h3>
      </div>
      <ol className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`sl-study-path__step sl-study-path__step--${step.status} flex min-w-[120px] flex-1 flex-col gap-1 rounded-xl border px-3 py-2`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-white">{step.label}</span>
              <StatusPill
                tone={STATUS_TONE[step.status]}
                label={STATUS_LABEL[step.status]}
                dot={false}
              />
            </div>
            {step.hint && (
              <span className="text-[0.65rem] text-[var(--sl-text-faint)]">{step.hint}</span>
            )}
            {!compact && index < steps.length - 1 && (
              <span className="hidden text-[var(--sl-text-faint)] sm:inline" aria-hidden>
                →
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
