"use client";

import { Panel } from "@/components/Chrome";
import RetrievalOverlapPanel from "@/components/RetrievalOverlapPanel";
import ClaimDeltaPanel from "@/components/ClaimDeltaPanel";
import ProofGateComparisonPanel from "@/components/ProofGateComparisonPanel";
import type { RunComparisonResponse } from "@/lib/types";

interface RunComparisonPanelProps {
  comparison: RunComparisonResponse;
}

export default function RunComparisonPanel({ comparison }: RunComparisonPanelProps) {
  return (
    <div className="space-y-4">
      <Panel title="Recommendation" glow="cyan">
        <p className="text-sm text-[var(--sl-text)]">{comparison.recommendation}</p>
        <p className="mt-2 text-xs text-[var(--sl-text-dim)]">
          Compared {comparison.run_ids.length} runs at {comparison.compared_at}
        </p>
      </Panel>
      <RetrievalOverlapPanel overlap={comparison.retrieval_overlap} />
      <ClaimDeltaPanel claims={comparison.claim_deltas} />
      <ProofGateComparisonPanel proof={comparison.proof_gate_comparison} />
    </div>
  );
}
