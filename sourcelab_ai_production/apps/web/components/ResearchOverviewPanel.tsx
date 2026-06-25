"use client";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  buildResearchOverviewMetrics,
  computeResearchVerdict,
  lessonQualityLabelText,
  lessonQualityLabelTone,
  researchVerdictText,
  researchVerdictTone,
} from "@/lib/research-validation";
import type { ResearchValidationInput } from "@/lib/research-validation";
import { formatScore } from "@/lib/format";

interface ResearchOverviewPanelProps {
  input: ResearchValidationInput;
}

export default function ResearchOverviewPanel({ input }: ResearchOverviewPanelProps) {
  const metrics = buildResearchOverviewMetrics(input);
  const verdict = computeResearchVerdict(input);

  return (
    <Panel title="Research overview" hint="Deterministic study-readiness verdict" glow="cyan" id="research-overview">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <StatusPill tone={researchVerdictTone(verdict)} label={researchVerdictText(verdict)} />
        <StatusPill
          tone={lessonQualityLabelTone(metrics.lessonQualityLabel)}
          label={lessonQualityLabelText(metrics.lessonQualityLabel)}
          dot={false}
        />
        {metrics.sourceLabels.map((label) => (
          <StatusPill key={label.key} tone={label.tone} label={label.text} dot={false} />
        ))}
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Support rate" value={formatScore(metrics.supportRate)} />
        <Metric label="Citation resolution" value={formatScore(metrics.citationResolutionRate)} />
        <Metric label="Sources / chunks" value={`${metrics.sourceCount} / ${metrics.chunkCount}`} />
        <Metric
          label="Claims"
          value={`${metrics.supportedClaims}/${metrics.totalClaims} supported`}
        />
        <Metric label="Needs review" value={String(metrics.needsReviewCount)} />
        <Metric label="Unsupported" value={String(metrics.unsupportedClaims)} />
        <Metric label="Conflicting" value={String(metrics.conflictingClaims)} />
        <Metric label="Topic" value={input.run.topic ?? "—"} />
      </div>
    </Panel>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2">
      <div className="text-base font-semibold text-white">{value}</div>
      <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {label}
      </div>
    </div>
  );
}
