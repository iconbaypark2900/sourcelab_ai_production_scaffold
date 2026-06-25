"use client";

import { useEffect, useMemo, useState } from "react";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import { extractAttemptAnswerText } from "@/lib/attempt-summary";
import {
  buildAttemptSelectOptions,
  computeCrossRunAnswerDiff,
  resolveRunAttemptId,
  type AttemptSelection,
  type CrossRunDiffPreset,
} from "@/lib/batch-run";
import { formatScore } from "@/lib/format";
import { getAnswerAttempt, getAnswerHistory, SourceLabApiError } from "@/lib/sourcelab-api";
import type { AnswerAttemptDetail, AnswerAttemptSummary, AnswerComparePerRun } from "@/lib/types";

interface CrossRunAnswerDiffPanelProps {
  perRun: AnswerComparePerRun[];
  preset?: CrossRunDiffPreset | null;
  onPresetConsumed?: () => void;
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

function formatCharDelta(fromLen: number, toLen: number): string {
  const delta = toLen - fromLen;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toLocaleString()} chars`;
}

function AttemptSideCard({
  label,
  runId,
  topic,
  attemptId,
  detail,
  answerText,
  previewMode,
}: {
  label: string;
  runId: string;
  topic: string;
  attemptId: string;
  detail: AnswerAttemptDetail | null;
  answerText: string | null;
  previewMode: boolean;
}) {
  const review = detail?.answer_review;
  const displayText =
    previewMode && answerText && answerText.length > 480
      ? `${answerText.slice(0, 480)}…`
      : answerText;

  return (
    <div className="min-h-[8rem] rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.55)] p-2.5">
      <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-xs text-[var(--sl-cyan)]">{runId}</div>
      <div className="truncate text-sm text-[var(--sl-text-dim)]">{topic}</div>
      <div className="mt-1 font-mono text-[0.68rem] text-[var(--sl-text-faint)]">
        {attemptId.replace("attempt_", "")}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5 text-[0.68rem]">
        <span className="font-mono text-white">
          {formatScore(review?.overall_score ?? detail?.manifest.overall_score)}
        </span>
        <span className="text-[var(--sl-text-faint)]">
          Rubric {formatScore(review?.rubric_alignment_score ?? detail?.manifest.rubric_alignment_score)}
        </span>
        <span className="text-[var(--sl-text-faint)]">
          Uncapped {formatScore(review?.uncapped_score ?? detail?.manifest.uncapped_score)}
        </span>
        {(review?.needs_review ?? detail?.manifest.needs_review) ? (
          <StatusPill tone="review" label="REVIEW" dot={false} />
        ) : (
          <StatusPill tone="pass" label="CLEAR" dot={false} />
        )}
        {(review?.cap_reason ?? detail?.manifest.cap_reason) && (
          <StatusPill tone="blocked" label="CAPPED" dot={false} />
        )}
      </div>
      {(review?.cap_reason ?? detail?.manifest.cap_reason) && (
        <p className="mt-1 text-xs text-[var(--sl-amber)]">
          Cap: {review?.cap_reason ?? detail?.manifest.cap_reason}
        </p>
      )}
      <p className="mt-1 text-xs text-[var(--sl-text-faint)]">
        Focus: {review?.recommended_focus ?? detail?.manifest.next_task_focus ?? "—"}
      </p>
      {displayText ? (
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-[var(--sl-text-dim)]">
          {displayText}
        </pre>
      ) : (
        <p className="mt-2 text-xs text-[var(--sl-text-faint)]">Answer text unavailable.</p>
      )}
      {(review?.strengths?.length ?? 0) > 0 && (
        <div className="mt-2">
          <div className="text-[0.62rem] uppercase text-[var(--sl-emerald)]">Strengths</div>
          <ul className="mt-0.5 list-disc pl-4 text-xs text-[var(--sl-text-dim)]">
            {review?.strengths?.slice(0, 3).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {(review?.weaknesses?.length ?? 0) > 0 && (
        <div className="mt-2">
          <div className="text-[0.62rem] uppercase text-[var(--sl-rose)]">Weaknesses</div>
          <ul className="mt-0.5 list-disc pl-4 text-xs text-[var(--sl-text-dim)]">
            {review?.weaknesses?.slice(0, 3).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function CrossRunAnswerDiffPanel({
  perRun,
  preset,
  onPresetConsumed,
}: CrossRunAnswerDiffPanelProps) {
  const runsWithAttempts = useMemo(
    () => perRun.filter((row) => row.attempt_count > 0),
    [perRun],
  );

  const [runAId, setRunAId] = useState("");
  const [runBId, setRunBId] = useState("");
  const [attemptASelection, setAttemptASelection] = useState<AttemptSelection>("latest");
  const [attemptBSelection, setAttemptBSelection] = useState<AttemptSelection>("best");
  const [previewMode, setPreviewMode] = useState(true);
  const [detailA, setDetailA] = useState<AnswerAttemptDetail | null>(null);
  const [detailB, setDetailB] = useState<AnswerAttemptDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyCache, setHistoryCache] = useState<Record<string, AnswerAttemptSummary[]>>({});
  const [historyErrors, setHistoryErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (runsWithAttempts.length >= 2) {
      setRunAId((current) => current || runsWithAttempts[0].run_id);
      setRunBId((current) => current || runsWithAttempts[1].run_id);
    }
  }, [runsWithAttempts]);

  useEffect(() => {
    if (!preset) {
      return;
    }
    setRunAId(preset.runAId);
    setRunBId(preset.runBId);
    setAttemptASelection(preset.attemptA);
    setAttemptBSelection(preset.attemptB);
    onPresetConsumed?.();
    window.requestAnimationFrame(() => {
      document.getElementById("cross-run-answer-diff")?.scrollIntoView({ behavior: "smooth" });
    });
  }, [preset, onPresetConsumed]);

  useEffect(() => {
    if (!runAId || historyCache[runAId] !== undefined || historyErrors[runAId]) {
      return;
    }

    let cancelled = false;
    getAnswerHistory(runAId)
      .then((response) => {
        if (!cancelled) {
          setHistoryCache((prev) => ({ ...prev, [runAId]: response.attempts }));
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          const message =
            cause instanceof SourceLabApiError
              ? cause.message
              : cause instanceof Error
                ? cause.message
                : "Failed to load attempt history.";
          setHistoryErrors((prev) => ({ ...prev, [runAId]: message }));
          setHistoryCache((prev) => ({ ...prev, [runAId]: prev[runAId] ?? [] }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runAId, historyCache, historyErrors]);

  useEffect(() => {
    if (!runBId || historyCache[runBId] !== undefined || historyErrors[runBId]) {
      return;
    }

    let cancelled = false;
    getAnswerHistory(runBId)
      .then((response) => {
        if (!cancelled) {
          setHistoryCache((prev) => ({ ...prev, [runBId]: response.attempts }));
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          const message =
            cause instanceof SourceLabApiError
              ? cause.message
              : cause instanceof Error
                ? cause.message
                : "Failed to load attempt history.";
          setHistoryErrors((prev) => ({ ...prev, [runBId]: message }));
          setHistoryCache((prev) => ({ ...prev, [runBId]: prev[runBId] ?? [] }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runBId, historyCache, historyErrors]);

  const rowA = perRun.find((row) => row.run_id === runAId) ?? null;
  const rowB = perRun.find((row) => row.run_id === runBId) ?? null;
  const attemptAId = rowA ? resolveRunAttemptId(rowA, attemptASelection) : null;
  const attemptBId = rowB ? resolveRunAttemptId(rowB, attemptBSelection) : null;

  const attemptAOptions = useMemo(
    () => buildAttemptSelectOptions(historyCache[runAId] ?? []),
    [historyCache, runAId],
  );
  const attemptBOptions = useMemo(
    () => buildAttemptSelectOptions(historyCache[runBId] ?? []),
    [historyCache, runBId],
  );

  useEffect(() => {
    if (!runAId || !runBId || !attemptAId || !attemptBId) {
      setDetailA(null);
      setDetailB(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([getAnswerAttempt(runAId, attemptAId), getAnswerAttempt(runBId, attemptBId)])
      .then(([a, b]) => {
        if (!cancelled) {
          setDetailA(a);
          setDetailB(b);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setDetailA(null);
          setDetailB(null);
          setError(
            cause instanceof SourceLabApiError
              ? cause.message
              : cause instanceof Error
                ? cause.message
                : "Failed to load attempt details.",
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
  }, [runAId, runBId, attemptAId, attemptBId]);

  const answerTextA = extractAttemptAnswerText(detailA);
  const answerTextB = extractAttemptAnswerText(detailB);
  const diff =
    detailA && detailB ? computeCrossRunAnswerDiff(detailA, detailB, answerTextA, answerTextB) : null;

  if (runsWithAttempts.length < 2) {
    return (
      <Panel title="Cross-run answer diff" id="cross-run-answer-diff">
        <p className="text-sm text-[var(--sl-text-dim)]">
          At least two runs with answer attempts are required for cross-run comparison.
        </p>
      </Panel>
    );
  }

  return (
    <Panel title="Cross-run answer diff" glow="cyan" id="cross-run-answer-diff">
      <p className="mb-3 text-sm text-[var(--sl-text-dim)]">
        Compare learner attempts across two runs in this batch. Per-run attempt history loads via
        GET /learning/answers/&#123;run_id&#125;; detail fetches only the selected attempt.
      </p>

      <div className="mb-3 grid gap-2 lg:grid-cols-2">
        <label className="block">
          <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Run A
          </span>
          <select
            value={runAId}
            onChange={(event) => setRunAId(event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-2 py-1.5 text-xs"
          >
            {runsWithAttempts.map((row) => (
              <option key={row.run_id} value={row.run_id}>
                {row.run_id} · {row.topic.slice(0, 40)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Run B
          </span>
          <select
            value={runBId}
            onChange={(event) => setRunBId(event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-2 py-1.5 text-xs"
          >
            {runsWithAttempts.map((row) => (
              <option key={row.run_id} value={row.run_id}>
                {row.run_id} · {row.topic.slice(0, 40)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Attempt A
          </span>
          <select
            value={attemptASelection}
            onChange={(event) => setAttemptASelection(event.target.value as AttemptSelection)}
            className="mt-1 w-full rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-2 py-1.5 text-xs"
          >
            {attemptAOptions.map((option) => (
              <option key={`a-${option.value}`} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {historyErrors[runAId] && (
            <p className="mt-1 text-xs text-[var(--sl-amber)]">
              History unavailable — using latest/best shortcuts only.
            </p>
          )}
          {(historyCache[runAId]?.length ?? 0) === 0 && !historyErrors[runAId] && runAId && (
            <p className="mt-1 text-xs text-[var(--sl-text-faint)]">No attempts found for this run.</p>
          )}
        </label>
        <label className="block">
          <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Attempt B
          </span>
          <select
            value={attemptBSelection}
            onChange={(event) => setAttemptBSelection(event.target.value as AttemptSelection)}
            className="mt-1 w-full rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-2 py-1.5 text-xs"
          >
            {attemptBOptions.map((option) => (
              <option key={`b-${option.value}`} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {historyErrors[runBId] && (
            <p className="mt-1 text-xs text-[var(--sl-amber)]">
              History unavailable — using latest/best shortcuts only.
            </p>
          )}
          {(historyCache[runBId]?.length ?? 0) === 0 && !historyErrors[runBId] && runBId && (
            <p className="mt-1 text-xs text-[var(--sl-text-faint)]">No attempts found for this run.</p>
          )}
        </label>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          className={`sl-btn text-xs ${previewMode ? "sl-btn--primary" : ""}`}
          onClick={() => setPreviewMode(true)}
        >
          Preview
        </button>
        <button
          type="button"
          className={`sl-btn text-xs ${!previewMode ? "sl-btn--primary" : ""}`}
          onClick={() => setPreviewMode(false)}
        >
          Full text
        </button>
      </div>

      {loading && <p className="mb-2 text-xs text-[var(--sl-text-faint)]">Loading attempts…</p>}
      {error && <p className="mb-2 text-sm text-[var(--sl-rose)]">{error}</p>}

      {diff && attemptAId && attemptBId && (
        <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <DeltaCard label="Score" value={formatDelta(diff.scoreDelta)} tone={diff.scoreDelta} />
          <DeltaCard
            label="Rubric"
            value={formatDelta(diff.rubricDelta)}
            tone={diff.rubricDelta}
          />
          <DeltaCard
            label="Uncapped"
            value={formatDelta(diff.uncappedDelta)}
            tone={diff.uncappedDelta}
          />
          <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2">
            <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
              Review changed
            </div>
            <div className="mt-1 text-sm text-white">
              {diff.reviewChanged
                ? `${diff.fromNeedsReview ? "Review" : "Clear"} → ${diff.toNeedsReview ? "Review" : "Clear"}`
                : "No change"}
            </div>
          </div>
          <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2">
            <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
              Answer length
            </div>
            <div className={`mt-1 text-sm font-mono ${deltaTone(diff.answerLengthDelta)}`}>
              {formatCharDelta(diff.fromAnswerLength, diff.toAnswerLength)}
            </div>
          </div>
        </div>
      )}

      {attemptAId && attemptBId && (
        <div className="grid gap-2 lg:grid-cols-2">
          <AttemptSideCard
            label="Run A attempt"
            runId={runAId}
            topic={rowA?.topic ?? ""}
            attemptId={attemptAId}
            detail={detailA}
            answerText={answerTextA}
            previewMode={previewMode}
          />
          <AttemptSideCard
            label="Run B attempt"
            runId={runBId}
            topic={rowB?.topic ?? ""}
            attemptId={attemptBId}
            detail={detailB}
            answerText={answerTextB}
            previewMode={previewMode}
          />
        </div>
      )}
    </Panel>
  );
}

function DeltaCard({ label, value, tone }: { label: string; value: string; tone: number }) {
  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2">
      <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {label}
      </div>
      <div className={`mt-1 text-base font-semibold ${deltaTone(tone)}`}>{value}</div>
    </div>
  );
}
