"use client";

import Link from "next/link";

import { getCurriculum } from "@/lib/sourcelab-api";
import { formatScore, timeAgo } from "@/lib/format";
import { useApi } from "@/lib/use-api";
import type { CurriculumResponse, FullSkillProfile } from "@/lib/types";
import {
  ConnectionCard,
  EmptyState,
  LoadingPanel,
  Metric,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import TrendBadge from "@/components/TrendBadge";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function masteryBand(score: number): string {
  if (score >= 0.8) return "advanced";
  if (score >= 0.6) return "developing";
  return "needs_support";
}

export function masteryTone(score: number): "good" | "warn" | "bad" {
  if (score >= 0.8) return "good";
  if (score >= 0.6) return "warn";
  return "bad";
}

export function masteryPillTone(score: number): "pass" | "review" | "blocked" {
  if (score >= 0.8) return "pass";
  if (score >= 0.6) return "review";
  return "blocked";
}

export function avgMastery(profile: FullSkillProfile): number {
  const vals = Object.values(profile.mastery);
  if (!vals.length) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function CurriculumPage() {
  const { data, error, loading, reload } = useApi<CurriculumResponse>(
    () => getCurriculum(),
    [],
  );

  return (
    <PageShell>
      <PageHeader title="Progress" subtitle="Learning curriculum overview, skill mastery, and next-task recommendations." />

      {loading && <LoadingPanel label="Loading curriculum…" />}

      {error && (
        <ConnectionCard
          error={error}
          onRetry={reload}
        />
      )}

      {!loading && !error && !data && (
        <EmptyState title="No progress data" message="Submit an answer to start tracking your learning progress." />
      )}

      {data && <CurriculumDashboard data={data} />}
    </PageShell>
  );
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export function CurriculumDashboard({ data }: { data: CurriculumResponse }) {
  const { profile, latest_report, latest_next_task } = data;
  const totalAttempts = profile.attempts?.length ?? 0;
  const avgScore = avgMastery(profile);
  const topicCount = Object.keys(profile.mastery).length;
  const advancedTopics = Object.entries(profile.mastery).filter(([, s]) => s >= 0.8).length;
  const needsSupport = Object.entries(profile.mastery).filter(([, s]) => s < 0.6).length;
  const lastPractice = profile.last_practiced ? timeAgo(profile.last_practiced) : "Never";
  const latestReportJson = latest_report?.report_json as Record<string, unknown> | undefined;
  const latestReportOverall = latestReportJson?.overall_score as number | undefined;
  const latestReportFocus = latestReportJson?.recommended_focus as string | undefined;
  const report = latest_report as Record<string, unknown> | undefined;
  const nextTask = latest_next_task as Record<string, unknown> | undefined;

  return (
    <>
      {/* Metrics row */}
      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Topics practiced" value={String(topicCount)} tone="default" hint={`${advancedTopics} advanced, ${needsSupport} need support`} />
        <Metric label="Overall mastery" value={formatScore(avgScore)} tone={masteryTone(avgScore)} hint={`Across ${topicCount} topic${topicCount !== 1 ? "s" : ""}`} />
        <Metric label="Total attempts" value={String(totalAttempts)} tone="good" hint="All-time answer submissions" />
        <Metric label="Last practiced" value={lastPractice} tone="default" hint={profile.last_practiced ? new Date(profile.last_practiced).toLocaleString() : ""} />
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        {/* Next-task recommendation */}
        <Panel title="Next task" hint="Recommended focus" glow="cyan" className="lg:col-span-1">
          {nextTask ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <StatusPill tone="pass" dot={false} label={String(nextTask.difficulty ?? "?")} />
                <span className="font-medium text-white">Difficulty {String(nextTask.difficulty ?? "?")}/5</span>
              </div>
              <p className="text-[var(--sl-text-dim)]">
                Focus: <span className="text-white">{String(nextTask.focus ?? "General")}</span>
              </p>
              <p className="text-[var(--sl-text-dim)]">
                Format: <span className="text-white">{String(nextTask.task_format ?? "Standard")}</span>
              </p>
              <p className="text-xs leading-relaxed text-[var(--sl-text-dim)]">
                {String(nextTask.reason ?? "")}
              </p>
              <Link
                href="/runs/new"
                className="mt-2 inline-block rounded-lg bg-[rgba(34,211,238,0.12)] px-3 py-1.5 text-sm text-[var(--sl-cyan)] transition-colors hover:bg-[rgba(34,211,238,0.2)]"
              >
                Start lesson →
              </Link>
            </div>
          ) : (
            <p className="text-sm text-[var(--sl-text-dim)]">Submit an answer to get a personalized recommendation.</p>
          )}
        </Panel>

        {/* Latest report summary */}
        <Panel title="Latest result" hint="Most recent answer" glow="violet" className="lg:col-span-1">
          {report ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-2xl font-semibold text-white">
                  {latestReportOverall !== undefined ? formatScore(latestReportOverall) : "—"}
                </span>
              </div>
              {latestReportFocus && (
                <p className="text-[var(--sl-text-dim)]">
                  Focus: <span className="text-white">{latestReportFocus}</span>
                </p>
              )}
              <p className="text-xs text-[var(--sl-text-dim)]">
                Topic: {String(report?.topic ?? "Unknown")}
              </p>
              <Link
                href={`/runs/${String(report?.run_id ?? "")}`}
                className="inline-block rounded-lg bg-[rgba(34,211,238,0.12)] px-3 py-1.5 text-sm text-[var(--sl-cyan)] transition-colors hover:bg-[rgba(34,211,238,0.2)]"
              >
                View run →
              </Link>
            </div>
          ) : (
            <p className="text-sm text-[var(--sl-text-dim)]">No answers submitted yet.</p>
          )}
        </Panel>

        {/* Strengths & weaknesses */}
        <Panel title="Strengths & weaknesses" glow="violet" className="lg:col-span-1">
          <div className="space-y-3 text-sm">
            {profile.strengths && profile.strengths.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-[var(--sl-text-dim)] uppercase tracking-wider">Strengths</p>
                <ul className="space-y-1">
                  {profile.strengths.slice(0, 5).map((s, i) => (
                    <li key={i} className="flex items-center gap-1.5">
                      <span className="text-[var(--sl-green)]">●</span>
                      <span className="text-[var(--sl-text)]">{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {profile.weaknesses && profile.weaknesses.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-[var(--sl-text-dim)] uppercase tracking-wider">Weaknesses</p>
                <ul className="space-y-1">
                  {profile.weaknesses.slice(0, 5).map((w, i) => (
                    <li key={i} className="flex items-center gap-1.5">
                      <span className="text-[var(--sl-red)]">●</span>
                      <span className="text-[var(--sl-text)]">
                        {w.criterion ?? "General"} ({w.topic}) — score {formatScore(w.average_score)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {(!profile.strengths || profile.strengths.length === 0) &&
              (!profile.weaknesses || profile.weaknesses.length === 0) && (
                <p className="text-[var(--sl-text-dim)]">No strengths or weaknesses tracked yet.</p>
              )}
          </div>
        </Panel>
      </div>

      {/* Topic mastery cards */}
      <Panel title="Topic mastery" hint={`${topicCount} topic${topicCount !== 1 ? "s" : ""}`}>
        {topicCount > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(profile.mastery)
              .sort(([, a], [, b]) => b - a)
              .map(([topic, mastery]) => {
                const criterionData = profile.criterion_mastery?.[topic] ?? {};
                return (
                  <MasteryCard
                    key={topic}
                    topic={topic}
                    mastery={mastery}
                    criteria={criterionData}
                    attempts={profile.attempts?.filter((a) => a.topic === topic).length ?? 0}
                  />
                );
              })}
          </div>
        ) : (
          <p className="text-sm text-[var(--sl-text-dim)]">
            No topics practiced yet.{" "}
            <Link href="/runs/new" className="text-[var(--sl-cyan)] underline">
              Start a lesson
            </Link>
          </p>
        )}
      </Panel>

      {/* Source grounding history */}
      {profile.source_grounding_history && profile.source_grounding_history.length > 0 && (
        <div className="mt-4">
          <Panel title="Source grounding history" hint="Last 20 attempts" glow="cyan">
            <SourceGroundingSparkline history={profile.source_grounding_history} />
          </Panel>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// MasteryCard
// ---------------------------------------------------------------------------

export function MasteryCard({
  topic,
  mastery,
  criteria,
  attempts,
}: {
  topic: string;
  mastery: number;
  criteria: Record<string, number>;
  attempts: number;
}) {
  const band = masteryBand(mastery);
  const criterionEntries = Object.entries(criteria).sort(([, a], [, b]) => b - a);

  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] p-3 transition-colors hover:border-[rgba(34,211,238,0.3)]">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-white truncate mr-2">{topic}</span>
        <StatusPill tone={masteryPillTone(mastery)} dot={false} label={band} />
      </div>
      <div className="mb-2 flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-[rgba(255,255,255,0.08)]">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${Math.round(mastery * 100)}%`,
              background: mastery >= 0.8
                ? "linear-gradient(90deg, var(--sl-green), #4ade80)"
                : mastery >= 0.6
                  ? "linear-gradient(90deg, #f59e0b, #fbbf24)"
                  : "linear-gradient(90deg, #ef4444, #f87171)",
            }}
          />
        </div>
        <span className="text-xs font-medium text-white">{formatScore(mastery)}</span>
      </div>
      <div className="flex items-center justify-between text-xs text-[var(--sl-text-dim)]">
        <span>{attempts} attempt{attempts !== 1 ? "s" : ""}</span>
        <StatusPill tone={masteryPillTone(mastery)} dot={false} label={band} />
      </div>
      {criterionEntries.length > 0 && (
        <div className="mt-2 space-y-1 border-t border-[var(--sl-border)] pt-2">
          {criterionEntries.slice(0, 4).map(([name, score]) => (
            <div key={name} className="flex items-center justify-between text-xs">
              <span className="text-[var(--sl-text-dim)] truncate mr-2">{name.replace(/_/g, " ")}</span>
              <span className="text-white">{formatScore(score)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SourceGroundingSparkline
// ---------------------------------------------------------------------------

export function SourceGroundingSparkline({ history }: { history: number[] }) {
  if (!history.length) return null;

  const maxVal = Math.max(...history, 0.01);
  const minVal = Math.min(...history);
  const range = maxVal - minVal || 1;
  const recent = history[history.length - 1];
  const previous = history.length >= 2 ? history[history.length - 2] : recent;
  const trend = recent > previous ? "up" as const
    : recent < previous ? "down" as const
      : "flat" as const;
  const delta = recent - previous;
  const deltaPercent = previous !== 0 ? ((recent - previous) / Math.abs(previous)) * 100 : null;

  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center gap-3">
        <span className="text-white font-medium">{formatScore(recent)}</span>
        <TrendBadge direction={trend} delta={delta} deltaPercent={deltaPercent} />
        <span className="text-[var(--sl-text-dim)]">latest</span>
      </div>
      <div className="flex items-end gap-[2px] h-10">
        {history.map((val, i) => {
          const height = ((val - minVal) / range) * 100;
          return (
            <div
              key={i}
              className="flex-1 rounded-t transition-all"
              style={{
                height: `${Math.max(height, 5)}%`,
                background: val >= 0.6
                  ? "var(--sl-green)"
                  : val >= 0.4
                    ? "#f59e0b"
                    : "var(--sl-red)",
                opacity: i === history.length - 1 ? 1 : 0.5,
              }}
              title={`Attempt ${i + 1}: ${formatScore(val)}`}
            />
          );
        })}
      </div>
      <p className="text-xs text-[var(--sl-text-dim)]">
        Last {history.length} attempt{history.length !== 1 ? "s" : ""}
      </p>
    </div>
  );
}
