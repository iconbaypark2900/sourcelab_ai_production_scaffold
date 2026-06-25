"use client";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import type { LessonEvolutionReportArtifact } from "@/lib/types";

interface LessonEvolutionPanelProps {
  report: LessonEvolutionReportArtifact | null;
}

function verdictTone(verdict: string): "pass" | "review" | "blocked" | "neutral" {
  switch (verdict) {
    case "improved":
      return "pass";
    case "worse":
      return "blocked";
    case "unchanged":
      return "review";
    default:
      return "neutral";
  }
}

export default function LessonEvolutionPanel({ report }: LessonEvolutionPanelProps) {
  if (!report) {
    return null;
  }

  const delta = report.quality_delta;

  return (
    <Panel title="Lesson evolution" hint="Follow-up run comparison" glow="cyan" id="research-evolution">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <StatusPill tone={verdictTone(report.verdict)} label={report.verdict} />
        {report.profile_used && (
          <span className="sl-pill sl-pill--info text-xs">profile used</span>
        )}
      </div>

      {(report.previous_run_ids ?? []).length > 0 && (
        <div className="mb-3 text-xs text-[var(--sl-text-dim)]">
          Previous runs:{" "}
          <span className="font-mono text-white">{(report.previous_run_ids ?? []).join(", ")}</span>
        </div>
      )}

      {delta && (
        <div className="mb-3 grid gap-2 sm:grid-cols-2 text-xs text-[var(--sl-text-dim)]">
          {delta.coverage_delta != null && (
            <div>
              Coverage delta:{" "}
              <span className="font-mono text-white">{delta.coverage_delta >= 0 ? "+" : ""}{delta.coverage_delta.toFixed(4)}</span>
            </div>
          )}
          {delta.genericness_score_delta != null && (
            <div>
              Genericness delta:{" "}
              <span className="font-mono text-white">{delta.genericness_score_delta >= 0 ? "+" : ""}{delta.genericness_score_delta.toFixed(4)}</span>
            </div>
          )}
        </div>
      )}

      {(report.changes_from_previous ?? []).length > 0 && (
        <ul className="mb-3 space-y-1 text-sm text-[var(--sl-text-dim)]">
          {(report.changes_from_previous ?? []).map((change) => (
            <li key={`${change.area}-${change.description}`}>
              <span className="font-mono text-white">{change.area}</span> — {change.description}
            </li>
          ))}
        </ul>
      )}

      {delta && (delta.gaps_closed?.length ?? 0) > 0 && (
        <div className="text-xs text-[var(--sl-text-dim)]">
          Gaps closed: {(delta.gaps_closed ?? []).join("; ")}
        </div>
      )}
    </Panel>
  );
}
