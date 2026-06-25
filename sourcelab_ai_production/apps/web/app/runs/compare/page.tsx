"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import BatchAnswerMatrix from "@/components/BatchAnswerMatrix";
import CrossRunAnswerDiffPanel from "@/components/CrossRunAnswerDiffPanel";
import RunComparisonPanel from "@/components/RunComparisonPanel";
import {
  ConnectionCard,
  LoadingPanel,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import {
  buildComparePagePath,
  parseCompareRunIds,
  parseCompareTab,
  type CompareTab,
  validateCompareRunIds,
} from "@/lib/batch-run";
import { SourceLabApiError, compareRunAnswers, compareRuns } from "@/lib/sourcelab-api";
import type { AnswerCompareResponse, RunComparisonResponse } from "@/lib/types";

function CompareRunsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialRunIds = searchParams.get("run_ids") ?? "";
  const initialTab = parseCompareTab(searchParams.get("tab"));

  const [input, setInput] = useState(initialRunIds);
  const [activeTab, setActiveTab] = useState<CompareTab>(initialTab);
  const [comparison, setComparison] = useState<RunComparisonResponse | null>(null);
  const [answerComparison, setAnswerComparison] = useState<AnswerCompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<SourceLabApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const autoLoaded = useRef(false);

  const syncUrl = useCallback(
    (runIds: string[], tab: CompareTab) => {
      const path = buildComparePagePath({
        runIds,
        tab,
        preserve: searchParams,
      });
      router.replace(path, { scroll: false });
    },
    [router, searchParams],
  );

  const runComparison = useCallback(
    async (runIds: string[], tab: CompareTab) => {
      setError(null);
      setApiError(null);
      setComparison(null);
      setAnswerComparison(null);

      const validation = validateCompareRunIds(runIds);
      if (!validation.ok) {
        setError(validation.error ?? "Invalid run IDs.");
        return;
      }

      setLoading(true);
      try {
        const [runResult, answerResult] = await Promise.all([
          compareRuns(runIds),
          compareRunAnswers(runIds),
        ]);
        setComparison(runResult);
        setAnswerComparison(answerResult);
        syncUrl(runIds, tab);
      } catch (cause) {
        setApiError(
          cause instanceof SourceLabApiError
            ? cause
            : new SourceLabApiError({
                message: "Comparison failed.",
                status: 500,
                detail: cause instanceof Error ? cause.message : String(cause),
              }),
        );
      } finally {
        setLoading(false);
      }
    },
    [syncUrl],
  );

  useEffect(() => {
    if (autoLoaded.current) {
      return;
    }
    const runIds = parseCompareRunIds(initialRunIds);
    if (validateCompareRunIds(runIds).ok) {
      autoLoaded.current = true;
      void runComparison(runIds, initialTab);
    }
  }, [initialRunIds, initialTab, runComparison]);

  async function handleCompare(event: React.FormEvent) {
    event.preventDefault();
    const runIds = parseCompareRunIds(input);
    await runComparison(runIds, activeTab);
  }

  function handleTabChange(tab: CompareTab) {
    setActiveTab(tab);
    syncUrl(parseCompareRunIds(input), tab);
  }

  async function handleCopyLink() {
    const runIds = parseCompareRunIds(input);
    const path = buildComparePagePath({ runIds, tab: activeTab });
    const url =
      typeof window !== "undefined" ? `${window.location.origin}${path}` : path;
    try {
      await navigator.clipboard.writeText(url);
      setCopyMessage("Comparison link copied.");
    } catch {
      setCopyMessage("Could not copy link — copy from the address bar.");
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="Compare runs"
        subtitle="Artifact-driven comparison across two or more run IDs."
      >
        <Link href="/runs" className="sl-btn">
          Back to runs
        </Link>
      </PageHeader>

      <Panel title="Run IDs" glow="cyan">
        <form onSubmit={handleCompare} className="space-y-3">
          <label className="block">
            <span className="text-[0.66rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
              Run IDs (comma or space separated)
            </span>
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="20260621T010344Z, 20260621T010343Z"
              className="mt-1 w-full rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-3 py-2 font-mono text-sm"
            />
          </label>
          {error && <p className="text-sm text-[var(--sl-amber)]">{error}</p>}
          {apiError && (
            <div className="text-sm text-[var(--sl-rose)]">
              {apiError.message}
              {apiError.detail && (
                <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{apiError.detail}</p>
              )}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="submit" className="sl-btn sl-btn--primary" disabled={loading}>
              {loading ? "Comparing…" : "Compare"}
            </button>
            {(comparison || answerComparison) && (
              <button type="button" className="sl-btn" onClick={() => void handleCopyLink()}>
                Copy comparison link
              </button>
            )}
          </div>
          {copyMessage && <p className="text-xs text-[var(--sl-text-faint)]">{copyMessage}</p>}
        </form>
      </Panel>

      {loading && <LoadingPanel label="Loading comparison…" />}

      {(comparison || answerComparison) && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2 border-b border-[var(--sl-border)] pb-2">
            <button
              type="button"
              className={`sl-btn text-xs ${activeTab === "artifacts" ? "sl-btn--primary" : ""}`}
              onClick={() => handleTabChange("artifacts")}
            >
              Run artifacts
            </button>
            <button
              type="button"
              className={`sl-btn text-xs ${activeTab === "answers" ? "sl-btn--primary" : ""}`}
              onClick={() => handleTabChange("answers")}
            >
              Learner answers
            </button>
          </div>

          {activeTab === "artifacts" && comparison && (
            <RunComparisonPanel comparison={comparison} />
          )}

          {activeTab === "answers" && answerComparison && (
            <>
              <BatchAnswerMatrix comparison={answerComparison} />
              <CrossRunAnswerDiffPanel perRun={answerComparison.per_run} />
            </>
          )}
        </div>
      )}
    </PageShell>
  );
}

export default function CompareRunsPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading compare page…" />}>
      <CompareRunsContent />
    </Suspense>
  );
}
