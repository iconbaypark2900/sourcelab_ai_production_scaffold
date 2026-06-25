"use client";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import GapClosureWorkflowActions from "@/components/GapClosureWorkflowActions";
import type { SourcePromotionReportArtifact } from "@/lib/types";

interface SourcePromotionPanelProps {
  report: SourcePromotionReportArtifact | null;
}

export default function SourcePromotionPanel({ report }: SourcePromotionPanelProps) {
  if (!report) {
    return null;
  }

  const workflow = {
    runId: report.run_id,
    topic: report.topic,
    sourcePack: report.source_pack,
    promoteForce: report.mode === "force",
  };

  return (
    <Panel title="Source promotion" hint="Pack promotion candidates and write status" id="research-source-promotion">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <StatusPill tone={report.mode === "force" ? "pass" : "review"} label={report.mode} />
        <span className="text-xs text-[var(--sl-text-dim)]">min quality {report.min_quality?.toFixed(2)}</span>
      </div>

      {(report.target_domains ?? []).length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {(report.target_domains ?? []).map((domain) => (
            <span key={domain} className="sl-pill sl-pill--neutral text-xs font-mono">
              {domain}
            </span>
          ))}
        </div>
      )}

      <ul className="space-y-2 text-xs text-[var(--sl-text-dim)]">
        {(report.candidates ?? []).map((candidate) => (
          <li key={candidate.source_id} className="rounded border border-[var(--sl-border)] p-2">
            <div className="font-medium text-white">{candidate.title}</div>
            <div>
              {candidate.status} · q={candidate.quality_score?.toFixed(2)} · {candidate.reason}
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-3 text-xs text-[var(--sl-text-dim)]">
        Promoted: {report.promoted_count ?? 0} · Skipped: {report.skipped_count ?? 0}
      </div>

      <GapClosureWorkflowActions workflow={workflow} panel="promotion" />
    </Panel>
  );
}
