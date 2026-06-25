"use client";

import Link from "next/link";

import { getReleaseManifest } from "@/lib/sourcelab-api";
import { useApi } from "@/lib/use-api";
import { formatScore, timeAgo } from "@/lib/format";
import {
  ConnectionCard,
  LoadingPanel,
  Metric,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill, { type PillTone } from "@/components/StatusPill";

function gateTone(status: "PASS" | "FAIL" | "UNKNOWN"): PillTone {
  return status === "PASS" ? "pass" : status === "FAIL" ? "blocked" : "missing";
}

// Release bundle steps are produced by the CLI / filesystem (artifacts/release)
// and are NOT exposed over HTTP. We surface them as a documented checklist.
const CLI_RELEASE_STEPS: Array<{ label: string; command: string; note: string }> = [
  { label: "Release bundle", command: "sourcelab release bundle", note: "Packs the local v1 GA bundle" },
  { label: "Checksums", command: "sourcelab release checksums", note: "SHA256 over the bundle" },
  { label: "SBOM", command: "sourcelab release sbom", note: "Software bill of materials" },
  { label: "Attestation", command: "sourcelab release attest", note: "Build provenance attestation" },
  { label: "Publish plan", command: "sourcelab release publish --dry-run", note: "Dry-run publish plan" },
];

export default function ReleasePage() {
  const { data, error, loading, reload } = useApi(() => getReleaseManifest(), []);

  if (loading) {
    return (
      <PageShell>
        <PageHeader title="Release Health" subtitle="Composing release readiness…" />
        <LoadingPanel />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <PageHeader title="Release Health" />
        <ConnectionCard error={error} onRetry={reload} />
      </PageShell>
    );
  }

  const manifest = data!;
  const { version, latestRun, proof, harness, evals, pqcPack } = manifest;
  const passRate = evals?.summary?.overall_pass_rate ?? null;
  const proofGate = (proof?.summary?.release_gate_status || "—").toString();

  return (
    <PageShell>
      <PageHeader
        title="Release Health"
        subtitle="Composed from live API signals (proof bundle, golden evals, harness, source pack). The full release manifest is produced by the CLI."
      >
        <StatusPill tone={gateTone(manifest.strictReleaseStatus)} label={`STRICT ${manifest.strictReleaseStatus}`} />
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Strict release" glow={manifest.strictReleaseStatus === "PASS" ? "cyan" : "violet"}>
          <div className="flex items-center justify-between">
            <span className="text-3xl font-semibold sl-gradient-text">
              {manifest.strictReleaseStatus}
            </span>
            <StatusPill tone={gateTone(manifest.strictReleaseStatus)} label="GATE" dot={false} />
          </div>
          <p className="mt-2 text-xs text-[var(--sl-text-dim)]">
            Run: <code className="text-[var(--sl-cyan)]">sourcelab verify-release --strict</code>
          </p>
        </Panel>

        <Panel title="Golden evals (pqc_v1)" glow="violet">
          <div className="flex items-center justify-between">
            <span className="text-3xl font-semibold text-white">{formatScore(passRate)}</span>
            <StatusPill tone={gateTone(manifest.goldenEvalStatus)} label={manifest.goldenEvalStatus} />
          </div>
          <p className="mt-2 text-xs text-[var(--sl-text-dim)]">
            {evals?.summary?.total_cases ?? 0} eval cases
          </p>
        </Panel>

        <Panel title="Build">
          <div className="text-lg font-semibold text-white">{version.release_label}</div>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            <span className="sl-chip">v{version.version}</span>
            <span className="sl-chip">API {version.api_version}</span>
            <span className="sl-chip">py {version.python_version}</span>
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-4">
        <Metric
          label="Proof gate"
          value={<StatusPill status={proofGate} label={proofGate.toUpperCase()} />}
        />
        <Metric
          label="Harness"
          value={
            <StatusPill
              status={harness?.passed ?? null}
              label={harness ? (harness.passed ? "PASS" : "FAIL") : "—"}
            />
          }
        />
        <Metric
          label="pqc_v1 pack"
          value={
            <StatusPill
              status={pqcPack?.installed ?? null}
              label={pqcPack?.installed ? "INSTALLED" : "NOT INSTALLED"}
            />
          }
          hint={pqcPack ? `${pqcPack.installed_count}/${pqcPack.total_sources} sources` : undefined}
        />
        <Metric
          label="Latest run"
          value={
            latestRun?.run_id ? (
              <Link href={`/runs/${latestRun.run_id}`} className="font-mono text-sm text-[var(--sl-cyan)] hover:underline">
                open
              </Link>
            ) : (
              "—"
            )
          }
          hint={latestRun?.created_at ? timeAgo(latestRun.created_at) : undefined}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="Release readiness" className="lg:col-span-1">
          <ul className="space-y-2">
            <ReadinessRow label="Strict release gate" status={manifest.strictReleaseStatus} />
            <ReadinessRow label="Golden evals (pqc_v1)" status={manifest.goldenEvalStatus} />
            <ReadinessRow
              label="Proof bundle sealed"
              status={proofGate.toUpperCase() === "PASS" ? "PASS" : proof ? "FAIL" : "UNKNOWN"}
            />
            <ReadinessRow
              label="Harness validation"
              status={harness ? (harness.passed ? "PASS" : "FAIL") : "UNKNOWN"}
            />
            <ReadinessRow
              label="Required source pack"
              status={pqcPack?.installed ? "PASS" : pqcPack ? "FAIL" : "UNKNOWN"}
            />
          </ul>
        </Panel>

        <Panel
          title="Release artifacts"
          hint="Produced by the CLI / artifacts/release — not exposed over HTTP"
          className="lg:col-span-2"
        >
          <div className="space-y-2">
            {CLI_RELEASE_STEPS.map((step) => (
              <div
                key={step.label}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] px-3 py-2.5"
              >
                <div>
                  <div className="text-sm font-medium text-white">{step.label}</div>
                  <div className="text-[0.72rem] text-[var(--sl-text-faint)]">{step.note}</div>
                </div>
                <div className="flex items-center gap-2">
                  <code className="font-mono text-[0.7rem] text-[var(--sl-cyan)]">{step.command}</code>
                  <StatusPill tone="neutral" dot={false} label="CLI" />
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </PageShell>
  );
}

function ReadinessRow({ label, status }: { label: string; status: "PASS" | "FAIL" | "UNKNOWN" }) {
  return (
    <li className="flex items-center justify-between gap-2 border-b border-[var(--sl-border)] pb-2 last:border-0">
      <span className="text-sm text-[var(--sl-text-dim)]">{label}</span>
      <StatusPill tone={gateTone(status)} label={status} />
    </li>
  );
}
