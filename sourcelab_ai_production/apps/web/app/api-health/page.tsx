"use client";

import {
  API_BASE_URL,
  getHealth,
  getModelConfig,
  getModelHealth,
  getReadiness,
  getVersion,
} from "@/lib/sourcelab-api";
import { useApi } from "@/lib/use-api";
import { humanize } from "@/lib/format";
import {
  ConnectionCard,
  LoadingPanel,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";

async function settle<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--sl-border)] py-2 last:border-0">
      <span className="text-xs uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">{label}</span>
      <span className="break-all text-right text-sm text-[var(--sl-text)]">{value}</span>
    </div>
  );
}

export default function ApiHealthPage() {
  const { data, error, loading, reload } = useApi(async () => {
    const [health, readiness, version] = await Promise.all([
      getHealth(),
      getReadiness(),
      getVersion(),
    ]);
    const [modelConfig, modelHealth] = await Promise.all([
      settle(getModelConfig()),
      settle(getModelHealth()),
    ]);
    return { health, readiness, version, modelConfig, modelHealth };
  }, []);

  return (
    <PageShell>
      <PageHeader title="API Health" subtitle={`SourceLab FastAPI backend at ${API_BASE_URL}`}>
        {data && <StatusPill status={data.health.status} label={`HEALTH ${data.health.status.toUpperCase()}`} />}
      </PageHeader>

      {loading && <LoadingPanel label="Pinging backend…" />}
      {error && <ConnectionCard error={error} onRetry={reload} />}

      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Liveness & readiness" glow="cyan">
            <div className="mb-3 flex items-center gap-2">
              <StatusPill status={data.health.status} label={`/health ${data.health.status}`} />
              <StatusPill status={data.readiness.status} label={`/ready ${data.readiness.status}`} />
            </div>
            <div className="space-y-0">
              {Object.entries(data.readiness.components).map(([name, value]) => (
                <DetailRow
                  key={name}
                  label={humanize(name)}
                  value={<StatusPill status={value} label={value} />}
                />
              ))}
              {Object.keys(data.readiness.components).length === 0 && (
                <p className="text-sm text-[var(--sl-text-faint)]">No component details reported.</p>
              )}
            </div>
          </Panel>

          <Panel title="Version" glow="violet">
            <div className="space-y-0">
              <DetailRow label="Release" value={data.version.release_label} />
              <DetailRow label="Version" value={data.version.version} />
              <DetailRow label="API version" value={data.version.api_version} />
              <DetailRow label="Python" value={data.version.python_version} />
              <DetailRow label="Project root" value={data.version.project_root} />
              <DetailRow label="Artifacts dir" value={data.version.artifacts_directory} />
            </div>
          </Panel>

          <Panel title="Model router config">
            {data.modelConfig ? (
              <div className="space-y-0">
                <DetailRow label="Mode" value={data.modelConfig.mode} />
                <DetailRow label="Backend" value={data.modelConfig.backend} />
                <DetailRow label="Model" value={data.modelConfig.model_name || "—"} />
                <DetailRow label="Base URL" value={data.modelConfig.base_url || "—"} />
                <DetailRow label="Timeout" value={`${data.modelConfig.timeout_seconds}s`} />
                <DetailRow label="Fallback" value={data.modelConfig.fallback} />
              </div>
            ) : (
              <p className="text-sm text-[var(--sl-text-faint)]">Model config unavailable.</p>
            )}
          </Panel>

          <Panel title="Model backend health">
            {data.modelHealth ? (
              <div className="space-y-0">
                <DetailRow
                  label="Available"
                  value={
                    <StatusPill
                      status={data.modelHealth.available}
                      label={data.modelHealth.available ? "AVAILABLE" : "UNAVAILABLE"}
                    />
                  }
                />
                <DetailRow label="Backend" value={data.modelHealth.backend} />
                <DetailRow label="Model" value={data.modelHealth.model_name || "—"} />
                <DetailRow label="Latency" value={`${data.modelHealth.latency_ms.toFixed(1)} ms`} />
                {data.modelHealth.error && (
                  <DetailRow label="Error" value={<span className="text-[var(--sl-rose)]">{data.modelHealth.error}</span>} />
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--sl-text-faint)]">
                Model health endpoint unavailable (deterministic backend needs no live model).
              </p>
            )}
          </Panel>
        </div>
      )}
    </PageShell>
  );
}
