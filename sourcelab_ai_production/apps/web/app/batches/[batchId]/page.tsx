"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import BatchResearchMatrix from "@/components/BatchResearchMatrix";
import BatchAnswerMatrix from "@/components/BatchAnswerMatrix";
import BatchAnswerSubmitPanel from "@/components/BatchAnswerSubmitPanel";
import BatchDemoBundleExport from "@/components/BatchDemoBundleExport";
import BatchReportPreview from "@/components/BatchReportPreview";
import BatchSummaryPanel from "@/components/BatchSummaryPanel";
import CrossRunAnswerDiffPanel from "@/components/CrossRunAnswerDiffPanel";
import RunComparisonPanel from "@/components/RunComparisonPanel";
import RunRefreshBar from "@/components/RunRefreshBar";
import {
  ConnectionCard,
  LoadingPanel,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import { combineLastUpdated, type CrossRunDiffPreset } from "@/lib/batch-run";
import {
  SourceLabApiError,
  compareBatch,
  compareBatchAnswers,
  getBatch,
} from "@/lib/sourcelab-api";
import type { AnswerCompareResponse, BatchDetailResponse, RunComparisonResponse } from "@/lib/types";
import { useRunRefresh } from "@/lib/use-run-refresh";
import { formatScore } from "@/lib/format";
import { STUDY_SET_TERMS } from "@/lib/library-theme";

export default function BatchDetailPage() {
  const params = useParams<{ batchId: string }>();
  const batchId = params.batchId;
  const [comparison, setComparison] = useState<RunComparisonResponse | null>(null);
  const [answerComparison, setAnswerComparison] = useState<AnswerCompareResponse | null>(null);
  const [answerLoadError, setAnswerLoadError] = useState<SourceLabApiError | null>(null);
  const [compareError, setCompareError] = useState<SourceLabApiError | null>(null);
  const [comparing, setComparing] = useState(false);
  const [comparingAnswers, setComparingAnswers] = useState(false);
  const [answersLoading, setAnswersLoading] = useState(true);
  const [answersRefreshing, setAnswersRefreshing] = useState(false);
  const [answerLastUpdated, setAnswerLastUpdated] = useState<Date | null>(null);
  const [reportRefreshToken, setReportRefreshToken] = useState(0);
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null);
  const [crossRunPreset, setCrossRunPreset] = useState<CrossRunDiffPreset | null>(null);
  const prevBatchUpdated = useRef<Date | null>(null);
  const answerComparisonRef = useRef<AnswerCompareResponse | null>(null);
  answerComparisonRef.current = answerComparison;

  const {
    data,
    error,
    loading,
    refreshing,
    lastUpdated,
    autoRefresh,
    setAutoRefresh,
    refresh,
    intervalMs,
  } = useRunRefresh(() => getBatch(batchId), [batchId]);

  const loadAnswerComparison = useCallback(
    async (options?: { keepCache?: boolean }) => {
      const keepCache = options?.keepCache ?? true;
      setAnswerLoadError(null);
      if (!answerComparisonRef.current) {
        setAnswersLoading(true);
      } else {
        setAnswersRefreshing(true);
      }
      try {
        const result = await compareBatchAnswers(batchId);
        setAnswerComparison(result);
        setAnswerLastUpdated(new Date());
      } catch (cause) {
        setAnswerLoadError(
          cause instanceof SourceLabApiError
            ? cause
            : new SourceLabApiError({
                message: "Answer comparison failed.",
                status: 500,
                detail: cause instanceof Error ? cause.message : String(cause),
              }),
        );
        if (!keepCache) {
          setAnswerComparison(null);
        }
      } finally {
        setAnswersLoading(false);
        setAnswersRefreshing(false);
      }
    },
    [batchId],
  );

  const refreshRunComparison = useCallback(async () => {
    if (!data || (data as BatchDetailResponse).run_ids.length < 2) {
      return;
    }
    setCompareError(null);
    try {
      const result = await compareBatch(batchId);
      setComparison(result);
    } catch (cause) {
      setCompareError(
        cause instanceof SourceLabApiError
          ? cause
          : new SourceLabApiError({
              message: "Comparison failed.",
              status: 500,
              detail: cause instanceof Error ? cause.message : String(cause),
            }),
      );
    }
  }, [batchId, data]);

  const refreshAll = useCallback(() => {
    refresh();
    void loadAnswerComparison({ keepCache: true });
    void refreshRunComparison();
    setReportRefreshToken((value) => value + 1);
  }, [refresh, loadAnswerComparison, refreshRunComparison]);

  useEffect(() => {
    void loadAnswerComparison({ keepCache: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchId]);

  useEffect(() => {
    if (!data || (data as BatchDetailResponse).run_ids.length < 2) {
      return;
    }
    void refreshRunComparison();
  }, [batchId, data, refreshRunComparison]);

  useEffect(() => {
    if (!lastUpdated) {
      return;
    }
    if (prevBatchUpdated.current && prevBatchUpdated.current.getTime() !== lastUpdated.getTime()) {
      void loadAnswerComparison({ keepCache: true });
    }
    prevBatchUpdated.current = lastUpdated;
  }, [lastUpdated, loadAnswerComparison]);

  async function handleCompareRuns() {
    setCompareError(null);
    setComparing(true);
    try {
      const result = await compareBatch(batchId);
      setComparison(result);
    } catch (cause) {
      setCompareError(
        cause instanceof SourceLabApiError
          ? cause
          : new SourceLabApiError({
              message: "Comparison failed.",
              status: 500,
              detail: cause instanceof Error ? cause.message : String(cause),
            }),
      );
    } finally {
      setComparing(false);
    }
  }

  async function handleCompareAnswers() {
    setCompareError(null);
    setComparingAnswers(true);
    try {
      await loadAnswerComparison({ keepCache: true });
      document.getElementById("answer-matrix")?.scrollIntoView({ behavior: "smooth" });
    } catch {
      // loadAnswerComparison sets answerLoadError
    } finally {
      setComparingAnswers(false);
    }
  }

  if (loading && !data) {
    return (
      <PageShell>
        <PageHeader title={STUDY_SET_TERMS.batchDetail} />
        <LoadingPanel label="Loading study set…" />
      </PageShell>
    );
  }

  if (error && !data) {
    return (
      <PageShell>
        <PageHeader title={STUDY_SET_TERMS.batchDetail} />
        <ConnectionCard error={error} onRetry={refreshAll} />
      </PageShell>
    );
  }

  if (!data) {
    return null;
  }

  const batch = data as BatchDetailResponse;
  const answerSummary = answerComparison?.summary;
  const combinedLastUpdated = combineLastUpdated([lastUpdated, answerLastUpdated]);
  const isRefreshing = refreshing || answersRefreshing;
  const runOptions = batch.run_ids.map((runId) => {
    const summary = batch.run_summaries.find((r) => r.run_id === runId);
    const runMeta = batch.runs.find((r) => r.run_id === runId);
    return {
      runId,
      topic: summary?.topic ?? runMeta?.topic ?? "",
    };
  });

  return (
    <PageShell>
      <PageHeader title={batch.batch_name} subtitle={`${STUDY_SET_TERMS.batch} ${batch.batch_id}`}>
        <Link href="/batches" className="sl-btn">
          All study sets
        </Link>
        {answerSummary && (
          <>
            <StatusPill
              tone="info"
              label={`Answers ${answerSummary.runs_with_attempts}/${answerSummary.total_runs}`}
              dot={false}
            />
            {answerSummary.avg_latest_score != null && (
              <StatusPill
                tone="neutral"
                label={`Avg latest ${formatScore(answerSummary.avg_latest_score)}`}
                dot={false}
              />
            )}
            {answerSummary.avg_best_score != null && (
              <StatusPill
                tone="neutral"
                label={`Avg best ${formatScore(answerSummary.avg_best_score)}`}
                dot={false}
              />
            )}
            {answerSummary.review_heavy_runs.length > 0 && (
              <StatusPill
                tone="review"
                label={`Review-heavy ${answerSummary.review_heavy_runs.length}`}
                dot={false}
              />
            )}
          </>
        )}
        <StatusPill
          tone={batch.status === "complete" ? "pass" : "review"}
          label={batch.status.toUpperCase()}
        />
      </PageHeader>

      <RunRefreshBar
        lastUpdated={combinedLastUpdated}
        refreshing={isRefreshing}
        autoRefresh={autoRefresh}
        intervalMs={intervalMs}
        offline={Boolean(error)}
        onToggleAuto={setAutoRefresh}
        onRefresh={refreshAll}
      />

      {error && data && (
        <div className="mb-4">
          <ConnectionCard error={error} onRetry={refreshAll} />
        </div>
      )}

      <div className="space-y-4">
        <BatchSummaryPanel batch={batch} />

        <Panel title="Session cards">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {(batch.run_summaries.length ? batch.run_summaries : batch.runs).map((run) => {
              const runId = "run_id" in run ? run.run_id : (run as { run_id: string }).run_id;
              const topic = "topic" in run ? run.topic : "";
              const harness =
                "harness_passed" in run
                  ? run.harness_passed
                  : (run as { harness_status?: string }).harness_status === "PASS";
              return (
                <div
                  key={runId}
                  className="rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.35)] p-3"
                >
                  <div className="font-mono text-xs text-[var(--sl-cyan)]">{runId}</div>
                  <div className="mt-1 truncate text-sm text-white">{topic}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <StatusPill tone={harness ? "pass" : "blocked"} label={harness ? "PASS" : "FAIL"} dot={false} />
                    {"citation_resolution_rate" in run && (
                      <span className="text-xs text-[var(--sl-text-dim)]">
                        citations {formatScore(run.citation_resolution_rate as number | null)}
                      </span>
                    )}
                  </div>
                  <Link href={`/runs/${runId}`} className="sl-btn mt-3 w-full justify-center text-xs">
                    Open Reading Room
                  </Link>
                </div>
              );
            })}
          </div>
        </Panel>

        <BatchAnswerSubmitPanel
          runs={runOptions}
          answerComparison={answerComparison}
          onComplete={() => void loadAnswerComparison({ keepCache: true })}
        />

        {answersLoading && !answerComparison && (
          <LoadingPanel label="Loading study progress matrix…" />
        )}

        {answerLoadError && (
          <ConnectionCard
            error={answerLoadError}
            onRetry={() => void loadAnswerComparison({ keepCache: true })}
          />
        )}

        {answerComparison && (
          <>
            <BatchAnswerMatrix
              comparison={answerComparison}
              batchId={batchId}
              onCrossRunDiffPreset={setCrossRunPreset}
            />
            <CrossRunAnswerDiffPanel
              perRun={answerComparison.per_run}
              preset={crossRunPreset}
              onPresetConsumed={() => setCrossRunPreset(null)}
            />
          </>
        )}

        {comparison && comparison.run_ids.length >= 2 && (
          <BatchResearchMatrix comparison={comparison} batchId={batchId} />
        )}

        <BatchDemoBundleExport
          batchId={batchId}
          batchSummary={batch}
          runComparison={comparison}
          answerComparison={answerComparison}
          reportMarkdown={reportMarkdown}
        />

        <Panel title="Compare">
          <div className="mb-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="sl-btn sl-btn--primary"
              disabled={comparing || batch.run_ids.length < 2}
              onClick={handleCompareRuns}
            >
              {comparing ? "Comparing…" : "Compare generated runs"}
            </button>
            <button
              type="button"
              className="sl-btn sl-btn--primary"
              disabled={comparingAnswers || batch.run_ids.length < 1}
              onClick={handleCompareAnswers}
            >
              {comparingAnswers ? "Refreshing…" : "Compare learner answers"}
            </button>
            {batch.run_ids.length >= 2 && (
              <Link
                href={`/runs/compare?run_ids=${batch.run_ids.join(",")}&tab=answers`}
                className="sl-btn"
              >
                Open run compare page
              </Link>
            )}
          </div>
          {batch.run_ids.length < 2 && (
            <p className="text-sm text-[var(--sl-text-faint)]">
              At least two runs are required for run comparison.
            </p>
          )}
          {compareError && (
            <p className="text-sm text-[var(--sl-rose)]">{compareError.message}</p>
          )}
          {comparison && <RunComparisonPanel comparison={comparison} />}
        </Panel>

        <BatchReportPreview
          batchId={batchId}
          hasComparison={batch.has_comparison}
          refreshToken={reportRefreshToken}
          onReportLoaded={setReportMarkdown}
        />
      </div>
    </PageShell>
  );
}
