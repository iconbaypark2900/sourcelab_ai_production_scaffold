"use client";

import Link from "next/link";

import LibraryShelf from "@/components/LibraryShelf";
import ResearchPathMap from "@/components/ResearchPathMap";
import {
  ConnectionCard,
  LoadingPanel,
  Metric,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  buildCollectionCardModel,
  buildStudyPathSteps,
  groupCollectionsByShelf,
  LIBRARY_TERMS,
} from "@/lib/library-theme";
import { formatScore, timeAgo } from "@/lib/format";
import {
  getHealth,
  getLatestEvals,
  getReleaseManifest,
  getSourcePackStatus,
  getSourcePacks,
  validateSourcePack,
} from "@/lib/sourcelab-api";
import { useApi } from "@/lib/use-api";

async function settle<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

export default function HomePage() {
  const { data, error, loading, reload } = useApi(async () => {
    const [health, manifest, packsRes] = await Promise.all([
      getHealth(),
      getReleaseManifest(),
      getSourcePacks(),
    ]);
    const collections = await Promise.all(
      packsRes.packs.map(async (pack) => {
        const [status, validation, evals] = await Promise.all([
          settle(getSourcePackStatus(pack.pack_name)),
          settle(validateSourcePack(pack.pack_name)),
          settle(getLatestEvals(pack.pack_name)),
        ]);
        return buildCollectionCardModel(
          pack,
          status,
          validation,
          evals?.summary?.overall_pass_rate ?? null,
        );
      }),
    );
    return { health, manifest, collections, packTotal: packsRes.total };
  }, []);

  if (loading) {
    return (
      <PageShell>
        <PageHeader title={LIBRARY_TERMS.home} subtitle="Opening the research library…" />
        <LoadingPanel />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <PageHeader title={LIBRARY_TERMS.home} />
        <ConnectionCard error={error} onRetry={reload} />
      </PageShell>
    );
  }

  const { health, manifest, collections, packTotal } = data!;
  const { version, latestRun, evals, strictReleaseStatus, goldenEvalStatus } = manifest;
  const passRate = evals?.summary?.overall_pass_rate ?? null;
  const shelves = groupCollectionsByShelf(collections, { hideTemplate: true });

  const demoPath = buildStudyPathSteps({
    hasLesson: Boolean(latestRun?.run_id),
    hasChunks: true,
    proofPassed: latestRun?.harness_passed ?? false,
    hasAttempts: Boolean(latestRun?.has_answer),
  });

  return (
    <PageShell>
      <PageHeader
        title={
          <>
            SourceLab <span className="sl-gradient-text">Research Library</span>
          </>
        }
        subtitle="An educational interactive research library — source-grounded lessons, evidence review, and study journals on your local shelf."
      >
        <StatusPill status={health.status} label={`API ${health.status.toUpperCase()}`} />
        <Link href="/runs/new" className="sl-btn sl-btn--primary">
          Start lesson
        </Link>
      </PageHeader>

      <Panel title="Quick actions" glow="cyan" className="mb-4">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <Link href="/runs/new" className="sl-btn justify-between">
            Start lesson <span aria-hidden>&rarr;</span>
          </Link>
          <Link href="/source-packs" className="sl-btn justify-between">
            Browse collections <span aria-hidden>&rarr;</span>
          </Link>
          {latestRun?.run_id ? (
            <Link href={`/runs/${latestRun.run_id}`} className="sl-btn justify-between">
              Latest run <span aria-hidden>&rarr;</span>
            </Link>
          ) : (
            <span className="sl-btn opacity-50">Latest run — none yet</span>
          )}
          <Link href="/batches/new" className="sl-btn justify-between">
            Create study set <span aria-hidden>&rarr;</span>
          </Link>
          <Link href="/source-packs" className="sl-btn justify-between">
            Review collections <span aria-hidden>&rarr;</span>
          </Link>
        </div>
      </Panel>

      {latestRun?.run_id && (
        <div className="mb-4">
          <ResearchPathMap steps={demoPath} title={LIBRARY_TERMS.studyPath} />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Library edition" glow="cyan">
          <div className="space-y-3">
            <div className="text-2xl font-semibold text-white">{version.release_label}</div>
            <div className="flex flex-wrap gap-2 text-xs text-[var(--sl-text-dim)]">
              <span className="sl-chip">v{version.version}</span>
              <span className="sl-chip">{packTotal} collections</span>
            </div>
          </div>
        </Panel>

        <Panel title="Strict release shelf" glow={strictReleaseStatus === "PASS" ? "cyan" : "violet"}>
          <div className="flex items-center justify-between">
            <div className="text-2xl font-semibold text-white">Gate</div>
            <StatusPill
              tone={
                strictReleaseStatus === "PASS"
                  ? "pass"
                  : strictReleaseStatus === "FAIL"
                    ? "blocked"
                    : "missing"
              }
              label={strictReleaseStatus}
            />
          </div>
          <p className="mt-2 text-xs text-[var(--sl-text-dim)]">
            pqc_v1 strict-release requirement for production bundles.
          </p>
          <Link href="/release" className="sl-btn mt-3 w-full justify-center">
            Release health
          </Link>
        </Panel>

        <Panel title="Golden evals" glow="violet">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-semibold text-white">{formatScore(passRate)}</div>
            <StatusPill
              tone={
                goldenEvalStatus === "PASS"
                  ? "pass"
                  : goldenEvalStatus === "FAIL"
                    ? "blocked"
                    : "missing"
              }
              label={goldenEvalStatus}
            />
          </div>
          <Link href="/source-packs" className="sl-btn mt-3 w-full justify-center">
            View collections
          </Link>
        </Panel>
      </div>

      <div className="mt-6 space-y-8">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-white">Library shelves</h2>
          <Link href="/source-packs" className="text-xs text-[var(--sl-cyan)] hover:underline">
            All collections →
          </Link>
        </div>
        {shelves.map((group) => (
          <LibraryShelf key={group.shelf.id} shelf={group.shelf} collections={group.collections} compact />
        ))}
      </div>

      {latestRun && latestRun.run_id && (
        <Panel title="Latest study session" className="mt-6" glow="cyan">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-mono text-sm text-[var(--sl-cyan)]">{latestRun.run_id}</div>
                <div className="truncate text-base font-medium text-white" title={latestRun.topic}>
                  {latestRun.topic || "—"}
                </div>
                <div className="mt-0.5 text-[0.72rem] text-[var(--sl-text-faint)]">
                  {timeAgo(latestRun.created_at)}
                </div>
              </div>
              <Link href={`/runs/${latestRun.run_id}`} className="sl-btn sl-btn--primary">
                Open Reading Room
              </Link>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric
                label="Harness"
                value={
                  <StatusPill
                    status={latestRun.harness_passed}
                    label={latestRun.harness_passed ? "PASS" : "FAIL"}
                  />
                }
              />
              <Metric label="Citations" value={formatScore(latestRun.citation_resolution_rate)} tone="cyan" />
              <Metric
                label="Journal"
                value={latestRun.has_answer ? formatScore(latestRun.answer_score) : "none"}
                tone="violet"
              />
              <Metric label="Artifacts" value={latestRun.artifact_count} />
            </div>
          </div>
        </Panel>
      )}
    </PageShell>
  );
}
