"use client";

import { Panel } from "@/components/Chrome";
import { formatJaccard } from "@/lib/batch-run";
import type { RunComparisonResponse } from "@/lib/types";

interface RetrievalOverlapPanelProps {
  overlap: RunComparisonResponse["retrieval_overlap"];
}

export default function RetrievalOverlapPanel({ overlap }: RetrievalOverlapPanelProps) {
  return (
    <Panel title="Retrieval overlap">
      <div className="space-y-3 text-sm">
        {overlap.per_run.map((row) => (
          <div key={row.run_id} className="rounded-lg border border-[var(--sl-border)] p-2.5">
            <div className="font-mono text-xs text-[var(--sl-cyan)]">{row.run_id}</div>
            <div className="mt-1 text-[var(--sl-text-dim)]">
              {row.source_count} sources · {row.chunk_count} chunks
            </div>
          </div>
        ))}
        {overlap.pairwise.map((pair) => (
          <div key={`${pair.run_id_a}-${pair.run_id_b}`} className="text-[var(--sl-text-dim)]">
            <span className="font-mono text-[var(--sl-text)]">
              {pair.run_id_a} ↔ {pair.run_id_b}
            </span>
            : source Jaccard {formatJaccard(pair.source_jaccard)}, chunk Jaccard{" "}
            {formatJaccard(pair.chunk_jaccard)}, {pair.shared_chunk_ids.length} shared chunks
          </div>
        ))}
        {overlap.all_shared_chunk_ids.length > 0 && (
          <p className="text-xs text-[var(--sl-text-faint)]">
            All runs share {overlap.all_shared_chunk_ids.length} chunks.
          </p>
        )}
      </div>
    </Panel>
  );
}
