"use client";

import type { AnswerAttemptSummary } from "@/lib/types";

interface AttemptScoreSparklineProps {
  attempts: AnswerAttemptSummary[];
  selectedAttemptId?: string | null;
  latestAttemptId?: string | null;
  bestAttemptId?: string | null;
  /** Keyboard/hover focus highlight (may differ from selected). */
  focusedAttemptId?: string | null;
  onSelectAttempt?: (attemptId: string) => void;
}

const WIDTH = 280;
const HEIGHT = 56;
const PAD_X = 8;
const PAD_Y = 10;

function shortId(attemptId: string): string {
  return attemptId.replace("attempt_", "");
}

/**
 * Lightweight SVG score sparkline — no charting library.
 * Shows overall score trajectory with optional uncapped overlay and markers.
 */
export default function AttemptScoreSparkline({
  attempts,
  selectedAttemptId,
  latestAttemptId,
  bestAttemptId,
  focusedAttemptId,
  onSelectAttempt,
}: AttemptScoreSparklineProps) {
  if (attempts.length === 0) {
    return <p className="text-xs text-[var(--sl-text-faint)]">No attempts yet.</p>;
  }

  const plotWidth = WIDTH - PAD_X * 2;
  const plotHeight = HEIGHT - PAD_Y * 2;

  const scores = attempts.map((a) => a.overall_score);
  const uncapped = attempts.map((a) => a.uncapped_score);
  const minScore = Math.min(...scores, ...uncapped, 0);
  const maxScore = Math.max(...scores, ...uncapped, 1);
  const range = Math.max(maxScore - minScore, 0.05);

  const xAt = (index: number) =>
    attempts.length === 1
      ? PAD_X + plotWidth / 2
      : PAD_X + (index / (attempts.length - 1)) * plotWidth;

  const yAt = (score: number) =>
    PAD_Y + plotHeight - ((score - minScore) / range) * plotHeight;

  const overallPoints = attempts
    .map((attempt, index) => `${xAt(index)},${yAt(attempt.overall_score)}`)
    .join(" ");

  const uncappedPoints = attempts
    .map((attempt, index) => `${xAt(index)},${yAt(attempt.uncapped_score)}`)
    .join(" ");

  const showUncapped = attempts.some(
    (a) => Math.abs(a.uncapped_score - a.overall_score) > 0.005,
  );

  return (
    <div className="space-y-1">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-14 w-full"
        role="img"
        aria-label="Answer attempt score sparkline"
      >
        {/* Baseline grid */}
        <line
          x1={PAD_X}
          y1={yAt(minScore)}
          x2={WIDTH - PAD_X}
          y2={yAt(minScore)}
          stroke="rgba(148,163,184,0.15)"
          strokeWidth="1"
        />
        <line
          x1={PAD_X}
          y1={yAt(maxScore)}
          x2={WIDTH - PAD_X}
          y2={yAt(maxScore)}
          stroke="rgba(148,163,184,0.1)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />

        {showUncapped && (
          <polyline
            points={uncappedPoints}
            fill="none"
            stroke="rgba(251,191,36,0.45)"
            strokeWidth="1.25"
            strokeDasharray="4 3"
          />
        )}

        <polyline
          points={overallPoints}
          fill="none"
          stroke="rgba(34,211,238,0.85)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {attempts.map((attempt, index) => {
          const cx = xAt(index);
          const cy = yAt(attempt.overall_score);
          const isSelected = attempt.attempt_id === selectedAttemptId;
          const isFocused = attempt.attempt_id === (focusedAttemptId ?? selectedAttemptId);
          const isLatest = attempt.attempt_id === latestAttemptId;
          const isBest = attempt.attempt_id === bestAttemptId;
          const needsReview = attempt.needs_review;
          const capped = Boolean(attempt.cap_reason);

          let fill = "rgba(34,211,238,0.9)";
          let radius = 3.5;
          if (needsReview) {
            fill = "rgba(251,191,36,0.95)";
          }
          if (capped && !needsReview) {
            fill = "rgba(251,191,36,0.75)";
          }
          if (isBest) {
            fill = "rgba(52,211,153,0.95)";
            radius = 4.5;
          }
          if (isLatest) {
            fill = "rgba(34,211,238,1)";
            radius = 4;
          }
          if (isSelected) {
            fill = "rgba(168,85,247,1)";
            radius = 5;
          }

          return (
            <g key={attempt.attempt_id}>
              {(isSelected || isFocused) && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={isFocused && !isSelected ? 9 : 8}
                  fill={
                    isFocused && !isSelected
                      ? "rgba(168,85,247,0.12)"
                      : "rgba(168,85,247,0.18)"
                  }
                  stroke={
                    isFocused && !isSelected
                      ? "rgba(168,85,247,0.75)"
                      : "rgba(168,85,247,0.55)"
                  }
                  strokeWidth={isFocused && !isSelected ? 1.5 : 1}
                />
              )}
              {onSelectAttempt && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={14}
                  fill="transparent"
                  className="cursor-pointer"
                  aria-hidden="true"
                  onClick={() => onSelectAttempt(attempt.attempt_id)}
                />
              )}
              <circle
                cx={cx}
                cy={cy}
                r={radius}
                fill={fill}
                pointerEvents={onSelectAttempt ? "none" : undefined}
                tabIndex={onSelectAttempt ? 0 : undefined}
                role={onSelectAttempt ? "button" : undefined}
                aria-label={
                  onSelectAttempt
                    ? `${shortId(attempt.attempt_id)} score ${(attempt.overall_score * 100).toFixed(1)} percent`
                    : undefined
                }
                className={
                  onSelectAttempt
                    ? "outline-none focus-visible:[stroke:rgba(168,85,247,1)] focus-visible:[stroke-width:2]"
                    : undefined
                }
                onKeyDown={
                  onSelectAttempt
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onSelectAttempt(attempt.attempt_id);
                        }
                      }
                    : undefined
                }
              >
                <title>
                  {shortId(attempt.attempt_id)} · {(attempt.overall_score * 100).toFixed(1)}%
                  {needsReview ? " · needs review" : ""}
                  {capped ? " · capped" : ""}
                </title>
              </circle>
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[0.62rem] text-[var(--sl-text-faint)]">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-1.5 w-3 rounded bg-[rgba(34,211,238,0.85)]" />
          overall
        </span>
        {showUncapped && (
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-0 w-3 border-t border-dashed border-[rgba(251,191,36,0.7)]" />
            uncapped
          </span>
        )}
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[rgba(168,85,247,1)]" />
          selected
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[rgba(52,211,153,0.95)]" />
          best
        </span>
      </div>
    </div>
  );
}
