"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { runEvals, SourceLabApiError } from "@/lib/sourcelab-api";
import { formatScore, humanize } from "@/lib/format";
import type {
  EvalsLatestResponse,
  GoldenEvalReport,
  PackThresholdResponse,
} from "@/lib/types";
import {
  EVAL_TYPE_LABELS,
  groupFailuresByReport,
  hasReportFailures,
  reportFailureCount,
  totalFailureCount,
} from "@/lib/evals-summary";
import { complianceLabel, complianceTone } from "@/lib/eval-thresholds";
import EvalFailurePanel from "@/components/EvalFailurePanel";
import { Panel } from "@/components/Chrome";
import StatusPill, { type PillTone } from "@/components/StatusPill";

function passTone(passRate: number | undefined): PillTone {
  if (passRate === undefined || passRate === null) {
    return "missing";
  }
  if (passRate >= 1) {
    return "pass";
  }
  if (passRate >= 0.5) {
    return "review";
  }
  return "blocked";
}

function evalTone(report: GoldenEvalReport): PillTone {
  if (report.failed_cases && report.failed_cases > 0) {
    return "blocked";
  }
  if (report.pass_rate === 1) {
    return "pass";
  }
  return "review";
}

interface PackEvalCardProps {
  packName: string;
  evals: EvalsLatestResponse | null;
  thresholds?: PackThresholdResponse | null;
  strictRequired?: boolean;
}

export default function PackEvalCard({
  packName,
  evals,
  thresholds,
  strictRequired,
}: PackEvalCardProps) {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [latest, setLatest] = useState<EvalsLatestResponse | null>(evals);
  const [expandedReports, setExpandedReports] = useState<Set<string>>(new Set());

  const handleRun = useCallback(async () => {
    setRunning(true);
    setRunError(null);
    try {
      const result = await runEvals(packName);
      if (result.summary) {
        setLatest({
          pack_name: packName,
          summary: result.summary,
          markdown: "",
        });
        setExpandedReports(new Set());
      }
    } catch (err) {
      const message =
        err instanceof SourceLabApiError ? err.message : "Failed to run evals";
      setRunError(message);
    } finally {
      setRunning(false);
    }
  }, [packName]);

  const toggleReport = useCallback((evalName: string) => {
    setExpandedReports((prev) => {
      const next = new Set(prev);
      if (next.has(evalName)) {
        next.delete(evalName);
      } else {
        next.add(evalName);
      }
      return next;
    });
  }, []);

  const summary = latest?.summary;
  const hasEvals = Boolean(summary && summary.total_cases);
  const reports = summary?.eval_reports ?? [];
  const overallPassRate = summary?.overall_pass_rate;
  const totalCases = summary?.total_cases ?? 0;
  const failedCount = totalFailureCount(latest);
  const failureGroups = groupFailuresByReport(latest);

  const thresholdTone = thresholds ? complianceTone(thresholds) : null;

  return (
    <Panel
      title={packName}
      hint={strictRequired ? "Required for strict release" : undefined}
      glow={overallPassRate === 1 ? "cyan" : undefined}
      action={
        <div className="flex items-center gap-2">
          <Link
            href={`/evals/${encodeURIComponent(packName)}`}
            className="sl-btn text-xs"
          >
            History
          </Link>
          <button
            type="button"
            className="sl-btn sl-btn--primary text-xs"
            onClick={handleRun}
            disabled={running}
          >
            {running ? "Running…" : "Run evals"}
          </button>
        </div>
      }
    >
      {runError && (
        <p className="mb-3 rounded-lg border border-[var(--sl-rose)] bg-[rgba(244,63,94,0.08)] px-3 py-2 text-xs text-[var(--sl-rose)]">
          {runError}
        </p>
      )}

      {!hasEvals && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--sl-text-faint)]">
            No eval results yet. Run evals to populate this card.
          </span>
          <StatusPill tone="missing" label="NO EVALS" />
        </div>
      )}

      {hasEvals && (
        <>
          <div className="mb-3 flex items-center justify-between">
            <span className="text-2xl font-semibold text-white">
              {formatScore(overallPassRate)}
            </span>
            <div className="flex items-center gap-2">
              {failedCount > 0 && (
                <StatusPill
                  tone="blocked"
                  label={`${failedCount} failing`}
                />
              )}
              <StatusPill tone={passTone(overallPassRate)} label={`${totalCases} cases`} />
            </div>
          </div>

          {thresholds && (
            <div className="mb-3 flex items-center justify-between gap-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] px-3 py-2">
              <div className="flex items-center gap-2">
                <StatusPill
                  tone={
                    thresholdTone === "pass"
                      ? "pass"
                      : thresholdTone === "review"
                        ? "review"
                        : thresholdTone === "blocked"
                          ? "blocked"
                          : "missing"
                  }
                  dot={false}
                  label={complianceLabel(thresholds)}
                />
                <span className="text-xs text-[var(--sl-text-dim)]">
                  {(thresholds.thresholds.min_pass_rate * 100).toFixed(0)}% min ·{" "}
                  {thresholds.thresholds.min_cases}+ cases
                </span>
              </div>
            </div>
          )}

          {reports.length > 0 && (
            <div className="space-y-1.5">
              {reports.map((report) => {
                const evalName = report.eval_name ?? "";
                const reportFails = reportFailureCount(report);
                const isExpanded = expandedReports.has(evalName);
                const canExpand = hasReportFailures(report);
                return (
                  <div
                    key={evalName}
                    className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)]"
                  >
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
                      onClick={() => canExpand && toggleReport(evalName)}
                      aria-expanded={isExpanded}
                      disabled={!canExpand}
                    >
                      <div className="flex items-center gap-2">
                        <StatusPill
                          tone={evalTone(report)}
                          dot={false}
                          label={reportFails > 0 ? "FAIL" : "PASS"}
                        />
                        <span className="text-sm text-[var(--sl-text-dim)]">
                          {EVAL_TYPE_LABELS[evalName] ?? humanize(evalName)}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        {reportFails > 0 && (
                          <span className="rounded-md border border-[var(--sl-rose)] bg-[rgba(244,63,94,0.08)] px-1.5 py-0.5 text-[var(--sl-rose)]">
                            {reportFails} failing
                          </span>
                        )}
                        <span className="text-[var(--sl-text-faint)]">
                          {report.passed_cases ?? 0}/{report.total_cases ?? 0}
                        </span>
                        <span className="font-mono text-[var(--sl-cyan)]">
                          {formatScore(report.pass_rate)}
                        </span>
                        {canExpand && (
                          <span className="text-[var(--sl-text-faint)]">
                            {isExpanded ? "▾" : "▸"}
                          </span>
                        )}
                      </div>
                    </button>

                    {isExpanded && canExpand && (
                      <div className="border-t border-[var(--sl-border)] px-3 py-2">
                        <EvalFailurePanel
                          report={report}
                          failures={report.failures ?? []}
                          defaultOpen
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
