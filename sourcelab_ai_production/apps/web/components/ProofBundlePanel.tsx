import type { ProofBundleResponse } from "@/lib/types";
import { formatScore } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

interface ProofBundlePanelProps {
  proof: ProofBundleResponse | null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

export default function ProofBundlePanel({ proof }: ProofBundlePanelProps) {
  if (!proof) {
    return <p className="text-sm text-[var(--sl-text-faint)]">No proof bundle recorded.</p>;
  }

  const summary = proof.summary ?? {};
  const manifest = proof.manifest ?? {};

  const gate = (summary.release_gate_status || proof.status || "unknown").toString();
  const totalArtifacts = asNumber(manifest.total_artifacts) ?? summary.artifact_count ?? null;
  const requiredArtifacts = asNumber(manifest.required_artifacts);
  const missingRequired = asStringArray(manifest.missing_required);
  const invalidArtifacts = asStringArray(manifest.invalid_artifacts);

  const cells: Array<{ label: string; value: string; tone?: string }> = [
    { label: "Artifacts", value: totalArtifacts !== null ? String(totalArtifacts) : "—" },
    {
      label: "Required",
      value: requiredArtifacts !== null ? String(requiredArtifacts) : "—",
    },
    {
      label: "Citation res.",
      value: formatScore(summary.citation_resolution_rate ?? null),
    },
    {
      label: "High-risk",
      value: String(summary.unsupported_high_risk_claims ?? 0),
      tone: (summary.unsupported_high_risk_claims ?? 0) > 0 ? "text-[var(--sl-rose)]" : undefined,
    },
    {
      label: "Conflicts",
      value: String(summary.conflicts_detected ?? 0),
      tone: (summary.conflicts_detected ?? 0) > 0 ? "text-[var(--sl-rose)]" : undefined,
    },
    {
      label: "Review items",
      value: String(summary.human_review_items ?? 0),
      tone: (summary.human_review_items ?? 0) > 0 ? "text-[var(--sl-amber)]" : undefined,
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-[var(--sl-text-dim)]">Release gate</span>
        <StatusPill status={gate} label={`GATE ${gate.toUpperCase()}`} />
      </div>

      <div className="grid grid-cols-3 gap-2">
        {cells.map((cell) => (
          <div
            key={cell.label}
            className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2"
          >
            <div className={`text-base font-semibold ${cell.tone ?? "text-white"}`}>{cell.value}</div>
            <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
              {cell.label}
            </div>
          </div>
        ))}
      </div>

      {(missingRequired.length > 0 || invalidArtifacts.length > 0) && (
        <div className="space-y-1.5 rounded-lg border border-[rgba(251,113,133,0.3)] bg-[rgba(251,113,133,0.06)] p-2.5">
          {missingRequired.length > 0 && (
            <p className="text-xs text-[var(--sl-rose)]">
              Missing required: {missingRequired.join(", ")}
            </p>
          )}
          {invalidArtifacts.length > 0 && (
            <p className="text-xs text-[var(--sl-rose)]">
              Invalid: {invalidArtifacts.join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
