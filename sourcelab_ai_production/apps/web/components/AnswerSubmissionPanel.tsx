"use client";

import { useState } from "react";

import { submitAnswer, SourceLabApiError } from "@/lib/sourcelab-api";
import type { AnswerSubmitResponse } from "@/lib/types";
import { formatScore } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

interface AnswerSubmissionPanelProps {
  runId: string;
  topic?: string;
  /** Called after a successful submit so the page can refresh the run context. */
  onSubmitted?: () => void;
}

type SubmitStatus = "idle" | "submitting" | "success" | "error";

/**
 * Short, inline sample answers (the run pipeline is deterministic, so these
 * reliably exercise the strong / weak / unsupported scoring paths). Kept inline
 * rather than reading example files, since the browser never reads local files.
 */
const SAMPLES: Array<{ key: string; label: string; tone: string; text: string }> = [
  {
    key: "strong",
    label: "Strong",
    tone: "text-[var(--sl-emerald)]",
    text:
      "A safe post-quantum migration starts with a full cryptographic inventory: catalog every place public-key crypto is used (TLS, VPNs, code signing, CAs). " +
      "Separate immediate operational risk from long-term confidentiality risk, since 'harvest now, decrypt later' threatens data with a long secrecy lifetime. " +
      "Following NIST guidance, prioritize CRYSTALS-Kyber for key encapsulation and CRYSTALS-Dilithium for signatures, and roll out in phases (inventory, assess, pilot, deploy). " +
      "I am uncertain about the exact timeline for cryptographically relevant quantum computers, so I avoid claiming RSA-2048 can be broken today.",
  },
  {
    key: "weak",
    label: "Weak",
    tone: "text-[var(--sl-amber)]",
    text:
      "We should switch to quantum-safe encryption soon. It is more secure and will protect our data from hackers. " +
      "The team can update the algorithms when there is time.",
  },
  {
    key: "unsupported",
    label: "Unsupported",
    tone: "text-[var(--sl-rose)]",
    text:
      "Quantum computers can already break RSA-2048 today, so all encryption is useless right now. " +
      "Everyone must switch to unbreakable quantum encryption immediately or all data will be stolen this week.",
  },
];

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--sl-border)] py-1.5 last:border-0">
      <span className="text-[0.72rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {label}
      </span>
      <span className="font-mono text-xs text-[var(--sl-text)]">{value}</span>
    </div>
  );
}

export default function AnswerSubmissionPanel({
  runId,
  topic,
  onSubmitted,
}: AnswerSubmissionPanelProps) {
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<SubmitStatus>("idle");
  const [result, setResult] = useState<AnswerSubmitResponse | null>(null);
  const [error, setError] = useState<SourceLabApiError | null>(null);

  const trimmed = answer.trim();
  const canSubmit = trimmed.length > 0 && status !== "submitting";

  async function handleSubmit() {
    if (!canSubmit) {
      return;
    }
    setStatus("submitting");
    setError(null);
    try {
      const response = await submitAnswer(runId, answer);
      setResult(response);
      setStatus("success");
      onSubmitted?.();
    } catch (err: unknown) {
      setError(
        err instanceof SourceLabApiError
          ? err
          : new SourceLabApiError({
              message: err instanceof Error ? err.message : "Submission failed",
              status: -1,
            }),
      );
      setStatus("error");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[0.66rem] uppercase tracking-[0.12em] text-[var(--sl-text-faint)]">
          Load sample
        </span>
        {SAMPLES.map((sample) => (
          <button
            key={sample.key}
            type="button"
            className="sl-btn px-2.5 py-1 text-xs"
            disabled={status === "submitting"}
            onClick={() => {
              setAnswer(sample.text);
              setStatus("idle");
              setError(null);
            }}
          >
            <span className={sample.tone}>{sample.label}</span>
          </button>
        ))}
      </div>

      <textarea
        value={answer}
        onChange={(event) => setAnswer(event.target.value)}
        rows={7}
        placeholder={
          topic
            ? `Write a learner answer for "${topic}" and submit it for source-grounded scoring…`
            : "Write a learner answer and submit it for source-grounded scoring…"
        }
        className="w-full resize-y rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-3 py-2.5 text-sm text-[var(--sl-text)] placeholder:text-[var(--sl-text-faint)] focus:border-[rgba(34,211,238,0.5)] focus:outline-none"
        aria-label="Learner answer"
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[0.72rem] text-[var(--sl-text-faint)]">
          {trimmed.length > 0 ? `${trimmed.length} chars` : "Answer is empty"}
        </span>
        <div className="flex items-center gap-2">
          {answer.length > 0 && (
            <button
              type="button"
              className="sl-btn px-3 py-1.5 text-xs"
              disabled={status === "submitting"}
              onClick={() => {
                setAnswer("");
                setStatus("idle");
                setError(null);
              }}
            >
              Clear
            </button>
          )}
          <button
            type="button"
            className="sl-btn sl-btn--primary px-4 py-1.5 text-xs"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {status === "submitting" ? (
              <>
                <span className="sl-pill__dot" aria-hidden /> Scoring…
              </>
            ) : (
              "Submit answer"
            )}
          </button>
        </div>
      </div>

      {status === "error" && error && (
        <div className="rounded-lg border border-[rgba(244,63,94,0.32)] bg-[rgba(244,63,94,0.08)] p-3">
          <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-rose)]">
            {error.isConnectionError ? "API offline" : `Submission failed (${error.status})`}
          </div>
          <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{error.message}</p>
          {error.detail && (
            <p className="mt-1 text-[0.7rem] text-[var(--sl-text-faint)]">{error.detail}</p>
          )}
        </div>
      )}

      {status === "success" && result && (
        <div className="space-y-3 rounded-xl border border-[rgba(34,211,238,0.28)] bg-[rgba(9,14,28,0.55)] p-3.5">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-3xl font-semibold sl-gradient-text">
                {formatScore(result.overall_score)}
              </div>
              <div className="text-[0.72rem] text-[var(--sl-text-dim)]">final score · scored</div>
            </div>
            {result.needs_review === true ? (
              <StatusPill tone="review" label="HUMAN REVIEW" />
            ) : result.needs_review === false ? (
              <StatusPill tone="pass" label="REVIEW CLEAR" />
            ) : null}
          </div>

          <div className="space-y-0">
            <MetricRow label="Rubric alignment" value={formatScore(result.rubric_alignment_score)} />
            <MetricRow label="Uncapped score" value={formatScore(result.uncapped_score)} />
            <MetricRow
              label="Source grounding (rubric)"
              value={formatScore(result.source_grounding_score)}
            />
            <MetricRow
              label="Concept-overlap grounding"
              value={formatScore(result.concept_overlap_grounding_score)}
            />
          </div>

          {result.cap_reason && (
            <div className="rounded-lg border border-[rgba(251,191,36,0.32)] bg-[rgba(251,191,36,0.08)] p-2.5">
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-amber)]">
                Score capped
              </div>
              <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{result.cap_reason}</p>
            </div>
          )}

          {result.needs_review && result.human_review_reason && (
            <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.5)] p-2.5">
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                Human review reason
              </div>
              <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{result.human_review_reason}</p>
            </div>
          )}

          {result.next_task_focus && (
            <div className="rounded-lg border border-[rgba(168,85,247,0.28)] bg-[rgba(168,85,247,0.07)] p-2.5">
              <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-violet)]">
                Next task focus
              </div>
              <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{result.next_task_focus}</p>
            </div>
          )}

          <p className="text-[0.7rem] text-[var(--sl-text-faint)]">
            Scored against run <span className="font-mono">{result.run_id}</span>. The timeline,
            learning update, and artifact matrix refresh automatically.
          </p>
        </div>
      )}
    </div>
  );
}
