"use client";

import { useState } from "react";

import { EVAL_TYPE_LABELS } from "@/lib/evals-summary";
import type { GoldenEvalFailure, GoldenEvalReport } from "@/lib/types";
import { humanize, truncate } from "@/lib/format";

interface EvalFailurePanelProps {
  report: GoldenEvalReport;
  failures: GoldenEvalFailure[];
  defaultOpen?: boolean;
}

function FailureRow({ failure, index }: { failure: GoldenEvalFailure; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const caseLabel = failure.case_description ?? `Case #${index + 1}`;
  const hasDetails =
    failure.expected !== undefined ||
    failure.actual !== undefined ||
    (failure.details && failure.details.length > 0);

  return (
    <li className="border-b border-[var(--sl-border)] py-2 last:border-0">
      <button
        type="button"
        className="flex w-full items-start justify-between gap-2 text-left"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <span className="text-sm font-medium text-white">
          <span className="mr-2 font-mono text-xs text-[var(--sl-amber)]">
            #{failure.case_index ?? index + 1}
          </span>
          {truncate(caseLabel, 80)}
        </span>
        <span className="text-xs text-[var(--sl-text-faint)]">{expanded ? "▾" : "▸"}</span>
      </button>

      {expanded && hasDetails && (
        <dl className="mt-2 space-y-1.5 pl-6 text-xs">
          {failure.expected !== undefined && (
            <div>
              <dt className="text-[var(--sl-text-faint)]">Expected</dt>
              <dd className="text-[var(--sl-text)]">{truncate(failure.expected, 240)}</dd>
            </div>
          )}
          {failure.actual !== undefined && (
            <div>
              <dt className="text-[var(--sl-text-faint)]">Actual</dt>
              <dd className="text-[var(--sl-text)]">{truncate(failure.actual, 240)}</dd>
            </div>
          )}
          {failure.details && failure.details.length > 0 && (
            <div>
              <dt className="text-[var(--sl-text-faint)]">Details</dt>
              <dd className="text-[var(--sl-text)]">{truncate(failure.details, 240)}</dd>
            </div>
          )}
        </dl>
      )}
    </li>
  );
}

export default function EvalFailurePanel({
  report,
  failures,
  defaultOpen = false,
}: EvalFailurePanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const evalName = report.eval_name ?? "";
  const label = EVAL_TYPE_LABELS[evalName] ?? humanize(evalName);

  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)]">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className="text-sm font-medium text-[var(--sl-rose)]">
          {label}: {failures.length} failing case{failures.length === 1 ? "" : "s"}
        </span>
        <span className="text-xs text-[var(--sl-text-faint)]">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <ul className="border-t border-[var(--sl-border)] px-3 pb-2">
          {failures.map((failure, index) => (
            <FailureRow
              key={`${failure.case_index ?? index}-${index}`}
              failure={failure}
              index={index}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
