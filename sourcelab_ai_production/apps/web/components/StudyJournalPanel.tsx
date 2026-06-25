"use client";

import type { ReactNode } from "react";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import { buildStudyJournalSummary, LIBRARY_EMPTY_STATES } from "@/lib/library-theme";
import { formatScore } from "@/lib/format";
import type { AnswerAttemptSummary } from "@/lib/types";
import type { AttemptTimelineSummary } from "@/lib/attempt-summary";

interface StudyJournalPanelProps {
  summary: AttemptTimelineSummary;
  attempts: AnswerAttemptSummary[];
  children: ReactNode;
}

export default function StudyJournalPanel({
  summary,
  attempts,
  children,
}: StudyJournalPanelProps) {
  const journal = buildStudyJournalSummary(attempts, {
    totalAttempts: summary.totalAttempts,
    latestScore: summary.latestScore,
    bestScore: summary.bestScore,
    needsReviewCount: summary.needsReviewCount,
  });

  return (
    <div className="space-y-4">
      <Panel title="Study Journal" hint="Answer submission · history · diff" glow="violet">
        <p className="mb-3 text-sm text-[var(--sl-text-dim)]">{journal.headline}</p>
        {journal.totalAttempts > 0 ? (
          <div className="mb-4 flex flex-wrap gap-2">
            <StatusPill tone="info" label={`${journal.totalAttempts} entries`} dot={false} />
            <StatusPill
              tone="neutral"
              label={`Latest ${formatScore(journal.latestScore)}`}
              dot={false}
            />
            <StatusPill tone="pass" label={`Best ${formatScore(journal.bestScore)}`} dot={false} />
            {journal.needsReviewCount > 0 && (
              <StatusPill tone="review" label={`${journal.needsReviewCount} review`} dot={false} />
            )}
          </div>
        ) : (
          <p className="mb-4 text-xs text-[var(--sl-text-faint)]">
            {LIBRARY_EMPTY_STATES.noJournal.message}
          </p>
        )}
        {children}
      </Panel>
    </div>
  );
}
