"use client";

import { useState } from "react";

import type { RetrievedChunk, RetrievalDiagnostics } from "@/lib/types";
import { clamp } from "@/lib/format";
import SourceChip from "@/components/SourceChip";

interface EvidenceFieldProps {
  chunks: RetrievedChunk[];
  diagnostics?: RetrievalDiagnostics | null;
}

function ParticleRow({ chunk, maxScore }: { chunk: RetrievedChunk; maxScore: number }) {
  const [open, setOpen] = useState(false);
  const width = maxScore > 0 ? clamp((chunk.score / maxScore) * 100, 4, 100) : 4;

  return (
    <div className="sl-particle p-3">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-3 text-left"
        aria-expanded={open}
      >
        <SourceChip sourceId={chunk.source_id} trustTier={chunk.trust_tier} />
        <div className="ml-auto flex items-center gap-3">
          <div className="hidden w-24 sm:block">
            <div className="sl-bar">
              <div className="sl-bar__fill" style={{ width: `${width}%` }} />
            </div>
          </div>
          <span className="font-mono text-xs text-[var(--sl-cyan)]">{chunk.score.toFixed(4)}</span>
          <span className="text-xs text-[var(--sl-text-faint)]">{open ? "\u2212" : "+"}</span>
        </div>
      </button>

      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span className="truncate font-mono text-[0.68rem] text-[var(--sl-text-faint)]" title={chunk.chunk_id}>
          {chunk.chunk_id}
        </span>
      </div>

      {open && (
        <p className="sl-fade-up mt-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] p-2.5 text-xs leading-relaxed text-[var(--sl-text-dim)]">
          {chunk.text_preview || "No preview available."}
        </p>
      )}
    </div>
  );
}

export default function EvidenceField({ chunks, diagnostics }: EvidenceFieldProps) {
  if (!chunks.length) {
    return (
      <p className="text-sm text-[var(--sl-text-faint)]">
        No retrieved chunks recorded for this run.
      </p>
    );
  }

  const maxScore = Math.max(...chunks.map((chunk) => chunk.score), 0);

  return (
    <div className="space-y-3">
      {diagnostics && (
        <div className="flex flex-wrap items-center gap-2 text-[0.7rem] text-[var(--sl-text-dim)]">
          <span className="sl-pill sl-pill--neutral">mode {diagnostics.mode ?? "—"}</span>
          <span className="sl-pill sl-pill--neutral">backend {diagnostics.backend ?? "—"}</span>
          <span className="sl-pill sl-pill--neutral">
            {diagnostics.result_count ?? chunks.length}/{diagnostics.total_chunks ?? "?"} chunks
          </span>
        </div>
      )}
      <div className="space-y-2">
        {chunks.map((chunk) => (
          <ParticleRow key={chunk.chunk_id} chunk={chunk} maxScore={maxScore} />
        ))}
      </div>
    </div>
  );
}
