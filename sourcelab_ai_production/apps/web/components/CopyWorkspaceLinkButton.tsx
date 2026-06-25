"use client";

import { useCallback, useState } from "react";

import { buildWorkspaceDeepLink, type AttemptsTab, type ComparePreset } from "@/lib/attempt-url";
import type { HistoryFilter } from "@/lib/attempt-summary";

interface CopyWorkspaceLinkButtonProps {
  runId: string;
  attemptId?: string | null;
  fromAttemptId?: string | null;
  toAttemptId?: string | null;
  tab?: AttemptsTab;
  filter?: HistoryFilter;
  query?: string;
  preset?: ComparePreset | null;
}

export default function CopyWorkspaceLinkButton({
  runId,
  attemptId,
  fromAttemptId,
  toAttemptId,
  tab,
  filter,
  query,
  preset,
}: CopyWorkspaceLinkButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    const link = buildWorkspaceDeepLink(runId, {
      attemptId: attemptId ?? null,
      fromAttemptId: fromAttemptId ?? null,
      toAttemptId: toAttemptId ?? null,
      tab: tab ?? null,
      filter: filter ?? null,
      query: query ?? null,
      preset: preset ?? null,
    });
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copy workspace link:", link);
    }
  }, [runId, attemptId, fromAttemptId, toAttemptId, tab, filter, query, preset]);

  return (
    <button
      type="button"
      className="sl-btn px-2 py-0.5 text-[0.68rem]"
      onClick={() => void handleCopy()}
      title="Copy link with attempt, compare, tab, filter, search, and preset state"
    >
      {copied ? "Link copied" : "Copy workspace link"}
    </button>
  );
}
