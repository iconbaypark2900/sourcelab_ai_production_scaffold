"use client";

import { useMemo, useState } from "react";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  ANSWER_PROFILE_LABELS,
  ANSWER_SAMPLE_PRESETS,
  BATCH_FIELD_CLASS,
  applyQuickMissingPreset,
  buildBatchAnswerText,
  buildPerRunSubmitPlan,
  buildSubmitProfileSummary,
  findEmptyPerRunCustomRunIds,
  hasValidSubmitPlan,
  selectMissingAttemptRunIds,
  type AnswerProfileKey,
  type AnswerSampleKey,
} from "@/lib/batch-run";
import { formatScore } from "@/lib/format";
import { SourceLabApiError, submitAnswer } from "@/lib/sourcelab-api";
import type { AnswerCompareResponse, AnswerSubmitResponse } from "@/lib/types";

export interface BatchRunOption {
  runId: string;
  topic: string;
}

type ProfileMode = "global" | "per_run";
type RunSubmitStatus = "pending" | "submitting" | "submitted" | "skipped" | "failed";

interface RunSubmitResult {
  status: RunSubmitStatus;
  response?: AnswerSubmitResponse;
  error?: string;
}

interface BatchAnswerSubmitPanelProps {
  runs: BatchRunOption[];
  answerComparison?: AnswerCompareResponse | null;
  /** Called after all selected runs finish (success or failure). */
  onComplete?: () => void;
}

const SUBMIT_PROFILES: AnswerProfileKey[] = ["strong", "weak", "unsupported", "custom", "skip"];

export default function BatchAnswerSubmitPanel({
  runs,
  answerComparison,
  onComplete,
}: BatchAnswerSubmitPanelProps) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set(runs.map((r) => r.runId)));
  const [profileMode, setProfileMode] = useState<ProfileMode>("global");
  const [globalProfile, setGlobalProfile] = useState<AnswerProfileKey>("strong");
  const [perRunProfiles, setPerRunProfiles] = useState<Record<string, AnswerProfileKey>>(() =>
    Object.fromEntries(runs.map((run) => [run.runId, "strong" as AnswerProfileKey])),
  );
  const [perRunCustomTexts, setPerRunCustomTexts] = useState<Record<string, string>>({});
  const [customText, setCustomText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<Record<string, RunSubmitResult>>({});
  const [pendingQuickPreset, setPendingQuickPreset] = useState<AnswerSampleKey | null>(null);

  const selectedRunIds = useMemo(
    () => runs.filter((run) => selected.has(run.runId)).map((run) => run.runId),
    [runs, selected],
  );

  const submitPlan = useMemo(
    () =>
      buildPerRunSubmitPlan({
        selectedRunIds,
        mode: profileMode,
        globalProfile,
        perRunProfiles,
        customText,
        perRunCustomTexts,
      }),
    [selectedRunIds, profileMode, globalProfile, perRunProfiles, customText, perRunCustomTexts],
  );

  const profileSummary = useMemo(() => buildSubmitProfileSummary(submitPlan), [submitPlan]);
  const emptyCustomRunIds = useMemo(
    () => (profileMode === "per_run" ? findEmptyPerRunCustomRunIds(submitPlan) : []),
    [profileMode, submitPlan],
  );
  const missingAttemptRunIds = useMemo(
    () => (answerComparison ? selectMissingAttemptRunIds(answerComparison) : []),
    [answerComparison],
  );

  const globalAnswerText = useMemo(
    () => buildBatchAnswerText(globalProfile === "skip" ? "strong" : globalProfile, customText),
    [globalProfile, customText],
  );

  const canSubmit =
    hasValidSubmitPlan(submitPlan) &&
    !submitting &&
    emptyCustomRunIds.length === 0 &&
    (profileMode === "per_run" ||
      globalProfile === "skip" ||
      (globalProfile === "custom" ? customText.trim().length > 0 : globalAnswerText.length > 0));

  function toggleRun(runId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        next.add(runId);
      }
      return next;
    });
  }

  function selectAll() {
    setSelected(new Set(runs.map((r) => r.runId)));
  }

  function selectNone() {
    setSelected(new Set());
  }

  function setRunProfile(runId: string, profile: AnswerProfileKey) {
    setPerRunProfiles((prev) => ({ ...prev, [runId]: profile }));
  }

  function setRunCustomText(runId: string, text: string) {
    setPerRunCustomTexts((prev) => ({ ...prev, [runId]: text }));
  }

  function selectMissingOnly() {
    if (missingAttemptRunIds.length === 0) {
      return;
    }
    setSelected(new Set(missingAttemptRunIds));
  }

  function requestQuickMissingPreset(profile: AnswerSampleKey) {
    if (missingAttemptRunIds.length === 0) {
      return;
    }
    setPendingQuickPreset(profile);
  }

  function confirmQuickMissingPreset() {
    if (!pendingQuickPreset || missingAttemptRunIds.length === 0) {
      setPendingQuickPreset(null);
      return;
    }
    const preset = applyQuickMissingPreset(pendingQuickPreset, missingAttemptRunIds);
    setProfileMode(preset.profileMode);
    setGlobalProfile(preset.globalProfile);
    setSelected(new Set(preset.selectedRunIds));
    setPendingQuickPreset(null);
  }

  function cancelQuickMissingPreset() {
    setPendingQuickPreset(null);
  }

  async function handleSubmit() {
    if (!canSubmit) {
      return;
    }

    setSubmitting(true);
    const nextResults: Record<string, RunSubmitResult> = {};
    for (const entry of submitPlan) {
      nextResults[entry.runId] = entry.skipped
        ? { status: "skipped" }
        : { status: "pending" };
    }
    setResults(nextResults);

    for (const entry of submitPlan) {
      if (entry.skipped) {
        continue;
      }

      setResults((prev) => ({ ...prev, [entry.runId]: { status: "submitting" } }));
      try {
        const response = await submitAnswer(entry.runId, entry.answerText);
        setResults((prev) => ({
          ...prev,
          [entry.runId]: { status: "submitted", response },
        }));
      } catch (cause) {
        const message =
          cause instanceof SourceLabApiError
            ? cause.message
            : cause instanceof Error
              ? cause.message
              : "Submission failed";
        setResults((prev) => ({
          ...prev,
          [entry.runId]: { status: "failed", error: message },
        }));
      }
    }

    setSubmitting(false);
    onComplete?.();
  }

  if (runs.length === 0) {
    return null;
  }

  return (
    <Panel title="Submit sample answers across batch" glow="cyan">
      <p className="mb-3 text-sm text-[var(--sl-text-dim)]">
        Explicit local demo action — choose runs and answer profiles, then submit sequentially via
        the same scoring path as Run Studio. No auto-submit; failures are shown per run.
      </p>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button type="button" className="sl-btn text-xs" onClick={selectAll} disabled={submitting}>
          Select all
        </button>
        <button type="button" className="sl-btn text-xs" onClick={selectNone} disabled={submitting}>
          Select none
        </button>
        <button
          type="button"
          className="sl-btn text-xs"
          disabled={submitting || missingAttemptRunIds.length === 0}
          onClick={selectMissingOnly}
        >
          Submit missing only
        </button>
        <span className="text-xs text-[var(--sl-text-faint)]">
          {selected.size} of {runs.length} runs selected
        </span>
      </div>
      {answerComparison && missingAttemptRunIds.length === 0 && (
        <p className="mb-3 text-xs text-[var(--sl-text-faint)]">All runs already have attempts.</p>
      )}
      {answerComparison && missingAttemptRunIds.length > 0 && (
        <>
          <p className="mb-2 text-xs text-[var(--sl-text-dim)]">
            {missingAttemptRunIds.length} run{missingAttemptRunIds.length === 1 ? "" : "s"} without
            attempts — use Submit missing only or a quick preset below.
          </p>
          <div className="mb-3 flex flex-wrap gap-2">
            {(Object.keys(ANSWER_SAMPLE_PRESETS) as AnswerSampleKey[]).map((key) => (
              <button
                key={`quick-${key}`}
                type="button"
                className="sl-btn text-xs"
                disabled={submitting}
                onClick={() => requestQuickMissingPreset(key)}
              >
                Submit {ANSWER_SAMPLE_PRESETS[key].label.toLowerCase()} to all missing
              </button>
            ))}
          </div>
        </>
      )}

      {pendingQuickPreset && (
        <div className="mb-3 rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] px-3 py-2">
          <p className="text-sm text-[var(--sl-text-dim)]">
            Apply{" "}
            <strong>{ANSWER_SAMPLE_PRESETS[pendingQuickPreset].label}</strong> profile to{" "}
            {missingAttemptRunIds.length} missing run
            {missingAttemptRunIds.length === 1 ? "" : "s"}? You still need to click Submit to send
            answers.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              className="sl-btn sl-btn--primary text-xs"
              onClick={confirmQuickMissingPreset}
            >
              Confirm preset
            </button>
            <button type="button" className="sl-btn text-xs" onClick={cancelQuickMissingPreset}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          className={`sl-btn text-xs ${profileMode === "global" ? "sl-btn--primary" : ""}`}
          disabled={submitting}
          onClick={() => setProfileMode("global")}
        >
          Global profile
        </button>
        <button
          type="button"
          className={`sl-btn text-xs ${profileMode === "per_run" ? "sl-btn--primary" : ""}`}
          disabled={submitting}
          onClick={() => setProfileMode("per_run")}
        >
          Per-run profile
        </button>
      </div>

      {profileMode === "global" ? (
        <>
          <div className="mb-3">
            <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
              Answer profile (all selected runs)
            </span>
            <div className="mt-2 flex flex-wrap gap-2">
              {(Object.keys(ANSWER_SAMPLE_PRESETS) as AnswerSampleKey[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  className={`sl-btn text-xs ${globalProfile === key ? "sl-btn--primary" : ""}`}
                  disabled={submitting}
                  onClick={() => setGlobalProfile(key)}
                >
                  {ANSWER_SAMPLE_PRESETS[key].label}
                </button>
              ))}
              <button
                type="button"
                className={`sl-btn text-xs ${globalProfile === "custom" ? "sl-btn--primary" : ""}`}
                disabled={submitting}
                onClick={() => setGlobalProfile("custom")}
              >
                Custom text
              </button>
              <button
                type="button"
                className={`sl-btn text-xs ${globalProfile === "skip" ? "sl-btn--primary" : ""}`}
                disabled={submitting}
                onClick={() => setGlobalProfile("skip")}
              >
                Skip
              </button>
            </div>
          </div>

          {globalProfile === "custom" && (
            <textarea
              value={customText}
              onChange={(event) => setCustomText(event.target.value)}
              rows={5}
              placeholder="Enter custom answer text for all selected runs…"
              className={`${BATCH_FIELD_CLASS} mb-3`}
              disabled={submitting}
            />
          )}

          {globalProfile !== "custom" && globalProfile !== "skip" && (
            <p className="mb-3 text-xs text-[var(--sl-text-faint)]">
              Using <strong>{ANSWER_SAMPLE_PRESETS[globalProfile].label}</strong> sample (
              {globalAnswerText.length} chars).
            </p>
          )}
          {globalProfile === "skip" && (
            <p className="mb-3 text-xs text-[var(--sl-text-faint)]">
              All selected runs will be skipped — no submissions.
            </p>
          )}
        </>
      ) : (
        <div className="mb-4 max-h-64 space-y-2 overflow-y-auto rounded-xl border border-[var(--sl-border)] p-2">
          {runs.map((run) =>
            selected.has(run.runId) ? (
              <div key={run.runId} className="rounded-lg px-2 py-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    <span className="font-mono text-xs text-[var(--sl-cyan)]">{run.runId}</span>
                    <span className="ml-2 text-sm text-[var(--sl-text-dim)]">{run.topic}</span>
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {SUBMIT_PROFILES.map((profile) => (
                      <button
                        key={profile}
                        type="button"
                        className={`sl-btn text-xs ${
                          (perRunProfiles[run.runId] ?? "strong") === profile
                            ? "sl-btn--primary"
                            : ""
                        }`}
                        disabled={submitting}
                        onClick={() => setRunProfile(run.runId, profile)}
                      >
                        {ANSWER_PROFILE_LABELS[profile]}
                      </button>
                    ))}
                  </div>
                </div>
                {(perRunProfiles[run.runId] ?? "strong") === "custom" && (
                  <div className="mt-2">
                    <textarea
                      value={perRunCustomTexts[run.runId] ?? ""}
                      onChange={(event) => setRunCustomText(run.runId, event.target.value)}
                      rows={2}
                      placeholder="Custom answer text for this run…"
                      className={`${BATCH_FIELD_CLASS} text-xs`}
                      disabled={submitting}
                    />
                    {emptyCustomRunIds.includes(run.runId) && (
                      <p className="mt-1 text-xs text-[var(--sl-rose)]">
                        Custom text is required for this run.
                      </p>
                    )}
                  </div>
                )}
              </div>
            ) : null,
          )}
        </div>
      )}

      <div className="mb-3 rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.35)] px-3 py-2 text-sm text-[var(--sl-text-dim)]">
        <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
          Pre-submit summary
        </div>
        <div className="mt-1">
          {profileSummary.selectedCount} selected · {profileSummary.skippedCount} skipped ·{" "}
          {profileSummary.submitCount} expected submission
          {profileSummary.submitCount === 1 ? "" : "s"}
        </div>
        {Object.entries(profileSummary.profileCounts).length > 0 && (
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-[var(--sl-text-faint)]">
            {Object.entries(profileSummary.profileCounts).map(([profile, count]) => (
              <span key={profile}>
                {ANSWER_PROFILE_LABELS[profile as AnswerProfileKey]}: {count}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mb-4 max-h-48 space-y-1 overflow-y-auto rounded-xl border border-[var(--sl-border)] p-2">
        {runs.map((run) => (
          <label
            key={run.runId}
            className="flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-[rgba(34,211,238,0.06)]"
          >
            <input
              type="checkbox"
              checked={selected.has(run.runId)}
              disabled={submitting}
              onChange={() => toggleRun(run.runId)}
              className="mt-1"
            />
            <span>
              <span className="font-mono text-xs text-[var(--sl-cyan)]">{run.runId}</span>
              <span className="ml-2 text-sm text-[var(--sl-text-dim)]">{run.topic}</span>
            </span>
          </label>
        ))}
      </div>

      <button
        type="button"
        className="sl-btn sl-btn--primary"
        disabled={!canSubmit}
        onClick={handleSubmit}
      >
        {submitting
          ? "Submitting…"
          : `Submit to ${profileSummary.submitCount} run${profileSummary.submitCount === 1 ? "" : "s"}`}
      </button>

      {Object.keys(results).length > 0 && (
        <div className="mt-4 space-y-2">
          <div className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Per-run results
          </div>
          {runs
            .filter((run) => results[run.runId])
            .map((run) => {
              const result = results[run.runId];
              return (
                <div
                  key={run.runId}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--sl-border)] px-3 py-2"
                >
                  <span className="font-mono text-xs text-[var(--sl-cyan)]">{run.runId}</span>
                  <div className="flex flex-wrap items-center gap-2">
                    {result.status === "skipped" && (
                      <StatusPill tone="neutral" label="Skipped" dot={false} />
                    )}
                    {result.status === "submitting" && (
                      <StatusPill tone="info" label="Submitting…" dot={false} />
                    )}
                    {result.status === "submitted" && result.response && (
                      <>
                        <StatusPill tone="pass" label="Submitted" dot={false} />
                        <span className="text-xs text-[var(--sl-text-dim)]">
                          {formatScore(result.response.overall_score)}
                        </span>
                        {result.response.needs_review ? (
                          <StatusPill tone="review" label="Needs review" dot={false} />
                        ) : (
                          <StatusPill tone="pass" label="Review clear" dot={false} />
                        )}
                      </>
                    )}
                    {result.status === "failed" && (
                      <>
                        <StatusPill tone="blocked" label="Failed" dot={false} />
                        <span className="text-xs text-[var(--sl-rose)]">{result.error}</span>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
      )}
    </Panel>
  );
}
