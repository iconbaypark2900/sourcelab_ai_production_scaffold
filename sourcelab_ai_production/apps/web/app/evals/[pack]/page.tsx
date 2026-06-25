"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { getEvalsHistory, getEvalsThresholds, getLatestEvals, type SourceLabApiError } from "@/lib/sourcelab-api";
import { useApi } from "@/lib/use-api";
import { formatScore, timeAgo } from "@/lib/format";
import {
  bestPassRate,
  computeTrend,
  failureCountTrend,
  formatDelta,
  passRatePoints,
  trendArrow,
  trendLabel,
  worstPassRate,
} from "@/lib/evals-history";
import type { EvalsHistoryResponse, PackThresholdResponse } from "@/lib/types";
import {
  ConnectionCard,
  EmptyState,
  LoadingPanel,
  Metric,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill, { type PillTone } from "@/components/StatusPill";
import TrendBadge from "@/components/TrendBadge";
import ThresholdPanel from "@/components/ThresholdPanel";

interface HistoryPageData {
  history: EvalsHistoryResponse;
  hasLatest: boolean;
  thresholds: PackThresholdResponse | null;
}

function trendTone(direction: string): PillTone {
  if (direction === "up") return "pass";
  if (direction === "down") return "blocked";
  if (direction === "flat") return "info";
  return "missing";
}

function runTone(totalFailed: number | null | undefined): PillTone {
  if (totalFailed === null || totalFailed === undefined) return "missing";
  if (totalFailed === 0) return "pass";
  return "blocked";
}

export default function EvalHistoryPage() {
  const params = useParams<{ pack: string }>();
  const packName = params?.pack ?? "";

  const { data, error, loading, reload } = useApi<HistoryPageData>(
    async () => {
      const [history, latest, thresholds] = await Promise.all([
        getEvalsHistory(packName, 50),
        getLatestEvals(packName).catch(() => null),
        getEvalsThresholds(packName).catch(() => null),
      ]);
      return { history, hasLatest: Boolean(latest), thresholds };
    },
    [packName],
  );

  if (loading) {
    return (
      <PageShell>
        <PageHeader
          title={`${packName} eval history`}
          subtitle="Loading eval trend history…"
        />
        <LoadingPanel label="Loading eval history…" />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <PageHeader title={`${packName} eval history`} />
        <ConnectionCard error={error as SourceLabApiError} onRetry={reload} />
      </PageShell>
    );
  }

  const response = data!.history;
  const trend = computeTrend(response);
  const points = passRatePoints(response.history);
  const failures = failureCountTrend(response.history);
  const best = bestPassRate(response.history);
  const worst = worstPassRate(response.history);

  return (
    <PageShell>
      <PageHeader
        title={`${packName} eval history`}
        subtitle="Golden eval pass-rate trend across runs. Newest first."
      >
        <TrendBadge
          direction={trend.direction}
          delta={trend.delta}
          deltaPercent={trend.deltaPercent}
        />
        <Link href="/evals" className="sl-btn sl-btn--primary text-xs">
          ← All packs
        </Link>
      </PageHeader>

      <div className="mb-5 grid gap-4 lg:grid-cols-4">
        <Metric
          label="Latest pass rate"
          value={formatScore(trend.latest)}
          tone={
            trend.latest === null
              ? "default"
              : trend.latest >= 1
                ? "good"
                : trend.latest >= 0.5
                  ? "warn"
                  : "bad"
          }
        />
        <Metric
          label="Previous pass rate"
          value={formatScore(trend.previous)}
          hint={
            trend.previous === null ? "First run" : "Run before latest"
          }
        />
        <Metric
          label="Delta"
          value={`${trendArrow(trend.direction)} ${formatDelta(trend.delta)}`}
          tone={
            trend.direction === "up"
              ? "good"
              : trend.direction === "down"
                ? "bad"
                : trend.direction === "flat"
                  ? "default"
                  : "default"
          }
          hint={
            trend.deltaPercent !== null && trend.deltaPercent !== undefined
              ? `${trend.deltaPercent > 0 ? "+" : ""}${trend.deltaPercent.toFixed(1)}% relative`
              : "No prior run to compare"
          }
        />
        <Metric
          label="Run count"
          value={response.run_count}
          hint={
            points.length > 0
              ? `${points[points.length - 1].snapshotAt} → ${points[0].snapshotAt}`
              : "No runs yet"
          }
        />
      </div>

      {response.history.length === 0 && (
        <EmptyState
          title="No eval history yet"
          message="Run evals from the Evals tab to start building trend history."
        />
      )}

      {response.history.length > 0 && (
        <>
          <div className="mb-4 grid gap-4 lg:grid-cols-3">
            <Panel title="Trend summary" glow="cyan">
              <ul className="space-y-2 text-sm">
                <li className="flex items-center justify-between">
                  <span className="text-[var(--sl-text-dim)]">Direction</span>
                  <StatusPill
                    tone={trendTone(trend.direction)}
                    label={trendLabel(trend.direction)}
                    dot={false}
                  />
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-[var(--sl-text-dim)]">Best pass rate</span>
                  <span className="font-mono text-[var(--sl-cyan)]">
                    {formatScore(best)}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-[var(--sl-text-dim)]">Worst pass rate</span>
                  <span className="font-mono text-[var(--sl-cyan)]">
                    {formatScore(worst)}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-[var(--sl-text-dim)]">Latest failures</span>
                  <span className="font-mono text-[var(--sl-cyan)]">
                    {failures.latest ?? "—"}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-[var(--sl-text-dim)]">Failure delta</span>
                  <span
                    className={`font-mono ${
                      failures.delta === null
                        ? "text-[var(--sl-text-faint)]"
                        : failures.delta > 0
                          ? "text-[var(--sl-rose)]"
                          : failures.delta < 0
                            ? "text-[var(--sl-emerald)]"
                            : "text-[var(--sl-text)]"
                    }`}
                  >
                    {failures.delta === null
                      ? "—"
                      : `${failures.delta > 0 ? "+" : ""}${failures.delta}`}
                  </span>
                </li>
              </ul>
            </Panel>

            <Panel
              title="Sparkline"
              hint="Pass rate per run (newest at top)"
              glow="violet"
            >
              <Sparkline points={points} />
            </Panel>
            <ThresholdPanel response={data!.thresholds} />
          </div>

          <Panel title="Run history" hint={`${response.run_count} runs`}>
            <div className="space-y-1.5">
              {response.history.map((entry, index) => {
                const isLatest = index === 0;
                const isPrevious = index === 1;
                const tone = runTone(entry.total_failed);
                const rate = entry.overall_pass_rate ?? 0;
                const prevRate =
                  response.history[index + 1]?.overall_pass_rate;
                const delta =
                  prevRate !== undefined && prevRate !== null
                    ? rate - prevRate
                    : null;
                return (
                  <div
                    key={`${entry.snapshot_at}-${index}`}
                    className="flex items-center justify-between gap-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <StatusPill
                        tone={tone}
                        dot={false}
                        label={tone === "pass" ? "PASS" : "FAIL"}
                      />
                      <span className="font-mono text-xs text-[var(--sl-text-dim)]">
                        {entry.snapshot_at}
                      </span>
                      {isLatest && (
                        <span className="rounded-md border border-[var(--sl-cyan)] bg-[rgba(34,211,238,0.08)] px-1.5 py-0.5 text-[0.62rem] uppercase tracking-[0.12em] text-[var(--sl-cyan)]">
                          Latest
                        </span>
                      )}
                      {isPrevious && (
                        <span className="rounded-md border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-1.5 py-0.5 text-[0.62rem] uppercase tracking-[0.12em] text-[var(--sl-text-faint)]">
                          Previous
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-[var(--sl-text-faint)]">
                        {entry.total_passed ?? 0}/{entry.total_cases ?? 0}
                      </span>
                      {delta !== null && (
                        <span
                          className={`font-mono ${
                            delta > 0
                              ? "text-[var(--sl-emerald)]"
                              : delta < 0
                                ? "text-[var(--sl-rose)]"
                                : "text-[var(--sl-text-faint)]"
                          }`}
                        >
                          {formatDelta(delta)}
                        </span>
                      )}
                      <span className="font-mono text-[var(--sl-cyan)]">
                        {formatScore(entry.overall_pass_rate)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>
        </>
      )}

      <p className="mt-6 text-xs text-[var(--sl-text-faint)]">
        History is stored at{" "}
        <code className="text-[var(--sl-cyan)]">
          artifacts/evals/{packName}/history/&lt;UTC-timestamp&gt;.json
        </code>{" "}
        — snapshotted on each successful eval run.
      </p>
    </PageShell>
  );
}

function Sparkline({ points }: { points: { snapshotAt: string; passRate: number }[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-[var(--sl-text-faint)]">No data points to plot.</p>;
  }

  // Render newest at top -> reverse for chart (oldest at top visually)
  const ordered = [...points].reverse();
  const WIDTH = 100;
  const HEIGHT = 24;
  const stepX = points.length > 1 ? WIDTH / (points.length - 1) : 0;
  const yFor = (rate: number) => HEIGHT - rate * HEIGHT;

  const path = ordered
    .map((point, index) => {
      const x = index * stepX;
      const y = yFor(point.passRate);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-12 w-full"
        preserveAspectRatio="none"
        aria-label="Pass-rate trend over time"
        role="img"
      >
        <line
          x1="0"
          y1={HEIGHT}
          x2={WIDTH}
          y2={HEIGHT}
          stroke="rgba(255,255,255,0.1)"
          strokeWidth="0.3"
        />
        <path
          d={path}
          fill="none"
          stroke="var(--sl-cyan)"
          strokeWidth="0.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        {ordered.map((point, index) => {
          const x = index * stepX;
          const y = yFor(point.passRate);
          return (
            <circle
              key={point.snapshotAt}
              cx={x}
              cy={y}
              r="0.6"
              fill="var(--sl-cyan)"
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
      </svg>
      <div className="flex items-center justify-between text-[0.62rem] text-[var(--sl-text-faint)]">
        <span>{ordered[0]?.snapshotAt}</span>
        <span>
          {ordered.length} run{ordered.length === 1 ? "" : "s"}
        </span>
        <span>{ordered[ordered.length - 1]?.snapshotAt}</span>
      </div>
    </div>
  );
}
