"use client";

import { useCallback, useState } from "react";

import { buildAttemptDeepLink } from "@/lib/attempt-url";

interface CopyAttemptLinkButtonProps {
  runId: string;
  attemptId: string;
}

export default function CopyAttemptLinkButton({ runId, attemptId }: CopyAttemptLinkButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    const link = buildAttemptDeepLink(runId, attemptId);
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copy attempt link:", link);
    }
  }, [runId, attemptId]);

  return (
    <button
      type="button"
      className="sl-btn px-2 py-0.5 text-[0.68rem]"
      onClick={() => void handleCopy()}
      title="Copy shareable link to this attempt"
    >
      {copied ? "Link copied" : "Copy attempt link"}
    </button>
  );
}
