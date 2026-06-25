import type { AnswerAttemptDetail, LearningReportJson, RunSummary } from "@/lib/types";
import { clamp, formatScore, humanize } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

interface LearningScorePanelProps {
  run: RunSummary;
  learningJson?: LearningReportJson | null;
  /** When set, overlay metrics from a historical attempt instead of latest run. */
  selectedAttempt?: AnswerAttemptDetail | null;
  onBackToLatest?: () => void;
}

function ScoreBar({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) {
    return <span className="text-[var(--sl-text-faint)]">—</span>;
  }
  return (
    <div className="flex items-center gap-2">
      <div className="sl-bar w-full">
        <div
          className={`sl-bar__fill ${value >= 0.6 ? "sl-bar__fill--good" : "sl-bar__fill--warn"}`}
          style={{ width: `${clamp(value * 100, 2, 100)}%` }}
        />
      </div>
      <span className="w-12 text-right font-mono text-xs text-[var(--sl-text-dim)]">
        {formatScore(value)}
      </span>
    </div>
  );
}

function num(value: unknown): number | null {
  return typeof value === "number" && !Number.isNaN(value) ? value : null;
}

function metricsFromAttempt(attempt: AnswerAttemptDetail) {
  const review = attempt.answer_review ?? {};
  const manifest = attempt.manifest;
  const grounding = attempt.source_grounding_review ?? {};

  const finalScore = num(review.overall_score) ?? manifest.overall_score;
  const uncapped = num(review.uncapped_score) ?? manifest.uncapped_score;
  const rubricAlignment =
    num(review.rubric_alignment_score) ?? manifest.rubric_alignment_score;
  const rubricGrounding = num(review.source_grounding_score);
  const conceptOverlap = num(grounding.source_grounding_score);
  const needsReview = Boolean(review.needs_review ?? manifest.needs_review);
  const capReason =
    (typeof review.cap_reason === "string" && review.cap_reason) || manifest.cap_reason || "";
  const humanReviewReason =
    (typeof review.review_reason === "string" && review.review_reason) ||
    manifest.human_review_reason ||
    "";

  return {
    finalScore,
    uncapped,
    rubricAlignment,
    rubricGrounding,
    conceptOverlap,
    needsReview,
    capReason,
    humanReviewReason,
    learningJson: attempt.learning_report ?? null,
  };
}

export default function LearningScorePanel({
  run,
  learningJson,
  selectedAttempt,
  onBackToLatest,
}: LearningScorePanelProps) {
  if (!run.has_answer && !selectedAttempt) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--sl-border)] bg-[rgba(9,14,28,0.4)] px-4 py-6 text-center">
        <div className="text-sm font-medium text-white">No answer submitted</div>
        <p className="mt-1 text-xs text-[var(--sl-text-dim)]">
          Learning update metrics appear once a learner answer is scored for this run.
        </p>
      </div>
    );
  }

  const attemptMetrics = selectedAttempt ? metricsFromAttempt(selectedAttempt) : null;

  const finalScore = attemptMetrics?.finalScore ?? run.overall_score ?? run.answer_score ?? null;
  const uncappedScore = attemptMetrics?.uncapped ?? run.uncapped_score;
  const rubricAlignmentScore =
    attemptMetrics?.rubricAlignment ?? run.rubric_alignment_score;
  const rubricGroundingScore =
    attemptMetrics?.rubricGrounding ?? run.source_grounding_score;
  const conceptOverlapScore =
    attemptMetrics?.conceptOverlap ?? run.concept_overlap_grounding_score;
  const needsReview = attemptMetrics?.needsReview ?? run.needs_review;
  const capReason = attemptMetrics?.capReason ?? run.cap_reason;
  const humanReviewReason =
    attemptMetrics?.humanReviewReason ?? run.human_review_reason;
  const activeLearningJson =
    attemptMetrics?.learningJson ?? learningJson ?? null;

  const capped =
    uncappedScore !== null &&
    finalScore !== null &&
    uncappedScore > finalScore + 1e-9;

  const rubricBreakdown = activeLearningJson?.rubric_breakdown ?? null;

  const metrics: Array<{ label: string; value: number | null; hint?: string }> = [
    { label: "Rubric alignment", value: rubricAlignmentScore },
    { label: "Uncapped score", value: uncappedScore },
    { label: "Source grounding (rubric)", value: rubricGroundingScore },
    { label: "Concept-overlap grounding", value: conceptOverlapScore },
  ];

  return (
    <div className="space-y-4">
      {selectedAttempt && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[rgba(168,85,247,0.32)] bg-[rgba(168,85,247,0.08)] px-3 py-2">
          <span className="text-xs text-[var(--sl-text-dim)]">
            Viewing attempt{" "}
            <span className="font-mono text-white">
              {selectedAttempt.attempt_id.replace("attempt_", "")}
            </span>
          </span>
          {onBackToLatest && (
            <button type="button" className="sl-btn px-2 py-0.5 text-[0.68rem]" onClick={onBackToLatest}>
              Back to latest snapshot
            </button>
          )}
        </div>
      )}

      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-4xl font-semibold sl-gradient-text">{formatScore(finalScore)}</div>
          <div className="text-xs text-[var(--sl-text-dim)]">final score</div>
        </div>
        {needsReview === true ? (
          <StatusPill tone="review" label="HUMAN REVIEW" />
        ) : needsReview === false ? (
          <StatusPill tone="pass" label="REVIEW CLEAR" />
        ) : null}
      </div>

      {capped && (
        <div className="rounded-lg border border-[rgba(251,191,36,0.32)] bg-[rgba(251,191,36,0.08)] p-2.5">
          <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-amber)]">
            Score capped — {formatScore(uncappedScore)} → {formatScore(finalScore)}
          </div>
          {capReason && (
            <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{capReason}</p>
          )}
        </div>
      )}

      <div className="space-y-2.5">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <div className="mb-1 flex items-center justify-between text-xs text-[var(--sl-text-dim)]">
              <span>{metric.label}</span>
            </div>
            <ScoreBar value={metric.value} />
          </div>
        ))}
      </div>

      {needsReview && humanReviewReason && (
        <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] p-2.5">
          <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Human review reason
          </div>
          <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{humanReviewReason}</p>
        </div>
      )}

      {rubricBreakdown && Object.keys(rubricBreakdown).length > 0 && (
        <div>
          <div className="mb-2 sl-panel-title">Rubric breakdown</div>
          <div className="space-y-2">
            {Object.entries(rubricBreakdown).map(([criterion, score]) => (
              <div key={criterion}>
                <div className="mb-1 flex items-center justify-between text-[0.72rem] text-[var(--sl-text-dim)]">
                  <span>{humanize(criterion)}</span>
                </div>
                <ScoreBar value={typeof score === "number" ? score : null} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
