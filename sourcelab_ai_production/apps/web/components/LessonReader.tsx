"use client";

import { useState } from "react";

import GeneratedLessonPanel from "@/components/GeneratedLessonPanel";
import SourceChip from "@/components/SourceChip";
import StatusPill from "@/components/StatusPill";
import type { GeneratedLessonPackage, LessonShowResponse } from "@/lib/types";

type ReaderMode = "study" | "review";

interface LessonReaderProps {
  lesson: LessonShowResponse | null;
  lessonPackage?: GeneratedLessonPackage | null;
}

export default function LessonReader({ lesson, lessonPackage }: LessonReaderProps) {
  const [mode, setMode] = useState<ReaderMode>("study");
  const [showAnswerKey, setShowAnswerKey] = useState(false);
  const [showClaims, setShowClaims] = useState(false);

  const citations = lesson?.sources ?? lessonPackage?.source_ids ?? [];
  const answerKey =
    lesson?.answer_key_markdown ??
    (typeof lessonPackage?.answer_key === "string" ? lessonPackage.answer_key : null);
  const rubric = lessonPackage?.rubric ?? null;
  const claims =
    lessonPackage?.lesson?.required_source_concepts ??
    lessonPackage?.lesson?.learning_objectives ??
    [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] p-3">
        <span className="text-[0.66rem] uppercase tracking-[0.12em] text-[var(--sl-text-faint)]">
          Reader mode
        </span>
        {(["study", "review"] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setMode(option)}
            className={`rounded-lg px-3 py-1 text-xs capitalize transition-colors ${
              mode === option
                ? "bg-[rgba(212,175,106,0.16)] text-[var(--sl-parchment)]"
                : "text-[var(--sl-text-dim)] hover:text-white"
            }`}
          >
            {option}
          </button>
        ))}
        <div className="ml-auto flex flex-wrap gap-2">
          <label className="flex items-center gap-1.5 text-xs text-[var(--sl-text-dim)]">
            <input
              type="checkbox"
              checked={showClaims}
              onChange={(event) => setShowClaims(event.target.checked)}
            />
            Key claims
          </label>
          <label className="flex items-center gap-1.5 text-xs text-[var(--sl-text-dim)]">
            <input
              type="checkbox"
              checked={showAnswerKey}
              onChange={(event) => setShowAnswerKey(event.target.checked)}
              disabled={mode === "study" && !showAnswerKey}
            />
            Answer key
          </label>
        </div>
      </div>

      {mode === "study" && !showAnswerKey && (
        <p className="text-xs text-[var(--sl-parchment-dim)]">
          Study mode hides the answer key until you enable it — practice source-grounded reasoning first.
        </p>
      )}

      {citations.length > 0 && (
        <div>
          <div className="mb-1.5 text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Citations
          </div>
          <div className="flex flex-wrap gap-1.5">
            {citations.map((source) => (
              <SourceChip key={source} sourceId={source} />
            ))}
          </div>
        </div>
      )}

      {showClaims && claims.length > 0 && (
        <div className="rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] p-3">
          <div className="mb-2 text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Key claims to verify
          </div>
          <ul className="space-y-1.5 text-xs text-[var(--sl-text-dim)]">
            {claims.map((claim, index) => (
              <li key={index} className="flex gap-2">
                <StatusPill tone="info" label={`${index + 1}`} dot={false} />
                <span>{claim}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <GeneratedLessonPanel lesson={lesson} />

      {showAnswerKey && answerKey && (
        <div className="rounded-xl border border-[rgba(212,175,106,0.35)] bg-[rgba(212,175,106,0.06)] p-3">
          <div className="mb-2 text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-parchment)]">
            Answer key
          </div>
          <p className="text-sm leading-relaxed text-[var(--sl-text)]">{answerKey}</p>
        </div>
      )}

      {showAnswerKey && rubric && (
        <details className="sl-panel overflow-hidden">
          <summary className="cursor-pointer px-4 py-3 text-sm text-[var(--sl-text-dim)]">
            Rubric criteria
          </summary>
          <pre className="sl-code mx-4 mb-4">{JSON.stringify(rubric, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
