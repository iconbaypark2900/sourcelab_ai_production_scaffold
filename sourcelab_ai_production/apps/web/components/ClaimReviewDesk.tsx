"use client";

import ClaimValidationPanel from "@/components/ClaimValidationPanel";
import { EmptyState } from "@/components/Chrome";
import { LIBRARY_EMPTY_STATES } from "@/lib/library-theme";
import type { ResearchValidationInput } from "@/lib/research-validation";

interface ClaimReviewDeskProps {
  input: ResearchValidationInput;
}

/** Educational reframe of claim validation — wraps the v2.6 research panel. */
export default function ClaimReviewDesk({ input }: ClaimReviewDeskProps) {
  const hasClaims =
    (input.atomicClaims?.length ?? 0) > 0 || (input.claimMap?.length ?? 0) > 0;

  if (!hasClaims) {
    return (
      <EmptyState
        title={LIBRARY_EMPTY_STATES.noClaims.title}
        message={LIBRARY_EMPTY_STATES.noClaims.message}
      />
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--sl-text-dim)]">
        Review each atomic claim against retrieved evidence. Supported claims are ready for study;
        flagged claims need source review before you cite them in your journal.
      </p>
      <ClaimValidationPanel input={input} />
    </div>
  );
}
