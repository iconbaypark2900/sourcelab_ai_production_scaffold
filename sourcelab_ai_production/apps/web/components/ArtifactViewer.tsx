"use client";

import { useState } from "react";

import { getRunArtifact, SourceLabApiError } from "@/lib/sourcelab-api";
import type { RunArtifactContentResponse } from "@/lib/types";

interface ArtifactViewerProps {
  runId: string;
}

/** Forensic quick-load targets — all fetched via the read-only artifact endpoint. */
const QUICK_ARTIFACTS: string[] = [
  "answer_review.json",
  "learning_report.json",
  "source_grounding_review.json",
  "next_task_decision.json",
  "verification_report.json",
  "citation_resolution.json",
  "proof_summary.json",
  "harness_report.json",
];

export default function ArtifactViewer({ runId }: ArtifactViewerProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<RunArtifactContentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<SourceLabApiError | null>(null);

  async function load(name: string) {
    setSelected(name);
    setLoading(true);
    setError(null);
    try {
      setContent(await getRunArtifact(runId, name));
    } catch (err: unknown) {
      setContent(null);
      setError(
        err instanceof SourceLabApiError
          ? err
          : new SourceLabApiError({
              message: err instanceof Error ? err.message : "Failed to load artifact",
              status: -1,
            }),
      );
    } finally {
      setLoading(false);
    }
  }

  const body = (() => {
    if (!content) {
      return null;
    }
    if (content.content_json !== null && content.content_json !== undefined) {
      return JSON.stringify(content.content_json, null, 2);
    }
    if (content.content_text) {
      return content.content_text;
    }
    return null;
  })();

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {QUICK_ARTIFACTS.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => load(name)}
            className={`rounded-md px-2.5 py-1 font-mono text-[0.7rem] transition-colors ${
              selected === name
                ? "bg-[rgba(34,211,238,0.16)] text-white"
                : "text-[var(--sl-text-dim)] hover:text-white"
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      {!selected && (
        <p className="text-sm text-[var(--sl-text-faint)]">
          Select an artifact to load its raw content from the API.
        </p>
      )}

      {selected && (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-xs text-[var(--sl-cyan)]">{selected}</span>
            <button
              type="button"
              onClick={() => load(selected)}
              disabled={loading}
              className="sl-btn px-2.5 py-1 text-xs"
            >
              {loading ? "Loading…" : "Reload"}
            </button>
          </div>

          {error && (
            <div className="rounded-lg border border-[rgba(244,63,94,0.32)] bg-[rgba(244,63,94,0.08)] p-2.5">
              <p className="text-xs text-[var(--sl-text-dim)]">{error.message}</p>
            </div>
          )}

          {!error && !loading && content && !content.exists && (
            <p className="text-sm text-[var(--sl-text-faint)]">
              <span className="font-mono">{selected}</span> does not exist for this run yet.
            </p>
          )}

          {!error && content && content.exists && body !== null && (
            <pre className="sl-code">{body}</pre>
          )}
        </div>
      )}
    </div>
  );
}
