"use client";

import { useEffect, useState } from "react";

import type {
  AnswerAttemptDetail,
  AnswerCriterionScore,
  SourceGroundingReview,
} from "@/lib/types";
import { formatScore, humanize } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

interface AttemptDetailPanelProps {
  detail: AnswerAttemptDetail;
  runId?: string;
  note?: string;
  onSaveNote?: (note: string) => void;
  noteLastSavedAt?: string | null;
}

function ScoreCard({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] px-3 py-2">
      <div className="text-[0.62rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
        {label}
      </div>
      <div className="mt-0.5 font-mono text-lg font-semibold sl-gradient-text">
        {formatScore(value)}
      </div>
    </div>
  );
}

function RawArtifactExpander({
  title,
  value,
}: {
  title: string;
  value: unknown;
}) {
  if (value === null || value === undefined) {
    return null;
  }
  const isEmptyObject =
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value as object).length === 0;
  const isEmptyString = typeof value === "string" && value.trim() === "";
  if (isEmptyObject || isEmptyString) {
    return null;
  }

  return (
    <details className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.35)]">
      <summary className="cursor-pointer list-none px-3 py-2 text-[0.72rem] font-medium text-[var(--sl-text-dim)]">
        {title}
      </summary>
      <div className="border-t border-[var(--sl-border)] px-3 py-2">
        <pre className="sl-code max-h-64 overflow-auto text-[0.68rem]">
          {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
        </pre>
      </div>
    </details>
  );
}

function asCriterionScores(review: AnswerAttemptDetail["answer_review"]): AnswerCriterionScore[] {
  const scores = review?.criterion_scores;
  if (!Array.isArray(scores)) {
    return [];
  }
  return scores.filter(
    (item): item is AnswerCriterionScore =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as AnswerCriterionScore).criterion_name === "string",
  );
}

function asGroundingReview(
  value: AnswerAttemptDetail["source_grounding_review"],
): SourceGroundingReview | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  return value as SourceGroundingReview;
}

export default function AttemptDetailPanel({
  detail,
  note = "",
  onSaveNote,
  noteLastSavedAt,
}: AttemptDetailPanelProps) {
  const [showFullAnswer, setShowFullAnswer] = useState(false);
  const [draftNote, setDraftNote] = useState(note);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    setDraftNote(note);
  }, [note, detail.attempt_id]);

  useEffect(() => {
    if (!onSaveNote) {
      return;
    }
    const handle = window.setTimeout(() => {
      if (draftNote.trim() !== note.trim()) {
        onSaveNote(draftNote);
        setSavedFlash(true);
        window.setTimeout(() => setSavedFlash(false), 2000);
      }
    }, 600);
    return () => window.clearTimeout(handle);
  }, [draftNote, note, onSaveNote]);

  const { manifest, answer_review: review, learning_report: report } = detail;
  const submission = detail.answer_submission ?? {};
  const grounding = asGroundingReview(detail.source_grounding_review);
  const nextTask = detail.next_task_decision ?? {};

  const answerText =
    typeof submission.answer_text === "string" ? submission.answer_text : "";
  const previewLimit = 280;
  const needsTruncate = answerText.length > previewLimit;
  const displayAnswer =
    showFullAnswer || !needsTruncate
      ? answerText
      : `${answerText.slice(0, previewLimit).trim()}…`;

  const finalScore =
    typeof review?.overall_score === "number"
      ? review.overall_score
      : manifest.overall_score;
  const uncapped =
    typeof review?.uncapped_score === "number"
      ? review.uncapped_score
      : manifest.uncapped_score;
  const capped = uncapped > finalScore + 1e-9;

  const rubricScores = asCriterionScores(review);
  const strengths = Array.isArray(review?.strengths) ? review.strengths : [];
  const weaknesses = Array.isArray(review?.weaknesses) ? review.weaknesses : [];

  const capReason =
    (typeof review?.cap_reason === "string" && review.cap_reason) ||
    manifest.cap_reason ||
    "";
  const humanReviewReason =
    (typeof review?.review_reason === "string" && review.review_reason) ||
    manifest.human_review_reason ||
    "";

  const conceptOverlapScore =
    typeof grounding?.source_grounding_score === "number"
      ? grounding.source_grounding_score
      : null;
  const rubricGroundingScore =
    typeof review?.source_grounding_score === "number"
      ? review.source_grounding_score
      : null;

  const matchedConcepts = grounding?.matched_source_concepts ?? null;
  const totalConcepts = grounding?.total_source_concepts ?? null;
  const citedCoverage =
    matchedConcepts !== null &&
    totalConcepts !== null &&
    totalConcepts > 0
      ? matchedConcepts / totalConcepts
      : null;

  const unsupportedPhrases = grounding?.unsupported_phrases ?? [];

  return (
    <div className="mt-4 space-y-4 rounded-xl border border-[rgba(34,211,238,0.22)] bg-[rgba(9,14,28,0.55)] p-3.5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[0.62rem] uppercase tracking-[0.12em] text-[var(--sl-text-faint)]">
            Attempt detail
          </div>
          <div className="font-mono text-sm text-white">
            {detail.attempt_id.replace("attempt_", "")}
          </div>
          {manifest.created_at && (
            <div className="mt-0.5 text-[0.68rem] text-[var(--sl-text-faint)]">
              {manifest.created_at}
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-xl font-semibold sl-gradient-text">
            {formatScore(finalScore)}
          </span>
          {manifest.needs_review || review?.needs_review ? (
            <StatusPill tone="review" label="NEEDS REVIEW" />
          ) : (
            <StatusPill tone="pass" label="CLEAR" />
          )}
          {capped && <StatusPill tone="review" label="CAPPED" />}
        </div>
      </div>

      {onSaveNote && (
        <div className="space-y-2 rounded-lg border border-[rgba(168,85,247,0.22)] bg-[rgba(168,85,247,0.06)] p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="sl-panel-title">Private note</div>
            {(savedFlash || noteLastSavedAt) && (
              <span className="text-[0.66rem] text-[var(--sl-emerald)]">
                {savedFlash ? "Saved locally" : "Saved locally"}
              </span>
            )}
          </div>
          <p className="text-[0.66rem] leading-relaxed text-[var(--sl-text-faint)]">
            Browser-only annotation — not synced, not part of proof artifacts or run exports.
          </p>
          <textarea
            value={draftNote}
            onChange={(event) => setDraftNote(event.target.value)}
            rows={3}
            placeholder="Your review notes for this attempt…"
            className="w-full rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.55)] px-3 py-2 text-xs text-[var(--sl-text)] placeholder:text-[var(--sl-text-faint)]"
          />
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="sl-btn px-2 py-0.5 text-[0.68rem]"
              onClick={() => {
                onSaveNote(draftNote);
                setSavedFlash(true);
                window.setTimeout(() => setSavedFlash(false), 2000);
              }}
            >
              Save note
            </button>
          </div>
        </div>
      )}

      {/* Score cards */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <ScoreCard label="Final score" value={finalScore} />
        <ScoreCard
          label="Rubric alignment"
          value={
            typeof review?.rubric_alignment_score === "number"
              ? review.rubric_alignment_score
              : manifest.rubric_alignment_score
          }
        />
        <ScoreCard label="Uncapped score" value={uncapped} />
        <ScoreCard label="Grounding (rubric)" value={rubricGroundingScore} />
        <ScoreCard label="Concept overlap" value={conceptOverlapScore} />
      </div>

      {/* Review */}
      {(capReason || humanReviewReason || strengths.length > 0 || weaknesses.length > 0) && (
        <div className="space-y-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] p-3">
          <div className="sl-panel-title">Review</div>
          {capReason && (
            <p className="text-xs text-[var(--sl-amber)]">
              <span className="font-medium">Cap reason:</span> {capReason}
            </p>
          )}
          {humanReviewReason && (
            <p className="text-xs text-[var(--sl-text-dim)]">
              <span className="font-medium">Human review:</span> {humanReviewReason}
            </p>
          )}
          {strengths.length > 0 && (
            <div>
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-emerald)]">
                Strengths
              </div>
              <ul className="mt-1 space-y-0.5 text-xs text-[var(--sl-text-dim)]">
                {strengths.map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            </div>
          )}
          {weaknesses.length > 0 && (
            <div>
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-rose)]">
                Weaknesses
              </div>
              <ul className="mt-1 space-y-0.5 text-xs text-[var(--sl-text-dim)]">
                {weaknesses.map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Submitted answer */}
      {answerText && (
        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="sl-panel-title">Submitted answer</div>
            {needsTruncate && (
              <button
                type="button"
                className="sl-btn px-2 py-0.5 text-[0.68rem]"
                onClick={() => setShowFullAnswer((prev) => !prev)}
              >
                {showFullAnswer ? "Show preview" : "Show full answer"}
              </button>
            )}
          </div>
          <pre className="sl-code max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-relaxed">
            {displayAnswer}
          </pre>
        </div>
      )}

      {/* Rubric breakdown */}
      {rubricScores.length > 0 && (
        <div>
          <div className="mb-2 sl-panel-title">Rubric breakdown</div>
          <div className="space-y-2">
            {rubricScores.map((criterion) => {
              const contribution = criterion.weight * criterion.score;
              return (
                <div
                  key={criterion.criterion_name}
                  className="rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.4)] px-3 py-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-medium text-white">
                      {humanize(criterion.criterion_name)}
                    </span>
                    <span className="font-mono text-xs sl-gradient-text">
                      {formatScore(criterion.score)}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 text-[0.68rem] text-[var(--sl-text-faint)]">
                    <span>weight {formatScore(criterion.weight, 0)}</span>
                    <span>contribution {formatScore(contribution)}</span>
                  </div>
                  {criterion.feedback && (
                    <p className="mt-1 text-[0.68rem] text-[var(--sl-text-dim)]">
                      {criterion.feedback}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Grounding */}
      {grounding && (
        <div className="space-y-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.4)] p-3">
          <div className="sl-panel-title">Grounding</div>
          <div className="grid gap-2 sm:grid-cols-2">
            <ScoreCard label="Rubric grounding" value={rubricGroundingScore} />
            <ScoreCard label="Concept overlap" value={conceptOverlapScore} />
          </div>
          {citedCoverage !== null && (
            <p className="text-xs text-[var(--sl-text-dim)]">
              Cited coverage: {formatScore(citedCoverage)} ({matchedConcepts} / {totalConcepts}{" "}
              concepts)
            </p>
          )}
          {unsupportedPhrases.length > 0 && (
            <div>
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-amber)]">
                Weak evidence phrases
              </div>
              <ul className="mt-1 max-h-24 space-y-0.5 overflow-auto text-[0.68rem] text-[var(--sl-text-dim)]">
                {unsupportedPhrases.slice(0, 8).map((phrase) => (
                  <li key={phrase}>· {phrase}</li>
                ))}
                {unsupportedPhrases.length > 8 && (
                  <li className="text-[var(--sl-text-faint)]">
                    +{unsupportedPhrases.length - 8} more
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Next task */}
      {(nextTask.focus || nextTask.reason || nextTask.task_format) && (
        <div className="rounded-lg border border-[rgba(168,85,247,0.28)] bg-[rgba(168,85,247,0.07)] p-3">
          <div className="sl-panel-title">Next task</div>
          {nextTask.focus && (
            <div className="text-sm font-medium text-white">{nextTask.focus}</div>
          )}
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {nextTask.task_format && (
              <span className="sl-pill sl-pill--neutral">{humanize(nextTask.task_format)}</span>
            )}
            {typeof nextTask.difficulty === "number" && (
              <span className="sl-pill sl-pill--neutral">difficulty {nextTask.difficulty}</span>
            )}
          </div>
          {nextTask.reason && (
            <p className="mt-2 text-xs leading-relaxed text-[var(--sl-text-dim)]">
              {nextTask.reason}
            </p>
          )}
        </div>
      )}

      {/* Raw artifacts */}
      <div className="space-y-1.5">
        <div className="sl-panel-title">Raw artifacts</div>
        <RawArtifactExpander title="attempt_manifest.json" value={detail.manifest} />
        <RawArtifactExpander title="answer_submission.json" value={detail.answer_submission} />
        <RawArtifactExpander title="answer_review.json" value={detail.answer_review} />
        <RawArtifactExpander
          title="source_grounding_review.json"
          value={detail.source_grounding_review}
        />
        <RawArtifactExpander title="learning_report.json" value={detail.learning_report} />
        <RawArtifactExpander title="next_task_decision.json" value={detail.next_task_decision} />
        {detail.artifact_names.length > 0 && (
          <p className="text-[0.66rem] text-[var(--sl-text-faint)]">
            On disk: {detail.artifact_names.join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}
