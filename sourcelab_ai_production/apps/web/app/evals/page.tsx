"use client";

import {
  getEvalsThresholds,
  getLatestEvals,
  getSourcePacks,
  type SourceLabApiError,
} from "@/lib/sourcelab-api";
import { useApi } from "@/lib/use-api";
import { formatScore } from "@/lib/format";
import {
  aggregateEvals,
  isEvaluated,
  isPassing,
  STRICT_RELEASE_PACK,
  strictReleaseEvalStatus,
  type EvalsAggregate,
} from "@/lib/evals-summary";
import { complianceTone } from "@/lib/eval-thresholds";
import {
  ConnectionCard,
  LoadingPanel,
  Metric,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import PackEvalCard from "@/components/PackEvalCard";
import StatusPill from "@/components/StatusPill";
import type { PackThresholdResponse } from "@/lib/types";

async function settle<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

interface EvalsPageData extends EvalsAggregate {
  packs: Array<{
    pack_name: string;
    evals: Awaited<ReturnType<typeof getLatestEvals>> | null;
    thresholds: PackThresholdResponse | null;
  }>;
}

export default function EvalsPage() {
  const { data, error, loading, reload } = useApi<EvalsPageData>(async () => {
    const packsRes = await getSourcePacks();
    const packs = await Promise.all(
      packsRes.packs.map(async (pack) => ({
        pack_name: pack.pack_name,
        evals: await settle(getLatestEvals(pack.pack_name)),
        thresholds: await settle(getEvalsThresholds(pack.pack_name)),
      })),
    );

    return { packs, ...aggregateEvals(packs) };
  }, []);

  const strictStatus = data ? strictReleaseEvalStatus(data.packs) : "NO_EVALS";
  const thresholdPassing =
    data?.packs.filter((p) => p.thresholds && complianceTone(p.thresholds) === "pass")
      .length ?? 0;

  return (
    <PageShell>
      <PageHeader
        title="Golden Evals"
        subtitle="Golden evaluation results across all source packs. Run evals to refresh results for any pack."
      >
        {data && (
          <span className="sl-pill sl-pill--neutral">
            <span className="sl-pill__dot" /> {data.evaluatedPacks}/{data.totalPacks} evaluated
          </span>
        )}
      </PageHeader>

      {loading && <LoadingPanel label="Loading golden evals…" />}
      {error && (
        <ConnectionCard error={error as SourceLabApiError} onRetry={reload} />
      )}

      {data && (
        <>
          <div className="mb-5 grid gap-4 lg:grid-cols-4">
            <Metric
              label="Packs evaluated"
              value={`${data.evaluatedPacks}/${data.totalPacks}`}
              tone="cyan"
            />
            <Metric
              label="Packs passing"
              value={data.passingPacks}
              tone={data.passingPacks === data.totalPacks && data.totalPacks > 0 ? "good" : "warn"}
            />
            <Metric
              label="Thresholds met"
              value={`${thresholdPassing}/${data.totalPacks}`}
              tone={
                thresholdPassing === data.totalPacks && data.totalPacks > 0
                  ? "good"
                  : "warn"
              }
            />
            <Metric
              label="Strict release"
              value={
                <StatusPill
                  tone={strictStatus === "PASS" ? "pass" : "missing"}
                  label={strictStatus}
                />
              }
              hint="pqc_v1"
            />
          </div>

          {data.packs.length === 0 && (
            <div className="sl-panel flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
              <div className="text-base font-semibold text-white">No source packs found</div>
              <div className="max-w-md text-sm text-[var(--sl-text-dim)]">
                Bootstrap packs with{" "}
                <code className="text-[var(--sl-cyan)]">
                  python scripts/bootstrap_sourcelab_source_packs.py --packs all
                </code>
              </div>
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            {data.packs.map((pack) => (
              <PackEvalCard
                key={pack.pack_name}
                packName={pack.pack_name}
                evals={pack.evals}
                thresholds={pack.thresholds}
                strictRequired={pack.pack_name === STRICT_RELEASE_PACK}
              />
            ))}
          </div>

          <p className="mt-6 text-xs text-[var(--sl-text-faint)]">
            CLI:{" "}
            <code className="text-[var(--sl-cyan)]">sourcelab evals run --pack &lt;pack&gt;</code>{" "}
            and{" "}
            <code className="text-[var(--sl-cyan)]">sourcelab evals thresholds show --pack &lt;pack&gt;</code>
          </p>
        </>
      )}
    </PageShell>
  );
}
