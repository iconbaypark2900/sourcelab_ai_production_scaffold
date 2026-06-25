"use client";

import { useCallback, useEffect, useState } from "react";

import {
  buildCompareDeepLink,
  comparePresetForQuickAction,
  type ComparePreset,
} from "@/lib/attempt-url";
import {
  computeAttemptTimelineSummary,
  extractAttemptAnswerText,
} from "@/lib/attempt-summary";
import { getAnswerAttempt, getAnswerDiff, SourceLabApiError } from "@/lib/sourcelab-api";
import type { AnswerAttemptDetail, AnswerAttemptSummary, AnswerDiffResponse } from "@/lib/types";
import { formatScore } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

interface AnswerDiffPanelProps {
  runId: string;
  attempts: AnswerAttemptSummary[];
  fromAttemptId?: string | null;
  toAttemptId?: string | null;
  selectedAttemptId?: string | null;
  comparePinned?: boolean;
  invalidCompareWarning?: string | null;
  onFromChange?: (attemptId: string) => void;
  onToChange?: (attemptId: string) => void;
  onQuickCompare?: (fromId: string | null, toId: string | null, preset?: ComparePreset | null) => void;
  onPinComparison?: () => void;
  onClearComparison?: () => void;
}

function deltaTone(value: number): string {
  if (value > 0.005) {
    return "text-[var(--sl-emerald)]";
  }
  if (value < -0.005) {
    return "text-[var(--sl-rose)]";
  }
  return "text-[var(--sl-text-dim)]";
}

function formatDelta(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

function DeltaRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--sl-border)] py-1.5 last:border-0">
      <span className="text-[0.72rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {label}
      </span>
      <span className={`font-mono text-xs ${deltaTone(value)}`}>{formatDelta(value)}</span>
    </div>
  );
}

function ChangeList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "green" | "amber" | "red";
}) {
  if (items.length === 0) {
    return null;
  }
  const color =
    tone === "green"
      ? "text-[var(--sl-emerald)]"
      : tone === "amber"
        ? "text-[var(--sl-amber)]"
        : "text-[var(--sl-rose)]";
  return (
    <div>
      <div className={`text-[0.66rem] uppercase tracking-[0.1em] ${color}`}>{title}</div>
      <ul className="mt-1 space-y-0.5 text-xs text-[var(--sl-text-dim)]">
        {items.map((item) => (
          <li key={item}>· {item}</li>
        ))}
      </ul>
    </div>
  );
}

function AnswerTextColumn({
  label,
  attemptId,
  text,
  score,
  needsReview,
  capReason,
  previewMode,
}: {
  label: string;
  attemptId: string;
  text: string | null;
  score: number | null | undefined;
  needsReview: boolean;
  capReason: string | null | undefined;
  previewMode: boolean;
}) {
  const charCount = text?.length ?? 0;
  const displayText =
    previewMode && text && text.length > 480 ? `${text.slice(0, 480)}…` : text;

  return (
    <div className="min-h-[6rem] rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.55)] p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
          {label}
        </div>
        <span className="font-mono text-[0.68rem] text-[var(--sl-text-dim)]">
          {attemptId.replace("attempt_", "")}
        </span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[0.68rem] text-[var(--sl-text-faint)]">
        <span className="font-mono text-white">{formatScore(score)}</span>
        {needsReview ? (
          <StatusPill tone="review" label="REVIEW" />
        ) : (
          <StatusPill tone="pass" label="CLEAR" />
        )}
        {capReason ? (
          <StatusPill tone="review" label="CAPPED" />
        ) : null}
        <span className="text-[var(--sl-text-dim)]">{charCount.toLocaleString()} chars</span>
      </div>
      {displayText ? (
        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-[var(--sl-text-dim)]">
          {displayText}
        </pre>
      ) : (
        <p className="mt-2 text-xs text-[var(--sl-text-faint)]">Answer text unavailable.</p>
      )}
    </div>
  );
}

function formatCharDelta(fromLen: number, toLen: number): string {
  const delta = toLen - fromLen;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toLocaleString()} chars (${fromLen.toLocaleString()} → ${toLen.toLocaleString()})`;
}

export default function AnswerDiffPanel({
  runId,
  attempts,
  fromAttemptId,
  toAttemptId,
  selectedAttemptId,
  comparePinned = false,
  invalidCompareWarning,
  onFromChange,
  onToChange,
  onQuickCompare,
  onPinComparison,
  onClearComparison,
}: AnswerDiffPanelProps) {
  const [diff, setDiff] = useState<AnswerDiffResponse | null>(null);
  const [fromDetail, setFromDetail] = useState<AnswerAttemptDetail | null>(null);
  const [toDetail, setToDetail] = useState<AnswerAttemptDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [answerTextLoading, setAnswerTextLoading] = useState(false);
  const [error, setError] = useState<SourceLabApiError | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [answerPreviewMode, setAnswerPreviewMode] = useState(true);

  const timeline = computeAttemptTimelineSummary(attempts, selectedAttemptId);

  const fromId =
    fromAttemptId ??
    selectedAttemptId ??
    (attempts.length >= 2 ? attempts[0].attempt_id : "");
  const toId =
    toAttemptId ??
    timeline.latestAttemptId ??
    (attempts.length >= 2 ? attempts[attempts.length - 1].attempt_id : "");

  const applyCompare = (from: string | null, to: string | null) => {
    const preset = comparePresetForQuickAction(from, to, timeline, selectedAttemptId ?? null);
    if (onQuickCompare) {
      onQuickCompare(from, to, preset);
      return;
    }
    if (from) {
      onFromChange?.(from);
    }
    if (to) {
      onToChange?.(to);
    }
  };

  const handleCopyComparisonLink = useCallback(async () => {
    if (!fromId || !toId) {
      return;
    }
    const link = buildCompareDeepLink(runId, fromId, toId, {
      attemptId: selectedAttemptId,
      tab: "diff",
    });
    try {
      await navigator.clipboard.writeText(link);
      setLinkCopied(true);
      window.setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      window.prompt("Copy comparison link:", link);
    }
  }, [runId, fromId, toId, selectedAttemptId]);

  useEffect(() => {
    if (!fromId || !toId || fromId === toId) {
      setDiff(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    getAnswerDiff(runId, fromId, toId)
      .then((result) => {
        if (!cancelled) {
          setDiff(result);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof SourceLabApiError
              ? err
              : new SourceLabApiError({
                  message: err instanceof Error ? err.message : "Diff failed",
                  status: -1,
                }),
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runId, fromId, toId]);

  useEffect(() => {
    if (!fromId || !toId || fromId === toId) {
      setFromDetail(null);
      setToDetail(null);
      return;
    }

    let cancelled = false;
    setAnswerTextLoading(true);

    Promise.all([getAnswerAttempt(runId, fromId), getAnswerAttempt(runId, toId)])
      .then(([from, to]) => {
        if (!cancelled) {
          setFromDetail(from);
          setToDetail(to);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFromDetail(null);
          setToDetail(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAnswerTextLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runId, fromId, toId]);

  const fromAnswerText = extractAttemptAnswerText(fromDetail);
  const toAnswerText = extractAttemptAnswerText(toDetail);
  const fromCharCount = fromAnswerText?.length ?? 0;
  const toCharCount = toAnswerText?.length ?? 0;
  const showAnswerComparison =
    !answerTextLoading && (fromAnswerText !== null || toAnswerText !== null);

  if (attempts.length < 2) {
    return (
      <p className="text-xs text-[var(--sl-text-faint)]">
        Submit at least two answers to compare attempts.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {invalidCompareWarning && (
        <div className="rounded-lg border border-[rgba(251,191,36,0.32)] bg-[rgba(251,191,36,0.08)] px-3 py-2 text-xs text-[var(--sl-amber)]">
          {invalidCompareWarning}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          className="sl-btn px-2 py-1 text-[0.68rem]"
          disabled={!selectedAttemptId || !timeline.latestAttemptId}
          onClick={() =>
            applyCompare(selectedAttemptId ?? null, timeline.latestAttemptId)
          }
        >
          Selected → latest
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-1 text-[0.68rem]"
          disabled={!timeline.firstAttemptId || !timeline.latestAttemptId}
          onClick={() =>
            applyCompare(timeline.firstAttemptId, timeline.latestAttemptId)
          }
        >
          First → latest
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-1 text-[0.68rem]"
          disabled={!timeline.previousAttemptId || !selectedAttemptId}
          onClick={() =>
            applyCompare(timeline.previousAttemptId, selectedAttemptId ?? null)
          }
        >
          Previous → selected
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-1 text-[0.68rem]"
          disabled={!selectedAttemptId || !timeline.bestAttemptId}
          onClick={() =>
            applyCompare(selectedAttemptId ?? null, timeline.bestAttemptId)
          }
        >
          Selected → best
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          className={`sl-btn px-2 py-1 text-[0.68rem] ${comparePinned ? "sl-btn--primary" : ""}`}
          disabled={!fromId || !toId || fromId === toId}
          onClick={() => onPinComparison?.()}
          title="Keep this comparison in the URL across refresh"
        >
          {comparePinned ? "Comparison pinned" : "Pin comparison"}
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-1 text-[0.68rem]"
          disabled={!fromId || !toId || fromId === toId}
          onClick={() => void handleCopyComparisonLink()}
        >
          {linkCopied ? "Link copied" : "Copy comparison link"}
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-1 text-[0.68rem]"
          disabled={!comparePinned}
          onClick={() => onClearComparison?.()}
        >
          Clear comparison
        </button>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <label className="block">
          <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            From (earlier)
          </span>
          <select
            value={fromId}
            onChange={(event) => onFromChange?.(event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-2 py-1.5 text-xs text-[var(--sl-text)]"
          >
            {attempts.map((a) => (
              <option key={a.attempt_id} value={a.attempt_id}>
                {a.attempt_id.replace("attempt_", "")} · {formatScore(a.overall_score)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            To (later)
          </span>
          <select
            value={toId}
            onChange={(event) => onToChange?.(event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-2 py-1.5 text-xs text-[var(--sl-text)]"
          >
            {attempts.map((a) => (
              <option key={a.attempt_id} value={a.attempt_id}>
                {a.attempt_id.replace("attempt_", "")} · {formatScore(a.overall_score)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {answerTextLoading && (
        <p className="text-xs text-[var(--sl-text-faint)]">Loading answer text…</p>
      )}

      {showAnswerComparison && (
        <div className="space-y-2 rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] p-3.5">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                Answer text comparison
              </div>
              {diff && (
                <div className={`mt-1 text-sm font-semibold ${deltaTone(diff.score_delta)}`}>
                  Score {formatDelta(diff.score_delta)} ·{" "}
                  {formatScore(diff.from_overall_score)} → {formatScore(diff.to_overall_score)}
                </div>
              )}
              {(fromAnswerText !== null || toAnswerText !== null) && (
                <div className="mt-1 text-[0.68rem] text-[var(--sl-text-dim)]">
                  Length {formatCharDelta(fromCharCount, toCharCount)}
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className={`sl-btn px-2 py-0.5 text-[0.68rem] ${answerPreviewMode ? "sl-btn--primary" : ""}`}
                onClick={() => setAnswerPreviewMode(true)}
              >
                Preview
              </button>
              <button
                type="button"
                className={`sl-btn px-2 py-0.5 text-[0.68rem] ${!answerPreviewMode ? "sl-btn--primary" : ""}`}
                onClick={() => setAnswerPreviewMode(false)}
              >
                Full text
              </button>
              {diff && (diff.needs_review_changed || diff.cap_reason_changed) && (
                <div className="text-right text-[0.68rem] text-[var(--sl-text-dim)]">
                  {diff.needs_review_changed && (
                    <div>
                      Review: {diff.from_needs_review ? "Needs review" : "Clear"} →{" "}
                      {diff.to_needs_review ? "Needs review" : "Clear"}
                    </div>
                  )}
                  {diff.cap_reason_changed && (
                    <div>
                      Cap: {diff.from_cap_reason || "(none)"} → {diff.to_cap_reason || "(none)"}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <AnswerTextColumn
              label="From answer"
              attemptId={fromId}
              text={fromAnswerText}
              score={fromDetail?.answer_review?.overall_score ?? diff?.from_overall_score}
              needsReview={
                fromDetail?.answer_review?.needs_review ?? diff?.from_needs_review ?? false
              }
              capReason={
                fromDetail?.answer_review?.cap_reason ?? diff?.from_cap_reason ?? null
              }
              previewMode={answerPreviewMode}
            />
            <AnswerTextColumn
              label="To answer"
              attemptId={toId}
              text={toAnswerText}
              score={toDetail?.answer_review?.overall_score ?? diff?.to_overall_score}
              needsReview={toDetail?.answer_review?.needs_review ?? diff?.to_needs_review ?? false}
              capReason={toDetail?.answer_review?.cap_reason ?? diff?.to_cap_reason ?? null}
              previewMode={answerPreviewMode}
            />
          </div>

          {diff &&
            (diff.strengths_added.length > 0 ||
              diff.strengths_removed.length > 0 ||
              diff.weaknesses_added.length > 0 ||
              diff.weaknesses_removed.length > 0) && (
              <div className="grid gap-3 border-t border-[var(--sl-border)] pt-3 sm:grid-cols-2">
                <ChangeList title="Strengths added" items={diff.strengths_added} tone="green" />
                <ChangeList title="Strengths removed" items={diff.strengths_removed} tone="red" />
                <ChangeList title="Weaknesses added" items={diff.weaknesses_added} tone="red" />
                <ChangeList
                  title="Weaknesses resolved"
                  items={diff.weaknesses_removed}
                  tone="green"
                />
              </div>
            )}
        </div>
      )}

      {!showAnswerComparison && !answerTextLoading && fromId && toId && fromId !== toId && (
        <p className="text-xs text-[var(--sl-text-faint)]">
          Answer text comparison unavailable for this pair.
        </p>
      )}

      {loading && <p className="text-xs text-[var(--sl-text-faint)]">Computing diff…</p>}

      {error && (
        <div className="rounded-lg border border-[rgba(244,63,94,0.32)] bg-[rgba(244,63,94,0.08)] p-3">
          <p className="text-xs text-[var(--sl-text-dim)]">{error.message}</p>
        </div>
      )}

      {diff && !loading && (
        <div className="space-y-3 rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] p-3.5">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                Score change
              </div>
              <div className={`text-2xl font-semibold ${deltaTone(diff.score_delta)}`}>
                {formatDelta(diff.score_delta)}
              </div>
            </div>
            <div className="text-right text-xs text-[var(--sl-text-dim)]">
              {formatScore(diff.from_overall_score)} → {formatScore(diff.to_overall_score)}
            </div>
          </div>

          <div className="space-y-0">
            <DeltaRow label="Rubric alignment" value={diff.rubric_alignment_delta} />
            <DeltaRow label="Uncapped score" value={diff.uncapped_delta} />
            <DeltaRow label="Source grounding" value={diff.grounding_delta} />
          </div>

          {diff.needs_review_changed && (
            <div className="rounded-lg border border-[rgba(251,191,36,0.32)] bg-[rgba(251,191,36,0.08)] p-2.5">
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-amber)]">
                Review status changed
              </div>
              <p className="mt-1 text-xs text-[var(--sl-text-dim)]">
                {diff.from_needs_review ? "Needs review" : "Clear"} →{" "}
                {diff.to_needs_review ? "Needs review" : "Clear"}
              </p>
            </div>
          )}

          {diff.cap_reason_changed && (
            <div className="rounded-lg border border-[rgba(251,191,36,0.32)] bg-[rgba(251,191,36,0.08)] p-2.5">
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-amber)]">
                Cap reason changed
              </div>
              <p className="mt-1 text-xs text-[var(--sl-text-dim)]">
                {diff.from_cap_reason || "(none)"} → {diff.to_cap_reason || "(none)"}
              </p>
            </div>
          )}

          {diff.next_task_changed && (
            <div className="rounded-lg border border-[rgba(168,85,247,0.28)] bg-[rgba(168,85,247,0.07)] p-2.5">
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-violet)]">
                Next task changed
              </div>
              <p className="mt-1 text-xs text-[var(--sl-text-dim)]">
                {diff.from_next_task_focus || "—"} → {diff.to_next_task_focus || "—"}
              </p>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <ChangeList title="Strengths added" items={diff.strengths_added} tone="green" />
            <ChangeList title="Strengths removed" items={diff.strengths_removed} tone="red" />
            <ChangeList title="Weaknesses added" items={diff.weaknesses_added} tone="red" />
            <ChangeList title="Weaknesses resolved" items={diff.weaknesses_removed} tone="green" />
          </div>
        </div>
      )}
    </div>
  );
}
