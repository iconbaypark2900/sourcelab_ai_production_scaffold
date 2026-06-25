"use client";

import { useMemo } from "react";

import EvidenceField from "@/components/EvidenceField";
import { EmptyState, Panel } from "@/components/Chrome";
import { LIBRARY_EMPTY_STATES, mapEvidenceForDrawer } from "@/lib/library-theme";
import type { RetrievedChunk, RetrievalDiagnostics } from "@/lib/types";

interface EvidenceDrawerProps {
  chunks: RetrievedChunk[];
  diagnostics?: RetrievalDiagnostics | null;
}

export default function EvidenceDrawer({ chunks, diagnostics }: EvidenceDrawerProps) {
  const drawerItems = useMemo(() => mapEvidenceForDrawer(chunks), [chunks]);

  if (!chunks.length) {
    return (
      <EmptyState
        title={LIBRARY_EMPTY_STATES.noEvidence.title}
        message={LIBRARY_EMPTY_STATES.noEvidence.message}
      />
    );
  }

  return (
    <div className="space-y-4">
      <Panel title="Evidence Drawer" hint="Source cards · chunks · trust labels" glow="cyan">
        <p className="mb-3 text-xs text-[var(--sl-text-dim)]">
          Each excerpt is a retrieved passage from your collection. Expand cards to read previews and
          compare trust tiers before citing in your Study Journal.
        </p>
        <div className="mb-4 grid gap-2 sm:grid-cols-3">
          {drawerItems.slice(0, 6).map((item) => (
            <div
              key={item.chunkId}
              className="rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.4)] px-2.5 py-2"
            >
              <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
                {item.label}
              </div>
              <div className="mt-0.5 truncate font-mono text-xs text-[var(--sl-cyan)]">
                {item.sourceId}
              </div>
              <div className="mt-1 font-mono text-[0.68rem] text-[var(--sl-parchment-dim)]">
                score {item.score.toFixed(3)} · tier {item.trustTier}
              </div>
            </div>
          ))}
        </div>
        <EvidenceField chunks={chunks} diagnostics={diagnostics} />
      </Panel>
    </div>
  );
}
