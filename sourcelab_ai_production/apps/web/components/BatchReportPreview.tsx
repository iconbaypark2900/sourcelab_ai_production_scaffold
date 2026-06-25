"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ConnectionCard, Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  batchReportDownloadUrl,
  batchReportExportFilename,
  copyTextPayload,
} from "@/lib/batch-run";
import { renderSimpleMarkdown } from "@/lib/simple-markdown";
import { getBatchReport, SourceLabApiError } from "@/lib/sourcelab-api";
import type { BatchReportResponse } from "@/lib/types";

interface BatchReportPreviewProps {
  batchId: string;
  hasComparison?: boolean;
  refreshToken?: number;
  onReportLoaded?: (markdown: string | null) => void;
}

type ReportStatus = "loading" | "available" | "empty" | "unavailable" | "error";

function deriveReportStatus(
  report: BatchReportResponse | null,
  hasComparison: boolean | undefined,
  error: SourceLabApiError | null,
  loading: boolean,
): ReportStatus {
  if (loading && !report) {
    return "loading";
  }
  if (error && !report) {
    return "error";
  }
  if (report?.comparison_report_md?.trim()) {
    return "available";
  }
  if (hasComparison === false) {
    return "unavailable";
  }
  return "empty";
}

export default function BatchReportPreview({
  batchId,
  hasComparison = true,
  refreshToken = 0,
  onReportLoaded,
}: BatchReportPreviewProps) {
  const [report, setReport] = useState<BatchReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<SourceLabApiError | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const reportRef = useRef<BatchReportResponse | null>(null);
  reportRef.current = report;

  const loadReport = useCallback(
    async (options?: { keepCache?: boolean }) => {
      const keepCache = options?.keepCache ?? true;
      setError(null);
      if (!reportRef.current) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }
      try {
        const result = await getBatchReport(batchId);
        setReport(result);
        setLastUpdated(new Date());
        onReportLoaded?.(result.comparison_report_md?.trim() ?? null);
      } catch (cause) {
        setError(
          cause instanceof SourceLabApiError
            ? cause
            : new SourceLabApiError({
                message: "Report load failed.",
                status: 500,
                detail: cause instanceof Error ? cause.message : String(cause),
              }),
        );
        if (!keepCache) {
          setReport(null);
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [batchId, onReportLoaded],
  );

  useEffect(() => {
    void loadReport({ keepCache: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchId, refreshToken]);

  const status = deriveReportStatus(report, hasComparison, error, loading);
  const markdown = report?.comparison_report_md?.trim() ?? "";

  async function handleCopyMarkdown() {
    if (!markdown) {
      return;
    }
    const copied = await copyTextPayload(markdown);
    setCopyMessage(copied ? "Report markdown copied." : "Could not copy — select from raw view.");
    window.setTimeout(() => setCopyMessage(null), 2500);
  }

  const statusTone =
    status === "available"
      ? "pass"
      : status === "loading" || status === "empty"
        ? "review"
        : status === "unavailable"
          ? "neutral"
          : "blocked";

  const statusLabel =
    status === "loading"
      ? "Loading"
      : status === "available"
        ? "Report available"
        : status === "empty"
          ? "Report empty"
          : status === "unavailable"
            ? "Not generated"
            : "Load failed";

  return (
    <Panel title="Batch report preview" glow="violet" id="batch-report-preview">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <StatusPill tone={statusTone} label={statusLabel} dot={false} />
        {lastUpdated && (
          <span className="text-xs text-[var(--sl-text-faint)]">
            Loaded {lastUpdated.toLocaleTimeString()}
            {refreshing ? " · refreshing…" : ""}
          </span>
        )}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="sl-btn text-xs"
          disabled={!markdown}
          onClick={() => void handleCopyMarkdown()}
        >
          Copy report markdown
        </button>
        <a
          href={batchReportDownloadUrl(batchId)}
          className={`sl-btn text-xs ${markdown ? "" : "pointer-events-none opacity-50"}`}
          download={batchReportExportFilename(batchId)}
        >
          Download report markdown
        </a>
        <button
          type="button"
          className="sl-btn text-xs"
          disabled={loading && !report}
          onClick={() => void loadReport({ keepCache: true })}
        >
          {refreshing ? "Refreshing…" : "Refresh report"}
        </button>
        {markdown && (
          <button
            type="button"
            className={`sl-btn text-xs ${showRaw ? "sl-btn--primary" : ""}`}
            onClick={() => setShowRaw((value) => !value)}
          >
            {showRaw ? "Rendered preview" : "Raw markdown"}
          </button>
        )}
      </div>

      {copyMessage && <p className="mb-2 text-xs text-[var(--sl-text-faint)]">{copyMessage}</p>}

      {loading && !report && (
        <p className="text-sm text-[var(--sl-text-dim)]">Loading comparison report…</p>
      )}

      {error && (
        <div className="mb-3">
          <ConnectionCard error={error} onRetry={() => void loadReport({ keepCache: true })} />
        </div>
      )}

      {!loading && !error && status === "unavailable" && (
        <p className="text-sm text-[var(--sl-text-dim)]">
          Comparison report is not available yet — at least two completed runs are required.
        </p>
      )}

      {!loading && !error && status === "empty" && (
        <p className="text-sm text-[var(--sl-text-dim)]">
          Report endpoint returned no markdown content for this batch.
        </p>
      )}

      {markdown && !showRaw && (
        <div className="max-h-[28rem] overflow-y-auto rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] p-4">
          <div className="sl-prose">{renderSimpleMarkdown(markdown)}</div>
        </div>
      )}

      {markdown && showRaw && (
        <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.55)] p-3 text-xs leading-relaxed text-[var(--sl-text-dim)]">
          {markdown}
        </pre>
      )}
    </Panel>
  );
}
