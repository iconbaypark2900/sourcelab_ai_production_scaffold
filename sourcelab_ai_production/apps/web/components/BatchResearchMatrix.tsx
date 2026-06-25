"use client";

import Link from "next/link";
import { useState } from "react";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  buildBatchResearchMatrixRows,
  buildResearchMatrixExportMarkdown,
  getResearchMatrixRowLabels,
  researchMatrixExportFilename,
} from "@/lib/research-validation";
import { downloadTextFile } from "@/lib/batch-run";
import { formatScore } from "@/lib/format";
import type { RunComparisonResponse } from "@/lib/types";

interface BatchResearchMatrixProps {
  comparison: RunComparisonResponse;
  batchId?: string;
}

export default function BatchResearchMatrix({ comparison, batchId }: BatchResearchMatrixProps) {
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const rows = buildBatchResearchMatrixRows(comparison);

  function exportMarkdown() {
    const content = buildResearchMatrixExportMarkdown(comparison, batchId);
    downloadTextFile(researchMatrixExportFilename(batchId, "md"), content, "text/markdown");
  }

  function exportJson() {
    const content = JSON.stringify({ batch_id: batchId, rows }, null, 2);
    downloadTextFile(
      researchMatrixExportFilename(batchId, "json"),
      content,
      "application/json",
    );
  }

  async function copyMarkdown() {
    const content = buildResearchMatrixExportMarkdown(comparison, batchId);
    try {
      await navigator.clipboard.writeText(content);
      setCopyMessage("Matrix markdown copied.");
    } catch {
      setCopyMessage("Could not copy matrix markdown.");
    }
    window.setTimeout(() => setCopyMessage(null), 2500);
  }

  return (
    <Panel title="Batch research matrix" glow="cyan" id="research-matrix">
      <div className="mb-4 flex flex-wrap gap-2">
        <button type="button" className="sl-btn text-xs" onClick={exportJson}>
          Download JSON
        </button>
        <button type="button" className="sl-btn text-xs" onClick={exportMarkdown}>
          Download Markdown
        </button>
        <button type="button" className="sl-btn text-xs" onClick={() => void copyMarkdown()}>
          Copy Markdown
        </button>
      </div>
      {copyMessage && <p className="mb-2 text-xs text-[var(--sl-text-faint)]">{copyMessage}</p>}

      {comparison.recommendation && (
        <p className="mb-4 text-sm text-[var(--sl-text-faint)]">{comparison.recommendation}</p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--sl-border)] text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
              <th className="py-2 pr-3">Run</th>
              <th className="py-2 pr-3">Topic</th>
              <th className="py-2 pr-3 text-right">Sources</th>
              <th className="py-2 pr-3 text-right">Chunks</th>
              <th className="py-2 pr-3 text-right">Support</th>
              <th className="py-2 pr-3 text-right">Citation</th>
              <th className="py-2 pr-3 text-right">Unsupported</th>
              <th className="py-2 pr-3 text-right">Review</th>
              <th className="py-2 pr-3">Labels</th>
              <th className="py-2">Links</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const labels = getResearchMatrixRowLabels(row);
              return (
                <tr key={row.runId} className="border-b border-[var(--sl-border)]/60">
                  <td className="py-2 pr-3 font-mono text-xs text-[var(--sl-cyan)]">{row.runId}</td>
                  <td className="max-w-[180px] truncate py-2 pr-3">{row.topic}</td>
                  <td className="py-2 pr-3 text-right">{row.sourceCount}</td>
                  <td className="py-2 pr-3 text-right">{row.chunkCount}</td>
                  <td className="py-2 pr-3 text-right">{formatScore(row.supportRate)}</td>
                  <td className="py-2 pr-3 text-right">{formatScore(row.citationRate)}</td>
                  <td className="py-2 pr-3 text-right">{row.unsupportedClaims}</td>
                  <td className="py-2 pr-3 text-right">{row.needsReviewClaims}</td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap gap-1">
                      {labels.map((label) => (
                        <StatusPill
                          key={label.key}
                          tone={label.tone}
                          label={label.text}
                          dot={false}
                        />
                      ))}
                    </div>
                  </td>
                  <td className="py-2">
                    <Link href={`/runs/${row.runId}?mode=research`} className="sl-btn text-xs">
                      Research
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
