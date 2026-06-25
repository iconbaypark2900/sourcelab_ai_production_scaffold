"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import BatchProgressPanel from "@/components/BatchProgressPanel";
import BatchRunForm from "@/components/BatchRunForm";
import {
  LoadingPanel,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import { STUDY_SET_TERMS } from "@/lib/library-theme";
import {
  BATCH_TEMPLATES,
  newBatchRow,
  normalizeBatchRequest,
  validateBatchForm,
  type BatchRowState,
} from "@/lib/batch-run";
import { SourceLabApiError, createBatchLessonRuns } from "@/lib/sourcelab-api";
import { useBatchPresets, type BatchPreset } from "@/lib/use-batch-presets";
import type { BatchCreateResponse } from "@/lib/types";

export default function NewBatchPage() {
  const router = useRouter();
  const { allPresets, userPresets, savePreset, deletePreset } = useBatchPresets();
  const [batchName, setBatchName] = useState("PQC migration comparison");
  const [rows, setRows] = useState<BatchRowState[]>(() =>
    BATCH_TEMPLATES.pqc_migration.rows.map((row) => newBatchRow(row)),
  );
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<SourceLabApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [result, setResult] = useState<BatchCreateResponse | null>(null);
  const [presetLabel, setPresetLabel] = useState("");

  useEffect(() => {
    if (!submitting) {
      return;
    }
    const started = Date.now();
    const timer = setInterval(() => setElapsedMs(Date.now() - started), 500);
    return () => clearInterval(timer);
  }, [submitting]);

  function applyTemplate(key: string) {
    const template = BATCH_TEMPLATES[key];
    if (!template) {
      return;
    }
    setBatchName(template.label);
    setRows(template.rows.map((row) => newBatchRow(row)));
  }

  function applyPreset(preset: BatchPreset) {
    setBatchName(preset.batchName);
    setRows(preset.rows.map((row) => newBatchRow(row)));
  }

  function handleSavePreset() {
    const label = presetLabel.trim() || batchName.trim();
    if (!label) {
      return;
    }
    savePreset(label, batchName, rows);
    setPresetLabel("");
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setValidationError(null);
    setSubmitError(null);
    setResult(null);
    setElapsedMs(0);

    const validation = validateBatchForm(batchName, rows);
    if (!validation.ok) {
      setValidationError(
        validation.batchNameError ??
          Object.values(validation.rowErrors ?? {})[0] ??
          "Fix the form.",
      );
      return;
    }

    setSubmitting(true);
    try {
      const response = await createBatchLessonRuns(normalizeBatchRequest(batchName, rows));
      setResult(response);
      router.push(`/batches/${response.batch_id}`);
    } catch (cause) {
      setSubmitError(
        cause instanceof SourceLabApiError
          ? cause
          : new SourceLabApiError({
              message: "Batch creation failed.",
              status: 500,
              detail: cause instanceof Error ? cause.message : String(cause),
            }),
      );
      setSubmitting(false);
    }
  }

  if (submitting) {
    return (
      <PageShell>
        <PageHeader
          title={STUDY_SET_TERMS.newBatch}
          subtitle="Synchronous local study set pipeline — one blocking POST /lessons/batch"
        />
        <BatchProgressPanel
          batchName={batchName}
          rows={rows}
          elapsedMs={elapsedMs}
          complete={Boolean(result)}
          result={result}
        />
        {!result && <LoadingPanel label="Waiting for batch response…" />}
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title={STUDY_SET_TERMS.newBatch}
        subtitle="Generate multiple source-grounded sessions and compare them — same synchronous pipeline as sourcelab batch create."
      >
        <Link href="/batches" className="sl-btn">
          All study sets
        </Link>
      </PageHeader>

      <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Panel title="Study set configuration" glow="cyan">
          <BatchRunForm
            batchName={batchName}
            rows={rows}
            disabled={submitting}
            onBatchNameChange={setBatchName}
            onRowsChange={setRows}
            onApplyTemplate={applyTemplate}
          />

          <div className="mt-4 rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.35)] p-3">
            <div className="mb-2 text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
              Presets (browser-local only)
            </div>
            <div className="flex flex-wrap gap-2">
              {allPresets.map((preset) => (
                <div key={preset.id} className="flex items-center gap-1">
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => applyPreset(preset)}
                    className="sl-btn text-xs"
                  >
                    {preset.label}
                  </button>
                  {!preset.builtIn && (
                    <button
                      type="button"
                      className="text-xs text-[var(--sl-rose)]"
                      onClick={() => deletePreset(preset.id)}
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <input
                type="text"
                value={presetLabel}
                onChange={(event) => setPresetLabel(event.target.value)}
                placeholder="Preset label (defaults to study set name)"
                className="min-w-[180px] flex-1 rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-2 py-1.5 text-xs"
              />
              <button type="button" className="sl-btn text-xs" onClick={handleSavePreset}>
                Save preset
              </button>
            </div>
            {userPresets.length > 0 && (
              <p className="mt-2 text-[0.65rem] text-[var(--sl-text-faint)]">
                Saved presets live in localStorage ({userPresets.length} custom).
              </p>
            )}
          </div>

          {validationError && (
            <div className="mt-3 rounded-xl border border-[rgba(251,191,36,0.35)] bg-[rgba(251,191,36,0.08)] px-3 py-2 text-sm text-[var(--sl-amber)]">
              {validationError}
            </div>
          )}

          {submitError && (
            <div className="mt-3 rounded-xl border border-[rgba(248,113,113,0.35)] bg-[rgba(248,113,113,0.08)] px-3 py-2 text-sm">
              <div className="font-medium text-[var(--sl-rose)]">{submitError.message}</div>
              {submitError.detail && (
                <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{submitError.detail}</p>
              )}
            </div>
          )}

          <button type="submit" className="sl-btn sl-btn--primary mt-4 w-full justify-center">
            {STUDY_SET_TERMS.startBatch}
          </button>
        </Panel>

        <div className="space-y-4">
          <BatchProgressPanel batchName={batchName} rows={rows} elapsedMs={0} />

          <Panel title="What happens">
            <ol className="list-decimal space-y-2 pl-4 text-sm text-[var(--sl-text-dim)]">
              <li>Each row runs the full lesson pipeline synchronously in one HTTP request.</li>
              <li>Runs are written under artifacts/runs/.</li>
              <li>A study set manifest and comparison report are written under artifacts/batches/.</li>
              <li>Comparison requires at least two successful runs.</li>
            </ol>
            {result && (
              <div className="mt-4 space-y-2">
                <StatusPill tone="pass" label={`Study set ${result.batch_id}`} />
                <Link href={`/batches/${result.batch_id}`} className="sl-btn sl-btn--primary w-full justify-center">
                  Open study set
                </Link>
              </div>
            )}
          </Panel>
        </div>
      </form>
    </PageShell>
  );
}
