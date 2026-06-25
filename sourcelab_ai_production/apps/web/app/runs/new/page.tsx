"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  ConnectionCard,
  LoadingPanel,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  CREATE_RUN_FIELD_CLASS,
  LESSON_FORMAT_OPTIONS,
  MODEL_MODE_OPTIONS,
  RETRIEVAL_MODE_OPTIONS,
  normalizeCreateRunRequest,
  selectDefaultSourcePack,
  validateCreateRunForm,
  type CreateRunFormState,
  type PackChoice,
} from "@/lib/create-run";
import { LIBRARY_CREATION_STAGES, LIBRARY_TERMS } from "@/lib/library-theme";
import { formatScore } from "@/lib/format";
import {
  SourceLabApiError,
  STRICT_RELEASE_PACK,
  createLessonRun,
  getLatestEvals,
  getSourcePackStatus,
  getSourcePacks,
  validateSourcePack,
} from "@/lib/sourcelab-api";
import type { CreateLessonRunResponse } from "@/lib/types";
import { useApi } from "@/lib/use-api";

async function settle<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

const INITIAL_FORM: CreateRunFormState = {
  topic: "",
  sourcePack: "pqc_v1",
  difficulty: 2,
  lessonFormat: "architecture_review",
  retrievalMode: "hybrid",
  modelMode: "deterministic",
};

export default function CreateRunPage() {
  const router = useRouter();
  const [form, setForm] = useState<CreateRunFormState>(INITIAL_FORM);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<SourceLabApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [activeStage, setActiveStage] = useState(0);
  const [result, setResult] = useState<CreateLessonRunResponse | null>(null);
  const [autoNavigate, setAutoNavigate] = useState(true);

  const { data, error, loading, reload } = useApi(async () => {
    const packsRes = await getSourcePacks();
    const choices: PackChoice[] = await Promise.all(
      packsRes.packs.map(async (pack) => {
        const [status, validation, evals] = await Promise.all([
          settle(getSourcePackStatus(pack.pack_name)),
          settle(validateSourcePack(pack.pack_name)),
          settle(getLatestEvals(pack.pack_name)),
        ]);
        return {
          packName: pack.pack_name,
          installed: status?.installed ?? false,
          valid: validation?.valid ?? false,
          passRate: evals?.summary?.overall_pass_rate ?? null,
          required: pack.pack_name === STRICT_RELEASE_PACK,
        };
      }),
    );
    return { choices };
  }, []);

  useEffect(() => {
    if (!data?.choices.length) {
      return;
    }
    setForm((current) => ({
      ...current,
      sourcePack: selectDefaultSourcePack(data.choices),
    }));
  }, [data?.choices]);

  const selectedPack = useMemo(
    () => data?.choices.find((pack) => pack.packName === form.sourcePack) ?? null,
    [data?.choices, form.sourcePack],
  );

  useEffect(() => {
    if (!submitting) {
      return;
    }
    setActiveStage(0);
    const timers = LIBRARY_CREATION_STAGES.map((_, index) =>
      window.setTimeout(() => setActiveStage(index), index * 900),
    );
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [submitting]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setValidationError(null);
    setSubmitError(null);
    setResult(null);

    const validation = validateCreateRunForm(form);
    if (!validation.ok) {
      setValidationError(validation.topicError ?? validation.sourcePackError ?? "Fix the form.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await createLessonRun(normalizeCreateRunRequest(form));
      setResult(response);
      setActiveStage(LIBRARY_CREATION_STAGES.length - 1);
      if (autoNavigate && response.run_id) {
        router.push(`/runs/${response.run_id}`);
      }
    } catch (cause) {
      setSubmitError(
        cause instanceof SourceLabApiError
          ? cause
          : new SourceLabApiError({
              message: "Run creation failed.",
              status: 500,
              detail: cause instanceof Error ? cause.message : String(cause),
            }),
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <PageShell>
        <PageHeader title={LIBRARY_TERMS.startSession} subtitle="Loading collections…" />
        <LoadingPanel label="Preparing create-run form…" />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <PageHeader title={LIBRARY_TERMS.startSession} />
        <ConnectionCard error={error} onRetry={reload} />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title={LIBRARY_TERMS.startSession}
        subtitle="Generate a source-grounded lesson locally — same synchronous pipeline as sourcelab lesson create."
      >
        <Link href="/runs" className="sl-btn">
          All sessions
        </Link>
      </PageHeader>

      <p className="mb-4 text-sm text-[var(--sl-text-dim)]">
        Lessons are grounded in approved collection sources. Retrieval pulls relevant excerpts from
        the shelf; verification checks claims before the lesson reaches the Reading Room.
      </p>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Panel title="Study session configuration" glow="cyan">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <label className="block">
              <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                Topic
              </span>
              <input
                type="text"
                value={form.topic}
                disabled={submitting}
                onChange={(event) => setForm((current) => ({ ...current, topic: event.target.value }))}
                placeholder="e.g. post-quantum cryptography migration planning"
                className={`${CREATE_RUN_FIELD_CLASS} mt-1`}
              />
            </label>

            <label className="block">
              <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                {LIBRARY_TERMS.collection}
              </span>
              <select
                value={form.sourcePack}
                disabled={submitting}
                onChange={(event) =>
                  setForm((current) => ({ ...current, sourcePack: event.target.value }))
                }
                className={`${CREATE_RUN_FIELD_CLASS} mt-1`}
              >
                {(data?.choices ?? []).map((pack) => (
                  <option key={pack.packName} value={pack.packName}>
                    {pack.packName}
                    {pack.required ? " (strict-release)" : ""}
                    {!pack.valid ? " — invalid" : !pack.installed ? " — not installed" : ""}
                  </option>
                ))}
              </select>
            </label>

            {selectedPack && (
              <div className="rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] p-3 text-xs text-[var(--sl-text-dim)]">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill status={selectedPack.installed} label={selectedPack.installed ? "INSTALLED" : "NOT INSTALLED"} />
                  <StatusPill
                    tone={selectedPack.valid ? "pass" : "blocked"}
                    label={selectedPack.valid ? "VALID" : "INVALID"}
                  />
                  {selectedPack.required && <StatusPill tone="info" label="REQUIRED" dot={false} />}
                  <span>
                    Eval pass rate:{" "}
                    <span className="font-mono text-white">
                      {formatScore(selectedPack.passRate)}
                    </span>
                  </span>
                </div>
                {!selectedPack.valid && (
                  <p className="mt-2 text-[var(--sl-amber)]">
                    This collection failed validation. Choose another or repair it under Collections.
                  </p>
                )}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                  {LIBRARY_TERMS.studyDepth} (1–5)
                </span>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={form.difficulty}
                  disabled={submitting}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      difficulty: Number(event.target.value),
                    }))
                  }
                  className={`${CREATE_RUN_FIELD_CLASS} mt-1`}
                />
              </label>

              <label className="block">
                <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                  {LIBRARY_TERMS.lessonStyle}
                </span>
                <select
                  value={form.lessonFormat}
                  disabled={submitting}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      lessonFormat: event.target.value as CreateRunFormState["lessonFormat"],
                    }))
                  }
                  className={`${CREATE_RUN_FIELD_CLASS} mt-1`}
                >
                  {LESSON_FORMAT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="block">
              <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                Retrieval mode
              </span>
              <select
                value={form.retrievalMode}
                disabled={submitting}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    retrievalMode: event.target.value as CreateRunFormState["retrievalMode"],
                  }))
                }
                className={`${CREATE_RUN_FIELD_CLASS} mt-1`}
              >
                {RETRIEVAL_MODE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value} disabled={!option.supported}>
                    {option.label}
                    {!option.supported ? " (manifest only)" : ""}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[0.72rem] text-[var(--sl-text-faint)]">
                Hybrid executes the local PocketIndex search. Other modes are recorded in the run
                manifest for traceability.
              </p>
            </label>

            <label className="block">
              <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
                Model mode
              </span>
              <select
                value={form.modelMode}
                disabled={submitting}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    modelMode: event.target.value as CreateRunFormState["modelMode"],
                  }))
                }
                className={`${CREATE_RUN_FIELD_CLASS} mt-1`}
              >
                {MODEL_MODE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value} disabled={!option.supported}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex items-center gap-2 text-xs text-[var(--sl-text-dim)]">
              <input
                type="checkbox"
                checked={autoNavigate}
                disabled={submitting}
                onChange={(event) => setAutoNavigate(event.target.checked)}
              />
              Open Reading Room automatically after creation
            </label>

            {validationError && (
              <div className="rounded-xl border border-[rgba(251,191,36,0.35)] bg-[rgba(251,191,36,0.08)] px-3 py-2 text-sm text-[var(--sl-amber)]">
                {validationError}
              </div>
            )}

            {submitError && (
              <div className="rounded-xl border border-[rgba(248,113,113,0.35)] bg-[rgba(248,113,113,0.08)] px-3 py-2 text-sm text-[var(--sl-text)]">
                <div className="font-medium text-[var(--sl-rose)]">{submitError.message}</div>
                {submitError.detail && (
                  <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{submitError.detail}</p>
                )}
                {submitError.isConnectionError && (
                  <p className="mt-2 text-xs text-[var(--sl-text-dim)]">
                    Start the API with <code className="text-[var(--sl-cyan)]">sourcelab api --serve</code>.
                  </p>
                )}
              </div>
            )}

            <button
              type="submit"
              className="sl-btn sl-btn--primary w-full justify-center"
              disabled={submitting || selectedPack?.valid === false}
            >
              {submitting ? "Preparing lesson…" : "Start study session"}
            </button>
          </form>
        </Panel>

        <div className="space-y-4">
          <Panel title={submitting ? "Preparing lesson…" : result ? "Session ready" : "Library creation stages"}>
            <ol className="space-y-2">
              {LIBRARY_CREATION_STAGES.map((stage, index) => {
                const done = result ? true : submitting && index < activeStage;
                const active = submitting && index === activeStage && !result;
                return (
                  <li
                    key={stage}
                    className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
                      done
                        ? "border-[rgba(52,211,153,0.35)] bg-[rgba(52,211,153,0.08)]"
                        : active
                          ? "border-[rgba(34,211,238,0.45)] bg-[rgba(34,211,238,0.08)]"
                          : "border-[var(--sl-border)] bg-[rgba(4,7,16,0.35)]"
                    }`}
                  >
                    <span className="text-[var(--sl-text)]">{stage}</span>
                    <StatusPill
                      tone={done ? "pass" : active ? "info" : "missing"}
                      label={done ? "DONE" : active ? "RUNNING" : "WAIT"}
                      dot={false}
                    />
                  </li>
                );
              })}
            </ol>
            {submitting && (
              <p className="mt-3 text-xs text-[var(--sl-text-dim)]">
                Synchronous local pipeline — stages advance while the backend completes lesson
                creation, verification, and proof sealing. No simulated streaming.
              </p>
            )}
          </Panel>

          {result && !autoNavigate && (
            <Panel title="Success" glow="cyan">
              <div className="space-y-3">
                <div>
                  <div className="text-[0.62rem] uppercase tracking-[0.16em] text-[var(--sl-text-faint)]">
                    Run ID
                  </div>
                  <div className="font-mono text-sm text-[var(--sl-cyan)]">{result.run_id}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusPill tone={result.harness_status === "PASS" ? "pass" : "blocked"} label={`Harness ${result.harness_status}`} />
                  <StatusPill tone={result.proof_status === "PASS" ? "pass" : "review"} label={`Proof ${result.proof_status}`} />
                  <span className="sl-pill sl-pill--neutral">
                    {result.artifact_count} artifacts
                  </span>
                </div>
                <div className="flex flex-col gap-2">
                  <Link href={`/runs/${result.run_id}`} className="sl-btn sl-btn--primary justify-center">
                    Open Reading Room
                  </Link>
                  <Link
                    href={`/runs/${result.run_id}?tab=submit`}
                    className="sl-btn justify-center"
                  >
                    Submit answer
                  </Link>
                </div>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </PageShell>
  );
}
