"use client";

import { LESSON_FORMAT_OPTIONS, RETRIEVAL_MODE_OPTIONS } from "@/lib/create-run";
import {
  BATCH_FIELD_CLASS,
  BATCH_TEMPLATES,
  newBatchRow,
  type BatchRowState,
} from "@/lib/batch-run";

interface BatchRunFormProps {
  batchName: string;
  rows: BatchRowState[];
  disabled?: boolean;
  onBatchNameChange: (value: string) => void;
  onRowsChange: (rows: BatchRowState[]) => void;
  onApplyTemplate: (key: string) => void;
}

export default function BatchRunForm({
  batchName,
  rows,
  disabled = false,
  onBatchNameChange,
  onRowsChange,
  onApplyTemplate,
}: BatchRunFormProps) {
  function updateRow(id: string, patch: Partial<BatchRowState>) {
    onRowsChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }

  function removeRow(id: string) {
    if (rows.length <= 1) {
      return;
    }
    onRowsChange(rows.filter((row) => row.id !== id));
  }

  function addRow() {
    onRowsChange([...rows, newBatchRow()]);
  }

  return (
    <div className="space-y-4">
      <label className="block">
        <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
          Batch name
        </span>
        <input
          type="text"
          value={batchName}
          disabled={disabled}
          onChange={(event) => onBatchNameChange(event.target.value)}
          placeholder="e.g. PQC migration comparison"
          className={`${BATCH_FIELD_CLASS} mt-1`}
        />
      </label>

      <div>
        <div className="mb-2 text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
          Templates
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(BATCH_TEMPLATES).map(([key, template]) => (
            <button
              key={key}
              type="button"
              disabled={disabled}
              onClick={() => onApplyTemplate(key)}
              className="sl-btn text-xs"
              title={template.description}
            >
              {template.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {rows.map((row, index) => (
          <div
            key={row.id}
            className="rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.35)] p-3"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-[var(--sl-text-dim)]">Run {index + 1}</span>
              <button
                type="button"
                disabled={disabled || rows.length <= 1}
                onClick={() => removeRow(row.id)}
                className="text-xs text-[var(--sl-rose)] disabled:opacity-40"
              >
                Remove
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
                  Topic
                </span>
                <input
                  type="text"
                  value={row.topic}
                  disabled={disabled}
                  onChange={(event) => updateRow(row.id, { topic: event.target.value })}
                  className={`${BATCH_FIELD_CLASS} mt-1`}
                />
              </label>
              <label className="block">
                <span className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
                  Source pack
                </span>
                <input
                  type="text"
                  value={row.sourcePack}
                  disabled={disabled}
                  onChange={(event) => updateRow(row.id, { sourcePack: event.target.value })}
                  className={`${BATCH_FIELD_CLASS} mt-1`}
                />
              </label>
              <label className="block">
                <span className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
                  Difficulty
                </span>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={row.difficulty}
                  disabled={disabled}
                  onChange={(event) =>
                    updateRow(row.id, { difficulty: Number(event.target.value) })
                  }
                  className={`${BATCH_FIELD_CLASS} mt-1`}
                />
              </label>
              <label className="block">
                <span className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
                  Lesson format
                </span>
                <select
                  value={row.lessonFormat}
                  disabled={disabled}
                  onChange={(event) =>
                    updateRow(row.id, {
                      lessonFormat: event.target.value as BatchRowState["lessonFormat"],
                    })
                  }
                  className={`${BATCH_FIELD_CLASS} mt-1`}
                >
                  {LESSON_FORMAT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
                  Retrieval mode
                </span>
                <select
                  value={row.retrievalMode}
                  disabled={disabled}
                  onChange={(event) =>
                    updateRow(row.id, {
                      retrievalMode: event.target.value as BatchRowState["retrievalMode"],
                    })
                  }
                  className={`${BATCH_FIELD_CLASS} mt-1`}
                >
                  {RETRIEVAL_MODE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        ))}
      </div>

      <button type="button" disabled={disabled} onClick={addRow} className="sl-btn w-full justify-center">
        Add run row
      </button>
    </div>
  );
}
