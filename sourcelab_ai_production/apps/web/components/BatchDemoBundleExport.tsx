"use client";

import { useState } from "react";

import { Panel } from "@/components/Chrome";
import {
  downloadBatchDemoBundle,
  LOCAL_NOTES_EXCLUSION_NOTE,
} from "@/lib/batch-run";
import type {
  AnswerCompareResponse,
  BatchDetailResponse,
  RunComparisonResponse,
} from "@/lib/types";

interface BatchDemoBundleExportProps {
  batchId: string;
  batchSummary?: BatchDetailResponse | null;
  runComparison?: RunComparisonResponse | null;
  answerComparison?: AnswerCompareResponse | null;
  reportMarkdown?: string | null;
}

export default function BatchDemoBundleExport({
  batchId,
  batchSummary = null,
  runComparison = null,
  answerComparison = null,
  reportMarkdown = null,
}: BatchDemoBundleExportProps) {
  const [includeLocalNotes, setIncludeLocalNotes] = useState(false);

  function handleDownload() {
    downloadBatchDemoBundle({
      batchId,
      batchSummary,
      runComparison,
      answerComparison,
      reportMarkdown,
      includeLocalNotes,
    });
  }

  return (
    <Panel title="Demo bundle export" id="batch-demo-bundle">
      <p className="mb-3 text-sm text-[var(--sl-text-dim)]">
        Download a unified JSON bundle with batch summary, loaded comparisons, report markdown, and
        answer matrix exports. Browser-only — does not mutate proof artifacts.
      </p>

      <label className="mb-3 flex cursor-pointer items-start gap-2 text-sm text-[var(--sl-text-dim)]">
        <input
          type="checkbox"
          checked={includeLocalNotes}
          onChange={(event) => setIncludeLocalNotes(event.target.checked)}
          className="mt-1"
        />
        <span>
          Include local attempt notes
          <span className="mt-0.5 block text-xs text-[var(--sl-text-faint)]">
            Local notes are browser-only, not proof artifacts.
          </span>
        </span>
      </label>

      {!includeLocalNotes && (
        <p className="mb-3 text-xs text-[var(--sl-text-faint)]">{LOCAL_NOTES_EXCLUSION_NOTE}</p>
      )}

      <button type="button" className="sl-btn sl-btn--primary text-xs" onClick={handleDownload}>
        Download demo bundle JSON
      </button>
    </Panel>
  );
}
