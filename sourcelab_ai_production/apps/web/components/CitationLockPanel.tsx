import type { CitationResolution, SourceGroundingReview } from "@/lib/types";
import { clamp, formatScore } from "@/lib/format";
import StatusPill from "@/components/StatusPill";
import SourceChip from "@/components/SourceChip";

interface CitationLockPanelProps {
  citation: CitationResolution | null;
  grounding?: SourceGroundingReview | null;
}

function Segment({ value, total, color, label }: { value: number; total: number; color: string; label: string }) {
  if (!value || total <= 0) {
    return null;
  }
  const width = clamp((value / total) * 100, 0, 100);
  return <div title={`${label}: ${value}`} style={{ width: `${width}%`, background: color }} />;
}

export default function CitationLockPanel({ citation, grounding }: CitationLockPanelProps) {
  if (!citation) {
    return <p className="text-sm text-[var(--sl-text-faint)]">No citation resolution recorded.</p>;
  }

  const total = citation.total_claims || 0;
  const locked = citation.resolution_rate >= 1 && !citation.has_blocking_issues;

  const stats: Array<{ label: string; value: number; tone: string }> = [
    { label: "Supported", value: citation.supported_claims, tone: "text-[var(--sl-emerald)]" },
    { label: "Unsupported", value: citation.unsupported_claims, tone: "text-[var(--sl-text-dim)]" },
    { label: "Uncertain", value: citation.uncertain_claims, tone: "text-[var(--sl-amber)]" },
    { label: "Conflicting", value: citation.conflicting_claims, tone: "text-[var(--sl-rose)]" },
    { label: "High-risk", value: citation.unsupported_high_risk, tone: "text-[var(--sl-rose)]" },
    { label: "Needs review", value: citation.needs_review, tone: "text-[var(--sl-amber)]" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-3xl font-semibold text-white">
            {formatScore(citation.resolution_rate)}
          </div>
          <div className="text-xs text-[var(--sl-text-dim)]">citation resolution</div>
        </div>
        <StatusPill
          tone={locked ? "pass" : citation.has_blocking_issues ? "blocked" : "review"}
          label={locked ? "CITATIONS LOCKED" : citation.has_blocking_issues ? "LOCK BLOCKED" : "LOCKING"}
        />
      </div>

      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-[rgba(125,152,214,0.12)]">
        <Segment value={citation.supported_claims} total={total} color="var(--sl-emerald)" label="Supported" />
        <Segment value={citation.uncertain_claims} total={total} color="var(--sl-amber)" label="Uncertain" />
        <Segment value={citation.conflicting_claims} total={total} color="var(--sl-rose)" label="Conflicting" />
        <Segment value={citation.unsupported_claims} total={total} color="rgba(95,108,146,0.6)" label="Unsupported" />
      </div>

      <div className="grid grid-cols-3 gap-2">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2"
          >
            <div className={`text-lg font-semibold ${stat.tone}`}>{stat.value}</div>
            <div className="text-[0.64rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {grounding && (
        <div className="rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] p-3">
          <div className="flex items-center justify-between">
            <span className="sl-panel-title">Source grounding</span>
            <span className="font-mono text-xs text-[var(--sl-cyan)]">
              {formatScore(grounding.source_grounding_score, 2)}
            </span>
          </div>
          <p className="mt-1 text-[0.72rem] text-[var(--sl-text-dim)]">
            {grounding.matched_source_concepts}/{grounding.total_source_concepts} source concepts matched
          </p>
          {grounding.matched_source_ids.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {grounding.matched_source_ids.map((source) => (
                <SourceChip key={source} sourceId={source} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
