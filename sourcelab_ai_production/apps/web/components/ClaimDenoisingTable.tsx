"use client";

import { useMemo, useState } from "react";

import type { ClaimRecord, EvidenceMatch } from "@/lib/types";
import { clamp, humanize, truncate } from "@/lib/format";
import StatusPill, { statusTone, type PillTone } from "@/components/StatusPill";
import SourceChip from "@/components/SourceChip";

interface ClaimDenoisingTableProps {
  claims: ClaimRecord[];
  evidenceMatches?: EvidenceMatch[];
}

type SupportFilter = "all" | "supported" | "unsupported";

const SEVERITY_TONE: Record<string, PillTone> = {
  high: "blocked",
  medium: "review",
  low: "neutral",
};

function reasonFor(support: string): string {
  switch (support.toLowerCase()) {
    case "supported":
      return "Locked to cited source chunk";
    case "unsupported":
      return "No approved source chunk matched";
    case "uncertain":
      return "Ambiguous — weak evidence overlap";
    case "conflicting":
      return "Conflicts with approved sources";
    default:
      return humanize(support);
  }
}

export default function ClaimDenoisingTable({ claims, evidenceMatches = [] }: ClaimDenoisingTableProps) {
  const [filter, setFilter] = useState<SupportFilter>("all");

  // Confidence proxy: strongest evidence overlap recorded for a cited chunk.
  const chunkConfidence = useMemo(() => {
    const map = new Map<string, number>();
    for (const match of evidenceMatches) {
      const current = map.get(match.chunk_id) ?? 0;
      if (match.overlap_score > current) {
        map.set(match.chunk_id, match.overlap_score);
      }
    }
    return map;
  }, [evidenceMatches]);

  const filtered = useMemo(() => {
    if (filter === "all") {
      return claims;
    }
    return claims.filter((claim) => {
      const supported = claim.support_status.toLowerCase() === "supported";
      return filter === "supported" ? supported : !supported;
    });
  }, [claims, filter]);

  if (!claims.length) {
    return <p className="text-sm text-[var(--sl-text-faint)]">No claim map recorded for this run.</p>;
  }

  const supportedCount = claims.filter((c) => c.support_status.toLowerCase() === "supported").length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-[var(--sl-text-dim)]">
          {supportedCount}/{claims.length} claims locked to a source
        </span>
        <div className="ml-auto flex gap-1">
          {(["all", "supported", "unsupported"] as SupportFilter[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setFilter(option)}
              className={`rounded-md px-2.5 py-1 text-xs capitalize transition-colors ${
                filter === option
                  ? "bg-[rgba(34,211,238,0.14)] text-white"
                  : "text-[var(--sl-text-dim)] hover:text-white"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <div className="max-h-[420px] overflow-auto rounded-xl border border-[var(--sl-border)]">
        <table className="sl-table">
          <thead>
            <tr>
              <th className="w-[36%]">Claim</th>
              <th>Support</th>
              <th>Severity</th>
              <th>Confidence</th>
              <th>Source / Chunk</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((claim, index) => {
              const confidence = claim.chunk_id ? chunkConfidence.get(claim.chunk_id) ?? null : null;
              const severityTone = SEVERITY_TONE[claim.severity?.toLowerCase()] ?? "neutral";
              return (
                <tr key={`${claim.claim}-${index}`}>
                  <td className="text-[var(--sl-text)]" title={claim.claim}>
                    {truncate(claim.claim, 150)}
                  </td>
                  <td>
                    <StatusPill
                      tone={statusTone(claim.support_status)}
                      label={claim.support_status}
                    />
                  </td>
                  <td>
                    <StatusPill tone={severityTone} dot={false} label={claim.severity || "—"} />
                  </td>
                  <td className="min-w-[110px]">
                    {confidence === null ? (
                      <span className="text-[var(--sl-text-faint)]">—</span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <div className="sl-bar w-16">
                          <div
                            className={`sl-bar__fill ${confidence >= 0.6 ? "sl-bar__fill--good" : "sl-bar__fill--warn"}`}
                            style={{ width: `${clamp(confidence * 100, 4, 100)}%` }}
                          />
                        </div>
                        <span className="font-mono text-[0.7rem] text-[var(--sl-text-dim)]">
                          {confidence.toFixed(2)}
                        </span>
                      </div>
                    )}
                  </td>
                  <td>
                    {claim.source_id ? (
                      <div className="space-y-1">
                        <SourceChip sourceId={claim.source_id} trustTier={claim.trust_tier} />
                        {claim.chunk_id && (
                          <div
                            className="font-mono text-[0.66rem] text-[var(--sl-text-faint)]"
                            title={claim.chunk_id}
                          >
                            {truncate(claim.chunk_id, 28)}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-[var(--sl-text-faint)]">ungrounded</span>
                    )}
                  </td>
                  <td className="text-xs text-[var(--sl-text-dim)]">{reasonFor(claim.support_status)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
