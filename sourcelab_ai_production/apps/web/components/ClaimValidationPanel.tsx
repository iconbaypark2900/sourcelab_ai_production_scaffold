"use client";

import { useMemo, useState } from "react";

import { Panel } from "@/components/Chrome";
import StatusPill, { statusTone } from "@/components/StatusPill";
import SourceChip from "@/components/SourceChip";
import {
  groupClaimsByValidationStatus,
  type ClaimValidationGroup,
} from "@/lib/research-validation";
import type { ResearchValidationInput } from "@/lib/research-validation";
import { truncate } from "@/lib/format";

interface ClaimValidationPanelProps {
  input: ResearchValidationInput;
}

const GROUP_META: Record<
  ClaimValidationGroup,
  { title: string; tone: "pass" | "review" | "blocked" | "neutral" }
> = {
  supported: { title: "Supported", tone: "pass" },
  needs_review: { title: "Needs review", tone: "review" },
  unsupported: { title: "Unsupported", tone: "blocked" },
  conflicting: { title: "Conflicting", tone: "blocked" },
  uncited: { title: "Uncited", tone: "neutral" },
};

export default function ClaimValidationPanel({ input }: ClaimValidationPanelProps) {
  const groups = useMemo(() => groupClaimsByValidationStatus(input), [input]);
  const [activeGroup, setActiveGroup] = useState<ClaimValidationGroup>("supported");
  const total =
    groups.supported.length +
    groups.needs_review.length +
    groups.unsupported.length +
    groups.conflicting.length +
    groups.uncited.length;

  if (!total) {
    return (
      <Panel title="Claim validation" id="research-claim-validation">
        <p className="text-sm text-[var(--sl-text-faint)]">No atomic claims recorded for this run.</p>
      </Panel>
    );
  }

  const activeClaims = groups[activeGroup];

  return (
    <Panel title="Claim validation" hint="From verification + evidence artifacts" glow="violet" id="research-claim-validation">
      <div className="mb-3 flex flex-wrap gap-1">
        {(Object.keys(GROUP_META) as ClaimValidationGroup[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveGroup(key)}
            className={`rounded-lg border px-2 py-1 text-xs transition-colors ${
              activeGroup === key
                ? "border-[var(--sl-violet)] bg-[rgba(168,85,247,0.12)] text-white"
                : "border-[var(--sl-border)] text-[var(--sl-text-dim)] hover:text-white"
            }`}
          >
            {GROUP_META[key].title} ({groups[key].length})
          </button>
        ))}
      </div>

      <ul className="space-y-2">
        {activeClaims.map((claim) => (
          <li
            key={claim.claimId}
            className="rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] p-3"
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <StatusPill
                tone={statusTone(claim.supportStatus)}
                label={claim.supportStatus}
                dot={false}
              />
              <span className="sl-pill sl-pill--neutral">{claim.claimType}</span>
              <span className="sl-pill sl-pill--neutral">{claim.severity}</span>
              <span className="font-mono text-[0.68rem] text-[var(--sl-text-faint)]">
                {claim.claimId}
              </span>
            </div>
            <p className="text-sm text-[var(--sl-text)]">{truncate(claim.text, 240)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--sl-text-dim)]">
              {claim.sourceId && (
                <SourceChip sourceId={claim.sourceId} />
              )}
              {claim.chunkId && (
                <span className="font-mono text-[0.68rem]">{claim.chunkId}</span>
              )}
              <span>Evidence matches: {claim.evidenceCount}</span>
              {claim.reviewReason && (
                <span className="text-[var(--sl-amber)]">{claim.reviewReason}</span>
              )}
            </div>
          </li>
        ))}
        {!activeClaims.length && (
          <li className="text-sm text-[var(--sl-text-faint)]">
            No claims in this group.
          </li>
        )}
      </ul>
    </Panel>
  );
}
