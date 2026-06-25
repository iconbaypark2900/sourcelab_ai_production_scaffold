"use client";

import Link from "next/link";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  BATCH_PROGRESS_STAGES,
  estimateBatchProgressStage,
  type BatchRowState,
} from "@/lib/batch-run";
import type { BatchCreateResponse } from "@/lib/types";

interface BatchProgressPanelProps {
  batchName: string;
  rows: BatchRowState[];
  elapsedMs: number;
  complete?: boolean;
  result?: BatchCreateResponse | null;
}

export default function BatchProgressPanel({
  batchName,
  rows,
  elapsedMs,
  complete = false,
  result = null,
}: BatchProgressPanelProps) {
  const { stageIndex, stage } = estimateBatchProgressStage(elapsedMs, rows.length);

  return (
    <div className="space-y-4">
      <Panel title="Batch in progress" glow="cyan">
        <p className="text-sm text-[var(--sl-text-dim)]">
          This is a single local blocking HTTP request — not streaming. The UI shows estimated
          pipeline stages while the backend runs each row synchronously.
        </p>

        <ol className="mt-4 space-y-2">
          {BATCH_PROGRESS_STAGES.map((item, index) => {
            const done = complete || index < stageIndex;
            const active = !complete && index === stageIndex;
            return (
              <li
                key={item.id}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  active
                    ? "border-[rgba(34,211,238,0.45)] bg-[rgba(34,211,238,0.08)] text-white"
                    : done
                      ? "border-[var(--sl-border)] text-[var(--sl-text-dim)]"
                      : "border-[var(--sl-border)] text-[var(--sl-text-faint)]"
                }`}
              >
                <span className="font-mono text-xs">{done ? "✓" : active ? "…" : "·"}</span>
                {item.label}
                {active && !complete && (
                  <span className="ml-auto text-xs text-[var(--sl-cyan)]">estimated</span>
                )}
              </li>
            );
          })}
        </ol>

        {!complete && (
          <p className="mt-3 text-xs text-[var(--sl-text-faint)]">
            Current stage: {stage.label}
          </p>
        )}
      </Panel>

      <Panel title={complete ? "Run results" : "Planned runs"}>
        <div className="mb-2 text-xs text-[var(--sl-text-faint)]">{batchName}</div>
        <div className="space-y-2">
          {(complete && result ? result.runs : rows).map((row, index) => {
            if (complete && result && "run_id" in row) {
              const run = row as BatchCreateResponse["runs"][number];
              return (
                <div
                  key={run.run_id}
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--sl-border)] px-3 py-2"
                >
                  <span className="font-mono text-xs text-[var(--sl-cyan)]">{run.run_id}</span>
                  <span className="truncate text-sm">{run.topic}</span>
                  <StatusPill
                    tone={run.harness_status === "PASS" ? "pass" : "blocked"}
                    label={run.harness_status}
                    dot={false}
                  />
                  <Link href={`/runs/${run.run_id}`} className="sl-btn ml-auto text-xs">
                    Open Run Studio
                  </Link>
                </div>
              );
            }

            const planned = row as BatchRowState;
            return (
              <div
                key={planned.id}
                className="rounded-lg border border-[var(--sl-border)] px-3 py-2 text-sm"
              >
                <div className="text-xs text-[var(--sl-text-faint)]">Run {index + 1}</div>
                <div className="truncate">{planned.topic || "—"}</div>
                <div className="text-xs text-[var(--sl-text-dim)]">{planned.sourcePack}</div>
              </div>
            );
          })}
        </div>

        {complete && result && result.failures.length > 0 && (
          <div className="mt-3 space-y-1 text-sm text-[var(--sl-rose)]">
            {result.failures.map((failure) => (
              <div key={failure.index}>
                Row {failure.index + 1}: {failure.error}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
