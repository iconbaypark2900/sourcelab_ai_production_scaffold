"use client";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import GapClosureWorkflowActions from "@/components/GapClosureWorkflowActions";
import { suggestNextSafeCommandFromOrchestration } from "@/lib/gap-closure-workflow";
import type { GapClosureOrchestrationArtifact, GapClosureReportArtifact } from "@/lib/types";

interface GapClosurePanelProps {
  report: GapClosureReportArtifact | null;
  orchestration?: GapClosureOrchestrationArtifact | null;
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

export default function GapClosurePanel({ report, orchestration }: GapClosurePanelProps) {
  if (!report && !orchestration) {
    return null;
  }

  const topic = report?.topic ?? orchestration?.topic ?? "";
  const sourcePack = report?.source_pack ?? orchestration?.source_pack ?? "";
  const runId = report?.run_id ?? orchestration?.run_id ?? "";
  const workflow = {
    runId: orchestration?.run_id ?? report?.baseline_run_id ?? runId,
    topic,
    sourcePack,
    execute: orchestration?.mode === "execute",
    promoteForce: orchestration?.promotion_status === "force",
    repairManifests: orchestration?.manifest_repair_status === "executed",
    createFollowup: Boolean(orchestration?.followup_run_id),
  };

  const nextSafeCommand = orchestration
    ? suggestNextSafeCommandFromOrchestration({
        runId: orchestration.run_id,
        answerSubmitStatus: orchestration.answer_submit_status,
        answerSource: orchestration.answer_source,
        followupRunId: orchestration.followup_run_id,
        steps: orchestration.steps,
      })
    : null;

  const coverageDelta =
    report && report.coverage_score_before != null && report.coverage_score_after != null
      ? report.coverage_score_after - report.coverage_score_before
      : null;
  const genericnessDelta =
    report && report.genericness_before != null && report.genericness_after != null
      ? report.genericness_after - report.genericness_before
      : null;

  return (
    <Panel title="Gap closure" hint="Baseline vs follow-up evidence improvement" glow="cyan" id="research-gap-closure">
      {report && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <StatusPill tone={verdictTone(report.verdict)} label={report.verdict} />
            {report.baseline_run_id && (
              <span className="text-xs text-[var(--sl-text-dim)]">
                baseline <span className="font-mono text-white">{report.baseline_run_id}</span>
              </span>
            )}
          </div>

          <div className="mb-3 grid gap-2 sm:grid-cols-2 text-xs text-[var(--sl-text-dim)]">
            {coverageDelta != null && (
              <div>
                Coverage: {report.coverage_score_before?.toFixed(3)} → {report.coverage_score_after?.toFixed(3)}{" "}
                <span className="font-mono text-white">({coverageDelta >= 0 ? "+" : ""}{coverageDelta.toFixed(3)})</span>
              </div>
            )}
            {genericnessDelta != null && (
              <div>
                Genericness: {report.genericness_before?.toFixed(3)} → {report.genericness_after?.toFixed(3)}{" "}
                <span className="font-mono text-white">({genericnessDelta >= 0 ? "+" : ""}{genericnessDelta.toFixed(3)})</span>
              </div>
            )}
          </div>

          {(report.gaps_closed ?? []).length > 0 && (
            <div className="mb-2 text-xs text-[var(--sl-text-dim)]">
              Gaps closed: {(report.gaps_closed ?? []).join("; ")}
            </div>
          )}
          {(report.gaps_remaining ?? []).length > 0 && (
            <div className="mb-2 text-xs text-[var(--sl-text-dim)]">
              Gaps remaining: {(report.gaps_remaining ?? []).join("; ")}
            </div>
          )}
          {((report.new_sources_used ?? []).length > 0 || (report.new_library_cards_used ?? []).length > 0) && (
            <div className="text-xs text-[var(--sl-text-dim)]">
              New evidence:{" "}
              {[...(report.new_sources_used ?? []), ...(report.new_library_cards_used ?? [])].join(", ")}
            </div>
          )}
        </>
      )}

      {orchestration && (
        <div className="mb-3 space-y-1 text-xs text-[var(--sl-text-dim)]">
          <div>
            Orchestration mode: <span className="font-mono text-white">{orchestration.mode}</span>
          </div>
          <div>
            Answer submitted:{" "}
            <span className="font-mono text-white">
              {orchestration.answer_submit_status === "executed" ? "yes" : "no"}
            </span>
          </div>
          <div>
            Topic profile updated:{" "}
            <span className="font-mono text-white">{orchestration.topic_profile_updated ? "yes" : "no"}</span>
          </div>
          {orchestration.followup_run_id && (
            <div>
              Follow-up run: <span className="font-mono text-white">{orchestration.followup_run_id}</span>
            </div>
          )}
          {orchestration.followup_lesson_command && (
            <div className="font-mono text-[0.65rem]">{orchestration.followup_lesson_command}</div>
          )}
          {orchestration.gap_closure_verdict && (
            <div>
              Orchestration verdict:{" "}
              <StatusPill tone={verdictTone(orchestration.gap_closure_verdict)} label={orchestration.gap_closure_verdict} dot={false} />
            </div>
          )}
          {nextSafeCommand && (
            <div className="font-mono text-[0.65rem] text-[var(--sl-text-faint)]">
              Next safe command: {nextSafeCommand}
            </div>
          )}
        </div>
      )}

      {(report || orchestration) && (
        <GapClosureWorkflowActions
          workflow={workflow}
          panel="gap-closure"
          orchestrationCommands={orchestration?.commands_planned}
          orchestration={orchestration}
        />
      )}
    </Panel>
  );
}
