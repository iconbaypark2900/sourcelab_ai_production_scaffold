"use client";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import GapClosureWorkflowActions from "@/components/GapClosureWorkflowActions";
import type { LibraryExpansionExecutionArtifact } from "@/lib/types";

interface ExpansionExecutionPanelProps {
  report: LibraryExpansionExecutionArtifact | null;
}

function statusTone(status: string): "pass" | "review" | "blocked" | "neutral" {
  switch (status) {
    case "executed":
      return "pass";
    case "planned":
      return "review";
    case "error":
      return "blocked";
    default:
      return "neutral";
  }
}

export default function ExpansionExecutionPanel({ report }: ExpansionExecutionPanelProps) {
  if (!report) {
    return null;
  }

  const workflow = {
    runId: report.run_id,
    topic: report.topic,
    sourcePack: report.source_pack,
    execute: report.mode === "execute",
  };

  return (
    <Panel title="Expansion execution" hint="Collector commands and run status" id="research-expansion-execution">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <StatusPill tone={report.mode === "execute" ? "pass" : "review"} label={report.mode} />
      </div>

      {(report.collector_commands ?? []).length > 0 && (
        <ul className="mb-3 space-y-1 font-mono text-[0.65rem] text-[var(--sl-text-dim)]">
          {(report.collector_commands ?? []).map((command) => (
            <li key={command}>{command}</li>
          ))}
        </ul>
      )}

      {(report.executed_collectors ?? []).length > 0 && (
        <div className="mb-3 space-y-2 text-xs text-[var(--sl-text-dim)]">
          {(report.executed_collectors ?? []).map((entry) => (
            <div key={`${entry.collector}-${entry.query}`} className="rounded border border-[var(--sl-border)] p-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-white">{entry.collector}</span>
                <StatusPill tone={statusTone(entry.status)} label={entry.status} dot={false} />
              </div>
              {entry.message && <div className="mt-1">{entry.message}</div>}
            </div>
          ))}
        </div>
      )}

      {(report.manual_collectors ?? []).length > 0 && (
        <div className="text-xs text-[var(--sl-text-dim)]">
          Manual: {(report.manual_collectors ?? []).map((entry) => entry.collector).join(", ")}
        </div>
      )}

      <GapClosureWorkflowActions workflow={workflow} panel="expansion" />
    </Panel>
  );
}
