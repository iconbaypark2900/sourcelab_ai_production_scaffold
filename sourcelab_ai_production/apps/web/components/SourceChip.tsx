import type { TrustTier } from "@/lib/types";

const TIER_CLASS: Record<string, string> = {
  A: "sl-tier--A",
  B: "sl-tier--B",
  C: "sl-tier--C",
  D: "sl-tier--D",
  E: "sl-tier--E",
};

const TIER_LABEL: Record<string, string> = {
  A: "Trust tier A — highest",
  B: "Trust tier B",
  C: "Trust tier C",
  D: "Trust tier D",
  E: "Trust tier E — lowest",
};

interface SourceChipProps {
  sourceId: string;
  trustTier?: TrustTier | string | null;
  title?: string;
}

/** A source identifier rendered as a trust-tiered chip. */
export default function SourceChip({ sourceId, trustTier, title }: SourceChipProps) {
  const tier = (trustTier ?? "").toString().toUpperCase();
  const tierClass = TIER_CLASS[tier] ?? "sl-tier--unknown";
  const tierLabel = TIER_LABEL[tier] ?? "Trust tier unknown";

  return (
    <span className="sl-chip" title={title ?? sourceId}>
      <span className={`sl-tier ${tierClass}`} title={tierLabel} aria-label={tierLabel}>
        {tier || "?"}
      </span>
      <span className="truncate">{sourceId}</span>
    </span>
  );
}
