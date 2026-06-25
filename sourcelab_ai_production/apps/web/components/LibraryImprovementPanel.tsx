"use client";

import { Panel } from "@/components/Chrome";
import GapClosureWorkflowActions from "@/components/GapClosureWorkflowActions";
import type { LibraryImprovementReportArtifact } from "@/lib/types";

interface LibraryImprovementPanelProps {
  report: LibraryImprovementReportArtifact | null;
}

export default function LibraryImprovementPanel({ report }: LibraryImprovementPanelProps) {
  if (!report) {
    return null;
  }

  const workflow = {
    runId: report.run_id,
    topic: report.topic,
    sourcePack: report.source_pack,
    execute: true,
  };

  return (
    <Panel title="Library improvement" hint="Before/after expansion metrics" glow="violet" id="research-library-improvement">
      <div className="grid gap-2 sm:grid-cols-3 text-xs text-[var(--sl-text-dim)]">
        <Metric label="Source cards" before={report.source_cards_before} after={report.source_cards_after} delta={report.new_source_cards} />
        <Metric label="Chunks" before={report.chunks_before} after={report.chunks_after} delta={report.new_chunks} />
        <Metric label="Avg quality" before={report.quality_before} after={report.quality_after} />
      </div>

      {(report.executed_collectors ?? []).length > 0 && (
        <div className="mt-3 text-xs text-[var(--sl-text-dim)]">
          Executed collectors:{" "}
          <span className="font-mono text-white">{(report.executed_collectors ?? []).join(", ")}</span>
        </div>
      )}

      {(report.errors ?? []).length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-[var(--sl-text-dim)]">
          {(report.errors ?? []).map((error) => (
            <li key={error}>• {error}</li>
          ))}
        </ul>
      )}

      <GapClosureWorkflowActions workflow={workflow} panel="improvement" />
    </Panel>
  );
}

function Metric({
  label,
  before,
  after,
  delta,
}: {
  label: string;
  before?: number;
  after?: number;
  delta?: number;
}) {
  return (
    <div className="rounded border border-[var(--sl-border)] p-2">
      <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">{label}</div>
      <div className="font-mono text-white">
        {before ?? 0} → {after ?? 0}
        {delta != null && delta > 0 ? ` (+${delta})` : ""}
      </div>
    </div>
  );
}
