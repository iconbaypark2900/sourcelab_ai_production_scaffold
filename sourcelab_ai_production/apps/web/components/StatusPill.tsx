import type { ReactNode } from "react";

export type PillTone = "pass" | "review" | "blocked" | "missing" | "info" | "neutral";

const TONE_CLASS: Record<PillTone, string> = {
  pass: "sl-pill--pass",
  review: "sl-pill--review",
  blocked: "sl-pill--blocked",
  missing: "sl-pill--missing",
  info: "sl-pill--info",
  neutral: "sl-pill--neutral",
};

const PASS_WORDS = new Set([
  "PASS",
  "PASSED",
  "OK",
  "READY",
  "INSTALLED",
  "RESOLVED",
  "SUPPORTED",
  "COMPLETE",
  "TRUE",
  "GA",
  "ACTIVE",
  "APPROVED",
  "VALID",
]);
const BLOCK_WORDS = new Set([
  "FAIL",
  "FAILED",
  "BLOCKED",
  "ERROR",
  "REJECTED",
  "UNSUPPORTED",
  "FALSE",
  "INVALID",
]);
const REVIEW_WORDS = new Set([
  "REVIEW",
  "NEEDS_REVIEW",
  "WARN",
  "WARNING",
  "PENDING",
  "PENDING_REVIEW",
  "UNCERTAIN",
  "PARTIAL",
  "DEMO_MODE",
]);
const MISSING_WORDS = new Set([
  "MISSING",
  "NONE",
  "NO_RUNS",
  "NOT_INSTALLED",
  "UNKNOWN",
  "N/A",
]);

/** Map an arbitrary backend status string to a pill tone. */
export function statusTone(status: string | boolean | null | undefined): PillTone {
  if (status === true) {
    return "pass";
  }
  if (status === false) {
    return "blocked";
  }
  if (status === null || status === undefined || status === "") {
    return "missing";
  }
  const key = String(status).trim().toUpperCase().replace(/\s+/g, "_");
  if (PASS_WORDS.has(key)) {
    return "pass";
  }
  if (BLOCK_WORDS.has(key)) {
    return "blocked";
  }
  if (REVIEW_WORDS.has(key)) {
    return "review";
  }
  if (MISSING_WORDS.has(key)) {
    return "missing";
  }
  return "neutral";
}

interface StatusPillProps {
  status?: string | boolean | null;
  label?: ReactNode;
  tone?: PillTone;
  dot?: boolean;
  title?: string;
}

export default function StatusPill({ status, label, tone, dot = true, title }: StatusPillProps) {
  const resolvedTone = tone ?? statusTone(status ?? null);
  const text =
    label ??
    (status === true
      ? "PASS"
      : status === false
        ? "FAIL"
        : status === null || status === undefined || status === ""
          ? "—"
          : String(status));

  return (
    <span className={`sl-pill ${TONE_CLASS[resolvedTone]}`} title={title}>
      {dot && <span className="sl-pill__dot" aria-hidden />}
      {text}
    </span>
  );
}
