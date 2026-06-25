"use client";

import Link from "next/link";

import { listRuns } from "@/lib/sourcelab-api";
import { useApi } from "@/lib/use-api";
import { formatScore, timeAgo, truncate } from "@/lib/format";
import {
  ConnectionCard,
  EmptyState,
  LoadingPanel,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";

export default function RunsPage() {
  const { data, error, loading, reload } = useApi(() => listRuns(), []);

  return (
    <PageShell>
      <PageHeader
        title="Runs"
        subtitle="Every source-grounded generation field recorded under artifacts/runs."
      >
        <Link href="/runs/new" className="sl-btn sl-btn--primary">
          New lesson
        </Link>
        <Link href="/runs/compare" className="sl-btn">
          Compare
        </Link>
        {data && (
          <span className="sl-pill sl-pill--neutral">
            <span className="sl-pill__dot" /> {data.total} runs
          </span>
        )}
      </PageHeader>

      {loading && <LoadingPanel label="Loading run index…" />}
      {error && <ConnectionCard error={error} onRetry={reload} />}

      {data && data.runs.length === 0 && (
        <EmptyState
          title="No runs yet"
          message={
            <>
              <Link href="/runs/new" className="text-[var(--sl-cyan)] hover:underline">
                Create a run
              </Link>{" "}
              or generate one with <code className="text-[var(--sl-cyan)]">sourcelab local-demo</code>{" "}
              and refresh.
            </>
          }
        />
      )}

      {data && data.runs.length > 0 && (
        <Panel>
          <div className="overflow-auto">
            <table className="sl-table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Topic</th>
                  <th>Harness</th>
                  <th>Answer</th>
                  <th>Citations</th>
                  <th className="text-right">Artifacts</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {[...data.runs].reverse().map((run) => (
                  <tr key={run.run_id}>
                    <td>
                      <Link
                        href={`/runs/${run.run_id}`}
                        className="font-mono text-xs text-[var(--sl-cyan)] hover:underline"
                      >
                        {run.run_id}
                      </Link>
                    </td>
                    <td className="max-w-xs text-[var(--sl-text)]" title={run.topic}>
                      {truncate(run.topic, 60) || "—"}
                    </td>
                    <td>
                      <StatusPill
                        status={run.harness_passed}
                        label={
                          run.harness_passed === null
                            ? "—"
                            : run.harness_passed
                              ? "PASS"
                              : "FAIL"
                        }
                      />
                    </td>
                    <td className="font-mono text-xs">
                      {run.has_answer ? (
                        <span className="text-[var(--sl-text)]">{formatScore(run.answer_score)}</span>
                      ) : (
                        <span className="text-[var(--sl-text-faint)]">none</span>
                      )}
                    </td>
                    <td className="font-mono text-xs text-[var(--sl-text-dim)]">
                      {formatScore(run.citation_resolution_rate)}
                    </td>
                    <td className="text-right font-mono text-xs text-[var(--sl-text-dim)]">
                      {run.artifact_count}
                    </td>
                    <td className="text-xs text-[var(--sl-text-faint)]" title={run.created_at}>
                      {timeAgo(run.created_at)}
                    </td>
                    <td className="text-right">
                      <Link href={`/runs/${run.run_id}`} className="sl-btn px-3 py-1 text-xs">
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </PageShell>
  );
}
