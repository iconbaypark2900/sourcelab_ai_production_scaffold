"use client";

import type { ReactNode } from "react";

import { Panel } from "@/components/Chrome";
import SourceChip from "@/components/SourceChip";
import StatusPill from "@/components/StatusPill";
import {
  computeSourceCoverageDetails,
  computeSourceCoverageLabels,
} from "@/lib/research-validation";
import type { ResearchValidationInput } from "@/lib/research-validation";

interface SourceCoveragePanelProps {
  input: ResearchValidationInput;
}

export default function SourceCoveragePanel({ input }: SourceCoveragePanelProps) {
  const coverage = computeSourceCoverageDetails(input);
  const labels = computeSourceCoverageLabels(input);

  return (
    <Panel title="Source coverage" hint="Used vs unused pack sources" glow="cyan" id="research-source-coverage">
      <div className="mb-3 flex flex-wrap gap-1">
        {labels.map((label) => (
          <StatusPill key={label.key} tone={label.tone} label={label.text} dot={false} />
        ))}
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-3">
        <Stat label="Retrieved sources" value={String(coverage.usedSourceIds.length)} />
        <Stat label="Chunks" value={String(coverage.chunkCount)} />
        <Stat label="Unused pack sources" value={String(coverage.unusedSourceIds.length)} />
      </div>

      <Section title="Sources used">
        {coverage.usedSourceIds.length ? (
          <div className="flex flex-wrap gap-1.5">
            {coverage.usedSourceIds.map((sourceId) => {
              const chunk = input.chunks.find((row) => row.source_id === sourceId);
              return (
                <SourceChip
                  key={sourceId}
                  sourceId={sourceId}
                  trustTier={chunk?.trust_tier}
                />
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-[var(--sl-text-faint)]">No sources retrieved.</p>
        )}
      </Section>

      {coverage.unusedSourceIds.length > 0 && (
        <Section title="Sources in lesson package but not retrieved">
          <div className="flex flex-wrap gap-1.5">
            {coverage.unusedSourceIds.map((sourceId) => (
              <span key={sourceId} className="sl-pill sl-pill--neutral font-mono text-xs">
                {sourceId}
              </span>
            ))}
          </div>
        </Section>
      )}

      <Section title="Trust tier distribution">
        <div className="flex flex-wrap gap-2">
          {Object.entries(coverage.trustTierCounts).map(([tier, count]) => (
            <span key={tier} className="text-xs text-[var(--sl-text-dim)]">
              Tier {tier}: <span className="font-mono text-white">{count}</span>
            </span>
          ))}
        </div>
      </Section>

      {input.chunks.length > 0 && (
        <Section title="Retrieved chunks">
          <ul className="space-y-1 text-xs text-[var(--sl-text-dim)]">
            {input.chunks.map((chunk) => (
              <li key={chunk.chunk_id} className="font-mono">
                {chunk.chunk_id} · score {chunk.score.toFixed(3)}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </Panel>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-4 border-t border-[var(--sl-border)] pt-3">
      <div className="mb-2 text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {title}
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2">
      <div className="text-base font-semibold text-white">{value}</div>
      <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {label}
      </div>
    </div>
  );
}
