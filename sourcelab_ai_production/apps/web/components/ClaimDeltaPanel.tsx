"use client";

import { Panel } from "@/components/Chrome";
import { formatScore } from "@/lib/format";
import type { RunComparisonResponse } from "@/lib/types";

interface ClaimDeltaPanelProps {
  claims: RunComparisonResponse["claim_deltas"];
}

export default function ClaimDeltaPanel({ claims }: ClaimDeltaPanelProps) {
  return (
    <Panel title="Claim deltas">
      <div className="space-y-3 text-sm">
        {claims.per_run.map((row) => (
          <div key={row.run_id} className="rounded-lg border border-[var(--sl-border)] p-2.5">
            <div className="font-mono text-xs text-[var(--sl-cyan)]">{row.run_id}</div>
            <div className="mt-1 text-[var(--sl-text-dim)]">
              {row.supported_claims}/{row.total_claims} supported · resolution{" "}
              {formatScore(row.citation_resolution_rate)} · high-risk {row.unsupported_high_risk}
            </div>
          </div>
        ))}
        {claims.pairwise_deltas.map((delta) => (
          <div key={`${delta.run_id_a}-${delta.run_id_b}`} className="text-xs text-[var(--sl-text-dim)]">
            {delta.run_id_a} → {delta.run_id_b}: supported Δ
            {delta.supported_delta >= 0 ? "+" : ""}
            {delta.supported_delta}
            {delta.resolution_rate_delta !== null &&
              `, resolution Δ${(delta.resolution_rate_delta * 100).toFixed(1)}pp`}
          </div>
        ))}
      </div>
    </Panel>
  );
}
