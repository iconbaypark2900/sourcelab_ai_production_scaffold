"use client";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import type { RunComparisonResponse } from "@/lib/types";

interface ProofGateComparisonPanelProps {
  proof: RunComparisonResponse["proof_gate_comparison"];
}

export default function ProofGateComparisonPanel({ proof }: ProofGateComparisonPanelProps) {
  return (
    <Panel title="Proof / harness gates">
      <div className="mb-3 flex flex-wrap gap-2">
        <StatusPill
          tone={proof.all_passed_harness ? "pass" : "blocked"}
          label={proof.all_passed_harness ? "ALL HARNESS PASS" : "HARNESS GAPS"}
        />
        <StatusPill
          tone={proof.all_passed_proof ? "pass" : "review"}
          label={proof.all_passed_proof ? "ALL PROOF PASS" : "PROOF REVIEW"}
        />
      </div>
      <div className="space-y-2 text-sm">
        {proof.per_run.map((row) => (
          <div key={row.run_id} className="rounded-lg border border-[var(--sl-border)] p-2.5">
            <div className="font-mono text-xs text-[var(--sl-cyan)]">{row.run_id}</div>
            <div className="mt-1 flex flex-wrap gap-2 text-xs text-[var(--sl-text-dim)]">
              <span>Harness: {row.harness_passed ? "PASS" : "FAIL"}</span>
              <span>Proof: {row.proof_bundle_status || "unknown"}</span>
              <span>Gate: {row.release_gate_status || "unknown"}</span>
              <span>{row.artifact_count} artifacts</span>
              {row.missing_required.length > 0 && (
                <span className="text-[var(--sl-rose)]">
                  missing {row.missing_required.length} required
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
