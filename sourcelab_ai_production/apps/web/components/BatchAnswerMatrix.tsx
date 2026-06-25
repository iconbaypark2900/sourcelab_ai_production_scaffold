"use client";

import Link from "next/link";
import { useState } from "react";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  answerMatrixExportFilename,
  buildAnswerMatrixExportJson,
  buildAnswerMatrixExportMarkdown,
  buildBestVsBestPreset,
  buildGroupedAnswerRecommendations,
  buildLatestVsBestRunPreset,
  buildLatestVsLatestPreset,
  copyTextPayload,
  downloadTextFile,
  getAnswerRowLabels,
  runAttemptUrl,
  type CrossRunDiffPreset,
} from "@/lib/batch-run";
import { formatScore } from "@/lib/format";
import type { AnswerCompareResponse } from "@/lib/types";

interface BatchAnswerMatrixProps {
  comparison: AnswerCompareResponse;
  batchId?: string;
  /** When true, show recommendation bullets even when no attempts exist. */
  showRecommendations?: boolean;
  onCrossRunDiffPreset?: (preset: CrossRunDiffPreset) => void;
}

function RecommendationGroups({ comparison }: { comparison: AnswerCompareResponse }) {
  const groups = buildGroupedAnswerRecommendations(comparison);
  if (!groups.length) {
    return null;
  }

  return (
    <div className="mb-4 space-y-3">
      {groups.map((group) => (
        <div key={group.key}>
          <div className="mb-1 text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
            {group.title}
          </div>
          <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--sl-text-dim)]">
            {group.items.map((item) => (
              <li key={`${group.key}-${item}`}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** Learner answer comparison matrix — used on batch detail and runs compare. */
export default function BatchAnswerMatrix({
  comparison,
  batchId,
  showRecommendations = true,
  onCrossRunDiffPreset,
}: BatchAnswerMatrixProps) {
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const summary = comparison.summary;
  const hasAttempts = summary.runs_with_attempts > 0;
  const groups = showRecommendations ? buildGroupedAnswerRecommendations(comparison) : [];
  const hasRecommendations = groups.length > 0;

  function exportJson() {
    const content = buildAnswerMatrixExportJson(comparison, batchId);
    downloadTextFile(
      answerMatrixExportFilename(batchId, "json"),
      content,
      "application/json",
    );
  }

  function exportMarkdown() {
    const content = buildAnswerMatrixExportMarkdown(comparison, batchId);
    downloadTextFile(answerMatrixExportFilename(batchId, "md"), content, "text/markdown");
  }

  async function copyMarkdown() {
    const content = buildAnswerMatrixExportMarkdown(comparison, batchId);
    const copied = await copyTextPayload(content);
    setCopyMessage(copied ? "Matrix markdown copied." : "Could not copy matrix markdown.");
    window.setTimeout(() => setCopyMessage(null), 2500);
  }

  function applyPreset(preset: CrossRunDiffPreset | null) {
    if (preset && onCrossRunDiffPreset) {
      onCrossRunDiffPreset(preset);
    }
  }

  const latestVsLatest = buildLatestVsLatestPreset(comparison);
  const bestVsBest = buildBestVsBestPreset(comparison);
  const runsWithAttempts = comparison.per_run.filter((row) => row.attempt_count > 0);

  if (!hasAttempts) {
    return (
      <Panel title="Learner answer matrix" id="answer-matrix">
        <div className="mb-3 flex flex-wrap gap-2">
          <button type="button" className="sl-btn text-xs" onClick={exportJson}>
            Download JSON
          </button>
          <button type="button" className="sl-btn text-xs" onClick={exportMarkdown}>
            Download Markdown
          </button>
          <button type="button" className="sl-btn text-xs" onClick={() => void copyMarkdown()}>
            Copy Markdown
          </button>
        </div>
        {copyMessage && <p className="mb-2 text-xs text-[var(--sl-text-faint)]">{copyMessage}</p>}
        <p className="text-sm text-[var(--sl-text-dim)]">
          No answer attempts yet for runs in {batchId ? `batch ${batchId}` : "this comparison"}.
          Submit answers from Run Studio or use the batch sample-answer panel below.
        </p>
        {hasRecommendations && <RecommendationGroups comparison={comparison} />}
      </Panel>
    );
  }

  return (
    <Panel title="Learner answer matrix" glow="violet" id="answer-matrix">
      <div className="mb-4 flex flex-wrap gap-2">
        <button type="button" className="sl-btn text-xs" onClick={exportJson}>
          Download JSON
        </button>
        <button type="button" className="sl-btn text-xs" onClick={exportMarkdown}>
          Download Markdown
        </button>
        <button type="button" className="sl-btn text-xs" onClick={() => void copyMarkdown()}>
          Copy Markdown
        </button>
      </div>
      {copyMessage && <p className="mb-2 text-xs text-[var(--sl-text-faint)]">{copyMessage}</p>}

      {onCrossRunDiffPreset && runsWithAttempts.length >= 2 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="sl-btn text-xs"
            disabled={!latestVsLatest}
            onClick={() => applyPreset(latestVsLatest)}
          >
            Compare latest vs latest
          </button>
          <button
            type="button"
            className="sl-btn text-xs"
            disabled={!bestVsBest}
            onClick={() => applyPreset(bestVsBest)}
          >
            Compare best vs best
          </button>
        </div>
      )}

      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Runs with answers" value={`${summary.runs_with_attempts}/${summary.total_runs}`} />
        <Stat
          label="Runs without answers"
          value={`${summary.runs_without_attempts}/${summary.total_runs}`}
        />
        <Stat
          label="Avg latest"
          value={summary.avg_latest_score != null ? formatScore(summary.avg_latest_score) : "—"}
        />
        <Stat
          label="Avg best"
          value={summary.avg_best_score != null ? formatScore(summary.avg_best_score) : "—"}
        />
        <Stat label="Review-heavy" value={String(summary.review_heavy_runs.length)} />
      </div>

      {hasRecommendations && <RecommendationGroups comparison={comparison} />}

      {comparison.recommendation && (
        <p className="mb-4 text-sm text-[var(--sl-text-faint)]">{comparison.recommendation}</p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--sl-border)] text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
              <th className="py-2 pr-3">Run</th>
              <th className="py-2 pr-3">Topic</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2 pr-3 text-right">Att</th>
              <th className="py-2 pr-3 text-right">Latest</th>
              <th className="py-2 pr-3 text-right">Best</th>
              <th className="py-2 pr-3 text-right">Review</th>
              <th className="py-2 pr-3 text-right">Capped</th>
              <th className="py-2">Links</th>
            </tr>
          </thead>
          <tbody>
            {comparison.per_run.map((row) => {
              const labels = getAnswerRowLabels(row);
              const latestVsBestRun = buildLatestVsBestRunPreset(comparison, row.run_id);
              return (
                <tr key={row.run_id} className="border-b border-[var(--sl-border)]/60">
                  <td className="py-2 pr-3 font-mono text-xs text-[var(--sl-cyan)]">{row.run_id}</td>
                  <td className="max-w-[180px] truncate py-2 pr-3">{row.topic}</td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap gap-1">
                      {labels.map((label) => (
                        <StatusPill
                          key={label.key}
                          tone={label.tone}
                          label={label.text}
                          dot={false}
                        />
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-3 text-right">{row.attempt_count}</td>
                  <td className="py-2 pr-3 text-right">
                    {row.attempt_count ? formatScore(row.latest_score) : "—"}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    {row.attempt_count ? formatScore(row.best_score) : "—"}
                  </td>
                  <td className="py-2 pr-3 text-right">{row.needs_review_count}</td>
                  <td className="py-2 pr-3 text-right">{row.capped_count}</td>
                  <td className="py-2">
                    <div className="flex flex-wrap gap-1">
                      <Link href={`/runs/${row.run_id}`} className="sl-btn text-xs">
                        Studio
                      </Link>
                      {row.latest_attempt_id && (
                        <Link href={runAttemptUrl(row.run_id, row.latest_attempt_id)} className="sl-btn text-xs">
                          Latest
                        </Link>
                      )}
                      {row.best_attempt_id && row.best_attempt_id !== row.latest_attempt_id && (
                        <Link href={runAttemptUrl(row.run_id, row.best_attempt_id)} className="sl-btn text-xs">
                          Best
                        </Link>
                      )}
                      {onCrossRunDiffPreset && latestVsBestRun && (
                        <button
                          type="button"
                          className="sl-btn text-xs"
                          onClick={() => applyPreset(latestVsBestRun)}
                        >
                          vs best run
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2">
      <div className="text-base font-semibold text-white">{value}</div>
      <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {label}
      </div>
    </div>
  );
}
