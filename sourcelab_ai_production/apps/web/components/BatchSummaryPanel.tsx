"use client";

import { Panel } from "@/components/Chrome";
import type { BatchDetailResponse } from "@/lib/types";

interface BatchSummaryPanelProps {
  batch: BatchDetailResponse;
}

export default function BatchSummaryPanel({ batch }: BatchSummaryPanelProps) {
  const totals = (batch.summary.totals as Record<string, number> | undefined) ?? {};
  const topics = Array.isArray(batch.summary.topics)
    ? (batch.summary.topics as string[])
    : [];

  return (
    <Panel title="Batch summary" glow="cyan">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Runs created" value={String(totals.created ?? batch.run_ids.length)} />
        <Stat label="Failures" value={String(totals.failed ?? batch.failures.length)} />
        <Stat label="Harness pass" value={String(totals.harness_pass ?? "—")} />
        <Stat label="Artifacts" value={String(totals.artifact_count ?? "—")} />
      </div>
      {topics.length > 0 && (
        <p className="mt-3 text-xs text-[var(--sl-text-dim)]">
          Topics: {topics.join(" · ")}
        </p>
      )}
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2">
      <div className="text-base font-semibold text-white">{value}</div>
      <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {label}
      </div>
    </div>
  );
}
