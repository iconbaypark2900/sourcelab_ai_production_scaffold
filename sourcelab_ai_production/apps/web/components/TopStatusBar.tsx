import Link from "next/link";

import type { AnswerAttemptSummary, RunSummary } from "@/lib/types";
import { formatScore, timeAgo } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

interface TopStatusBarProps {
  run: RunSummary;
  /** When viewing a historical attempt, overlay answer/learning signals only. */
  selectedAttempt?: AnswerAttemptSummary | null;
  viewMode?: "latest" | "attempt";
}

/** The Run Studio header strip: identity + the headline release signals. */
export default function TopStatusBar({
  run,
  selectedAttempt,
  viewMode = "latest",
}: TopStatusBarProps) {
  const harnessLabel =
    run.harness_passed === null ? "—" : run.harness_passed ? "HARNESS PASS" : "HARNESS FAIL";

  const viewingHistorical = viewMode === "attempt" && selectedAttempt;
  const answerScore = viewingHistorical
    ? selectedAttempt.overall_score
    : run.has_answer
      ? run.answer_score
      : null;
  const needsReview = viewingHistorical
    ? selectedAttempt.needs_review
    : run.needs_review;

  return (
    <div className="sl-panel sl-panel--glow-cyan sl-fade-up px-4 py-3.5">
      {viewingHistorical && (
        <div className="mb-3 rounded-lg border border-[rgba(168,85,247,0.32)] bg-[rgba(168,85,247,0.08)] px-3 py-2 text-xs text-[var(--sl-text-dim)]">
          Viewing historical attempt:{" "}
          <span className="font-mono text-white">
            {selectedAttempt.attempt_id.replace("attempt_", "")}
          </span>
          . Latest run snapshot preserved.
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="min-w-0">
          <div className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--sl-text-faint)]">
            Run
          </div>
          <div className="font-mono text-sm text-white">{run.run_id || "—"}</div>
        </div>

        <div className="min-w-0 max-w-md flex-1">
          <div className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--sl-text-faint)]">
            Topic
          </div>
          <div className="truncate text-sm text-[var(--sl-text)]" title={run.topic}>
            {run.topic || "—"}
          </div>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Link href="/runs/new" className="sl-btn sl-btn--primary px-3 py-1 text-xs">
            Create new run
          </Link>
          <StatusPill status={run.harness_passed} label={harnessLabel} />
          <StatusPill
            status={run.proof_bundle_status}
            label={`PROOF ${run.proof_bundle_status?.toUpperCase() || "—"}`}
          />
          <span className="sl-pill sl-pill--info" title="Citation resolution rate">
            <span className="sl-pill__dot" />
            CITATIONS {formatScore(run.citation_resolution_rate)}
          </span>
          <span
            className={`sl-pill ${
              answerScore !== null ? "sl-pill--neutral" : "sl-pill--missing"
            }`}
            title={
              viewingHistorical
                ? "Historical attempt score (latest snapshot unchanged)"
                : "Learner answer score"
            }
          >
            <span className="sl-pill__dot" />
            ANSWER {answerScore !== null ? formatScore(answerScore) : "none"}
            {viewingHistorical ? " (attempt)" : ""}
          </span>
          {needsReview === true ? (
            <StatusPill tone="review" label="NEEDS REVIEW" />
          ) : needsReview === false ? (
            <StatusPill tone="pass" label="REVIEW CLEAR" />
          ) : null}
        </div>
      </div>

      {run.created_at && (
        <div className="mt-2 text-[0.7rem] text-[var(--sl-text-faint)]">
          Stabilized {timeAgo(run.created_at)}
          {run.unsupported_high_risk_claims > 0 && (
            <span className="ml-3 text-[var(--sl-amber)]">
              {run.unsupported_high_risk_claims} unsupported high-risk claim
              {run.unsupported_high_risk_claims === 1 ? "" : "s"}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
