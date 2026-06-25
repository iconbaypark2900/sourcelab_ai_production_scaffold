"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { refreshRunContext } from "@/lib/sourcelab-api";
import { useRunRefresh } from "@/lib/use-run-refresh";
import { buildAttemptQuery, parseAttemptQuery, resolveAttemptsTabFromQuery, resolveHistoryFilterFromQuery, resolveHistorySearchFromQuery, deriveComparePairFromPreset, type AttemptsTab, type ComparePreset } from "@/lib/attempt-url";
import { getVisibleHistoryAttempts } from "@/lib/attempt-filters";
import { useAnswerHistory, isEditableTarget } from "@/lib/use-answer-history";
import {
  computeAttemptTimelineSummary,
  deltaToneClass,
  formatScoreDelta,
  getAdjacentFilteredAttemptId,
  type HistoryFilter,
} from "@/lib/attempt-summary";
import { useAttemptNotes } from "@/lib/use-attempt-notes";
import { formatScore, humanize } from "@/lib/format";
import type { AnswerAttemptSummary } from "@/lib/types";
import {
  ConnectionCard,
  LoadingPanel,
  Panel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import TopStatusBar from "@/components/TopStatusBar";
import RunRefreshBar from "@/components/RunRefreshBar";
import DiffusionTimeline from "@/components/DiffusionTimeline";
import EvidenceField from "@/components/EvidenceField";
import GeneratedLessonPanel from "@/components/GeneratedLessonPanel";
import ClaimDenoisingTable from "@/components/ClaimDenoisingTable";
import CitationLockPanel from "@/components/CitationLockPanel";
import ProofBundlePanel from "@/components/ProofBundlePanel";
import LearningScorePanel from "@/components/LearningScorePanel";
import ArtifactMatrix from "@/components/ArtifactMatrix";
import AnswerSubmissionPanel from "@/components/AnswerSubmissionPanel";
import AnswerHistoryPanel from "@/components/AnswerHistoryPanel";
import AnswerDiffPanel from "@/components/AnswerDiffPanel";
import ArtifactViewer from "@/components/ArtifactViewer";
import ResearchOverviewPanel from "@/components/ResearchOverviewPanel";
import SourceCoveragePanel from "@/components/SourceCoveragePanel";
import ClaimValidationPanel from "@/components/ClaimValidationPanel";
import LessonPlanQualityPanel from "@/components/LessonPlanQualityPanel";
import ResearchGapsPanel from "@/components/ResearchGapsPanel";
import NextResearchActionsPanel from "@/components/NextResearchActionsPanel";
import ResearchEnginePanels from "@/components/ResearchEnginePanels";
import LessonReader from "@/components/LessonReader";
import EvidenceDrawer from "@/components/EvidenceDrawer";
import ClaimReviewDesk from "@/components/ClaimReviewDesk";
import StudyJournalPanel from "@/components/StudyJournalPanel";
import ResearchPathMap from "@/components/ResearchPathMap";
import {
  buildStudyPathFromResearchInput,
  LIBRARY_TERMS,
  READING_ROOM_TABS,
  type ReadingRoomTab,
} from "@/lib/library-theme";
import type { ResearchValidationInput } from "@/lib/research-validation";

type DisplayMode = "library" | "research" | "operations" | "detailed" | "forensic";

function resolveDisplayMode(query: string | null): DisplayMode {
  if (query === "research" || query === "operations" || query === "detailed" || query === "forensic") {
    return query;
  }
  if (query === "overview") {
    return "library";
  }
  return "library";
}

function resolveLibraryTab(query: string | null): ReadingRoomTab {
  const valid = READING_ROOM_TABS.map((t) => t.id);
  if (query && valid.includes(query as ReadingRoomTab)) {
    return query as ReadingRoomTab;
  }
  return "reading-room";
}

const REFRESH_INTERVAL_MS = 5000;

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--sl-border)] py-1.5 last:border-0">
      <span className="text-[0.72rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {label}
      </span>
      <span className="text-right text-xs text-[var(--sl-text)]">{value}</span>
    </div>
  );
}

function ForensicJson({ title, value }: { title: string; value: unknown }) {
  if (value === null || value === undefined) {
    return null;
  }
  return (
    <details className="sl-panel overflow-hidden">
      <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-white">
        <span className="sl-panel-title">{title}</span>
      </summary>
      <div className="px-4 pb-4">
        <pre className="sl-code">{JSON.stringify(value, null, 2)}</pre>
      </div>
    </details>
  );
}

function RunStudioPageInner() {
  const params = useParams<{ runId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const runId = Array.isArray(params.runId) ? params.runId[0] : params.runId;

  const attemptQuery = parseAttemptQuery(searchParams);
  const attemptFromUrl = attemptQuery.attemptId;
  const fromFromUrl = attemptQuery.fromAttemptId;
  const toFromUrl = attemptQuery.toAttemptId;
  const presetFromUrl = attemptQuery.preset;
  const comparePinnedFromUrl = Boolean(fromFromUrl && toFromUrl);

  const [mode, setMode] = useState<DisplayMode>(() => resolveDisplayMode(searchParams.get("mode")));
  const [libraryTab, setLibraryTab] = useState<ReadingRoomTab>(() =>
    resolveLibraryTab(searchParams.get("tab")),
  );
  const [attemptsTab, setAttemptsTab] = useState<AttemptsTab>(() =>
    resolveAttemptsTabFromQuery(attemptQuery),
  );
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [learningPanelUsesAttempt, setLearningPanelUsesAttempt] = useState(Boolean(attemptFromUrl));
  const [diffFromId, setDiffFromId] = useState<string | null>(fromFromUrl);
  const [diffToId, setDiffToId] = useState<string | null>(toFromUrl);
  const [comparePinned, setComparePinned] = useState(comparePinnedFromUrl);
  const [invalidCompareWarning, setInvalidCompareWarning] = useState<string | null>(null);
  const [historyFilter, setHistoryFilter] = useState<HistoryFilter>(() =>
    resolveHistoryFilterFromQuery(attemptQuery),
  );
  const [historySearchQuery, setHistorySearchQuery] = useState(() =>
    resolveHistorySearchFromQuery(attemptQuery),
  );
  const [comparePreset, setComparePreset] = useState<ComparePreset | null>(presetFromUrl);
  const [focusedRowIndex, setFocusedRowIndex] = useState(-1);
  const [selectLatestAfterSubmit, setSelectLatestAfterSubmit] = useState(false);
  const [compareUrlApplied, setCompareUrlApplied] = useState(false);

  const attemptNotes = useAttemptNotes(runId);

  const {
    data,
    error,
    loading,
    refreshing,
    lastUpdated,
    autoRefresh,
    setAutoRefresh,
    refresh,
    intervalMs,
  } = useRunRefresh(() => refreshRunContext(runId), [runId], {
    intervalMs: REFRESH_INTERVAL_MS,
  });

  const history = useAnswerHistory(runId, {
    refreshKey: historyRefreshKey,
    initialAttemptId: attemptFromUrl,
  });

  const {
    attempts: attemptSummaries,
    selectedAttemptId,
    selectedAttemptDetail,
    summary: timeline,
    loading: historyLoading,
    error: historyError,
    detailLoading,
    detailError,
    invalidAttemptWarning,
    refresh: refreshHistory,
    selectAttempt,
    clearSelection,
  } = history;

  const replaceRunUrl = useCallback(
    (params: URLSearchParams) => {
      const query = params.toString();
      router.replace(query ? `/runs/${runId}?${query}` : `/runs/${runId}`, { scroll: false });
    },
    [router, runId],
  );

  const syncAttemptUrl = useCallback(
    (attemptId: string | null, activateOverlay: boolean) => {
      const next = buildAttemptQuery(searchParams.toString(), {
        attemptId: attemptId && activateOverlay ? attemptId : null,
      });
      replaceRunUrl(next);
    },
    [replaceRunUrl, searchParams],
  );

  const syncCompareUrl = useCallback(
    (fromId: string | null, toId: string | null, pinned: boolean) => {
      const next = buildAttemptQuery(searchParams.toString(), {
        fromAttemptId: pinned && fromId ? fromId : null,
        toAttemptId: pinned && toId ? toId : null,
        preset: null,
      });
      replaceRunUrl(next);
    },
    [replaceRunUrl, searchParams],
  );

  const syncPresetUrl = useCallback(
    (preset: ComparePreset | null) => {
      const next = buildAttemptQuery(searchParams.toString(), {
        preset,
        fromAttemptId: null,
        toAttemptId: null,
      });
      replaceRunUrl(next);
    },
    [replaceRunUrl, searchParams],
  );

  const syncWorkspaceTab = useCallback(
    (tab: AttemptsTab) => {
      const next = buildAttemptQuery(searchParams.toString(), { tab });
      replaceRunUrl(next);
    },
    [replaceRunUrl, searchParams],
  );

  const syncHistoryFilterUrl = useCallback(
    (filter: HistoryFilter) => {
      const next = buildAttemptQuery(searchParams.toString(), { filter });
      replaceRunUrl(next);
    },
    [replaceRunUrl, searchParams],
  );

  const syncHistorySearchUrl = useCallback(
    (query: string) => {
      const next = buildAttemptQuery(searchParams.toString(), { query });
      replaceRunUrl(next);
    },
    [replaceRunUrl, searchParams],
  );

  const handleAttemptsTabChange = useCallback(
    (tab: AttemptsTab) => {
      setAttemptsTab(tab);
      syncWorkspaceTab(tab);
    },
    [syncWorkspaceTab],
  );

  const handleHistoryFilterChange = useCallback(
    (filter: HistoryFilter) => {
      setHistoryFilter(filter);
      syncHistoryFilterUrl(filter);
    },
    [syncHistoryFilterUrl],
  );

  const handleHistorySearchQueryChange = useCallback(
    (query: string) => {
      setHistorySearchQuery(query);
      syncHistorySearchUrl(query);
    },
    [syncHistorySearchUrl],
  );

  const searchContext = useMemo(
    () => ({
      getNote: attemptNotes.getNote,
      hasNote: attemptNotes.hasNote,
    }),
    [attemptNotes.getNote, attemptNotes.hasNote],
  );

  const visibleAttempts = useMemo(
    () =>
      getVisibleHistoryAttempts(
        attemptSummaries,
        historyFilter,
        historySearchQuery,
        searchContext,
      ),
    [attemptSummaries, historyFilter, historySearchQuery, searchContext],
  );
  const reversedVisibleAttempts = useMemo(
    () => [...visibleAttempts].reverse(),
    [visibleAttempts],
  );

  const handleSelectAttempt = useCallback(
    (attemptId: string) => {
      selectAttempt(attemptId);
      setLearningPanelUsesAttempt(true);
      if (!comparePinned) {
        setDiffFromId(attemptId);
        if (attemptSummaries.length > 0) {
          setDiffToId(attemptSummaries[attemptSummaries.length - 1].attempt_id);
        }
      }
      syncAttemptUrl(attemptId, true);
      const rowIndex = reversedVisibleAttempts.findIndex((a) => a.attempt_id === attemptId);
      if (rowIndex >= 0) {
        setFocusedRowIndex(rowIndex);
      }
    },
    [selectAttempt, attemptSummaries, comparePinned, syncAttemptUrl, reversedVisibleAttempts],
  );

  const handleBackToLatestSnapshot = useCallback(() => {
    setLearningPanelUsesAttempt(false);
    clearSelection();
    syncAttemptUrl(null, false);
    if (reversedVisibleAttempts.length > 0) {
      setFocusedRowIndex(0);
    }
  }, [clearSelection, syncAttemptUrl, reversedVisibleAttempts.length]);

  const handleDiffFromChange = useCallback(
    (attemptId: string) => {
      setDiffFromId(attemptId);
      if (comparePinned) {
        syncCompareUrl(attemptId, diffToId, true);
      }
    },
    [comparePinned, diffToId, syncCompareUrl],
  );

  const handleDiffToChange = useCallback(
    (attemptId: string) => {
      setDiffToId(attemptId);
      if (comparePinned) {
        syncCompareUrl(diffFromId, attemptId, true);
      }
    },
    [comparePinned, diffFromId, syncCompareUrl],
  );

  const handleQuickCompare = useCallback(
    (fromId: string | null, toId: string | null, preset?: ComparePreset | null) => {
      if (fromId) {
        setDiffFromId(fromId);
      }
      if (toId) {
        setDiffToId(toId);
      }
      if (comparePinned && fromId && toId) {
        setComparePreset(null);
        syncCompareUrl(fromId, toId, true);
      } else if (preset) {
        setComparePreset(preset);
        syncPresetUrl(preset);
      } else if (fromId && toId) {
        setComparePreset(null);
        syncCompareUrl(fromId, toId, false);
      }
    },
    [comparePinned, syncCompareUrl, syncPresetUrl],
  );

  const handlePinComparison = useCallback(() => {
    if (!diffFromId || !diffToId) {
      return;
    }
    setComparePinned(true);
    setComparePreset(null);
    syncCompareUrl(diffFromId, diffToId, true);
  }, [diffFromId, diffToId, syncCompareUrl]);

  const handleClearComparison = useCallback(() => {
    setComparePinned(false);
    setComparePreset(null);
    setInvalidCompareWarning(null);
    syncCompareUrl(null, null, false);
    syncPresetUrl(null);
    if (attemptSummaries.length >= 2) {
      setDiffFromId(attemptSummaries[0].attempt_id);
      setDiffToId(attemptSummaries[attemptSummaries.length - 1].attempt_id);
    }
  }, [syncCompareUrl, syncPresetUrl, attemptSummaries]);

  const handleAnswerSubmitted = async () => {
    setHistoryRefreshKey((k) => k + 1);
    setSelectLatestAfterSubmit(true);
    await refresh();
    handleAttemptsTabChange("history");
  };

  useEffect(() => {
    setCompareUrlApplied(false);
    const parsed = parseAttemptQuery(searchParams);
    setAttemptsTab(resolveAttemptsTabFromQuery(parsed));
    setHistoryFilter(resolveHistoryFilterFromQuery(parsed));
    setHistorySearchQuery(resolveHistorySearchFromQuery(parsed));
    setComparePreset(parsed.preset);
  }, [runId, searchParams]);

  useEffect(() => {
    if (!selectLatestAfterSubmit || attemptSummaries.length === 0) {
      return;
    }
    const newest = attemptSummaries[attemptSummaries.length - 1];
    handleSelectAttempt(newest.attempt_id);
    setSelectLatestAfterSubmit(false);
  }, [selectLatestAfterSubmit, attemptSummaries, handleSelectAttempt]);

  useEffect(() => {
    if (invalidAttemptWarning) {
      setLearningPanelUsesAttempt(false);
      syncAttemptUrl(null, false);
    }
  }, [invalidAttemptWarning, syncAttemptUrl]);

  useEffect(() => {
    if (attemptFromUrl && attemptSummaries.some((a) => a.attempt_id === attemptFromUrl)) {
      setLearningPanelUsesAttempt(true);
      if (!attemptQuery.tab && !comparePinnedFromUrl) {
        setAttemptsTab("history");
      }
    }
  }, [attemptFromUrl, attemptSummaries, attemptQuery.tab, comparePinnedFromUrl]);

  useEffect(() => {
    if (attemptSummaries.length < 2 || compareUrlApplied) {
      return;
    }

    const validId = (id: string | null) =>
      id !== null && attemptSummaries.some((a) => a.attempt_id === id);

    const timelineForCompare = computeAttemptTimelineSummary(attemptSummaries, selectedAttemptId);
    const latest = attemptSummaries[attemptSummaries.length - 1].attempt_id;
    const fallbackFrom =
      selectedAttemptId && validId(selectedAttemptId)
        ? selectedAttemptId
        : attemptSummaries[0].attempt_id;
    const fallbackTo = latest;

    if (fromFromUrl || toFromUrl) {
      setCompareUrlApplied(true);
      const fromValid = validId(fromFromUrl);
      const toValid = validId(toFromUrl);

      if (!fromValid || !toValid) {
        const invalidParts = [
          fromFromUrl && !fromValid ? `"${fromFromUrl}"` : null,
          toFromUrl && !toValid ? `"${toFromUrl}"` : null,
        ].filter(Boolean);
        setInvalidCompareWarning(
          `Compare ${invalidParts.join(" / ")} not found — using defaults.`,
        );
        setDiffFromId(fallbackFrom);
        setDiffToId(fallbackTo);
        setComparePinned(false);
        setComparePreset(null);
        syncCompareUrl(null, null, false);
      } else {
        setDiffFromId(fromFromUrl);
        setDiffToId(toFromUrl);
        setComparePinned(true);
        setComparePreset(null);
        setInvalidCompareWarning(null);
      }
      return;
    }

    if (presetFromUrl) {
      setCompareUrlApplied(true);
      const derived = deriveComparePairFromPreset(
        presetFromUrl,
        timelineForCompare,
        selectedAttemptId,
      );
      if (derived && validId(derived.fromAttemptId) && validId(derived.toAttemptId)) {
        setDiffFromId(derived.fromAttemptId);
        setDiffToId(derived.toAttemptId);
        setComparePreset(presetFromUrl);
        setComparePinned(false);
        setInvalidCompareWarning(null);
      } else {
        setInvalidCompareWarning(`Compare preset "${presetFromUrl}" could not be resolved.`);
        setDiffFromId(fallbackFrom);
        setDiffToId(fallbackTo);
        setComparePreset(null);
        setComparePinned(false);
        syncPresetUrl(null);
      }
      return;
    }

    if (diffFromId === null) {
      setDiffFromId(attemptSummaries[0].attempt_id);
      setDiffToId(attemptSummaries[attemptSummaries.length - 1].attempt_id);
    }
  }, [
    attemptSummaries,
    compareUrlApplied,
    diffFromId,
    fromFromUrl,
    presetFromUrl,
    selectedAttemptId,
    syncCompareUrl,
    syncPresetUrl,
    toFromUrl,
  ]);

  useEffect(() => {
    if (attemptsTab === "diff" && selectedAttemptId && !comparePinned) {
      setDiffFromId(selectedAttemptId);
      if (attemptSummaries.length > 0) {
        setDiffToId(attemptSummaries[attemptSummaries.length - 1].attempt_id);
      }
    }
  }, [attemptsTab, selectedAttemptId, attemptSummaries, comparePinned]);

  useEffect(() => {
    if (selectedAttemptId && reversedVisibleAttempts.length > 0) {
      const rowIndex = reversedVisibleAttempts.findIndex(
        (a) => a.attempt_id === selectedAttemptId,
      );
      if (rowIndex >= 0 && focusedRowIndex < 0) {
        setFocusedRowIndex(rowIndex);
      }
    }
  }, [selectedAttemptId, reversedVisibleAttempts, focusedRowIndex]);

  useEffect(() => {
    if (attemptsTab !== "history" && attemptsTab !== "diff") {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) {
        return;
      }

      const focusDetail = (window as Window & { __slFocusAttemptDetail?: () => void })
        .__slFocusAttemptDetail;

      if (attemptsTab === "history" && visibleAttempts.length === 0) {
        return;
      }

      switch (event.key) {
        case "ArrowDown":
        case "ArrowRight": {
          if (attemptsTab !== "history") {
            break;
          }
          event.preventDefault();
          const id = getAdjacentFilteredAttemptId(
            reversedVisibleAttempts,
            selectedAttemptId,
            "prev",
          );
          if (id) {
            handleSelectAttempt(id);
          }
          break;
        }
        case "ArrowUp":
        case "ArrowLeft": {
          if (attemptsTab !== "history") {
            break;
          }
          event.preventDefault();
          const id = getAdjacentFilteredAttemptId(
            reversedVisibleAttempts,
            selectedAttemptId,
            "next",
          );
          if (id) {
            handleSelectAttempt(id);
          }
          break;
        }
        case "Home":
          if (attemptsTab !== "history") {
            break;
          }
          event.preventDefault();
          if (visibleAttempts.length > 0) {
            handleSelectAttempt(visibleAttempts[0].attempt_id);
          }
          break;
        case "End":
          if (attemptsTab !== "history") {
            break;
          }
          event.preventDefault();
          if (visibleAttempts.length > 0) {
            handleSelectAttempt(visibleAttempts[visibleAttempts.length - 1].attempt_id);
          }
          break;
        case "Enter":
          if (attemptsTab === "history" && selectedAttemptId) {
            event.preventDefault();
            focusDetail?.();
          }
          break;
        case "Escape":
          event.preventDefault();
          handleBackToLatestSnapshot();
          break;
        default:
          break;
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [
    attemptsTab,
    selectedAttemptId,
    visibleAttempts,
    reversedVisibleAttempts,
    handleSelectAttempt,
    handleBackToLatestSnapshot,
  ]);

  const latestAttemptId = timeline.latestAttemptId;

  const syncLibraryTabUrl = useCallback(
    (tab: ReadingRoomTab) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", tab);
      if (!params.get("mode")) {
        params.set("mode", "library");
      }
      replaceRunUrl(params);
    },
    [replaceRunUrl, searchParams],
  );

  const handleLibraryTabChange = useCallback(
    (tab: ReadingRoomTab) => {
      setLibraryTab(tab);
      syncLibraryTabUrl(tab);
    },
    [syncLibraryTabUrl],
  );

  const handleModeChange = useCallback(
    (next: DisplayMode) => {
      setMode(next);
      const params = new URLSearchParams(searchParams.toString());
      params.set("mode", next);
      replaceRunUrl(params);
    },
    [replaceRunUrl, searchParams],
  );

  const selectedAttemptSummary: AnswerAttemptSummary | null =
    selectedAttemptId !== null
      ? attemptSummaries.find((a) => a.attempt_id === selectedAttemptId) ?? null
      : null;

  const viewingHistoricalAttempt =
    Boolean(
      learningPanelUsesAttempt &&
        selectedAttemptId &&
        latestAttemptId &&
        selectedAttemptId !== latestAttemptId,
    );

  if (loading && !data) {
    return (
      <PageShell>
        <PageHeader title="Run Studio" subtitle={`Stabilizing field for ${runId}…`} />
        <LoadingPanel />
      </PageShell>
    );
  }

  if (error && !data) {
    return (
      <PageShell>
        <PageHeader title="Run Studio">
          <Link href="/runs" className="sl-btn">
            ← All runs
          </Link>
        </PageHeader>
        <ConnectionCard error={error} onRetry={refresh} />
      </PageShell>
    );
  }

  const studio = data!;
  const { run } = studio;
  const showForensic = mode === "forensic";
  const showDetailed = mode === "detailed" || mode === "forensic";
  const showResearch = mode === "research";
  const showLibrary = mode === "library";
  const showOperations = mode === "operations";

  const researchInput: ResearchValidationInput = {
    run: studio.run,
    chunks: studio.chunks,
    atomicClaims: studio.atomicClaims,
    claimMap: studio.claimMap,
    evidence: studio.evidence,
    citation: studio.citation,
    verification: studio.verification,
    humanReviewQueue: studio.humanReviewQueue,
    lessonPackage: studio.lessonPackage,
    learning: studio.learning,
    diagnostics: studio.diagnostics,
  };

  const latestScore = timeline.latestScore ?? run.overall_score ?? run.answer_score ?? null;
  const selectedScore = timeline.selectedScore;
  const scoreDelta = timeline.selectedToLatestDelta;
  const learningPanelAttempt =
    learningPanelUsesAttempt && selectedAttemptDetail ? selectedAttemptDetail : null;

  const studyPathSteps = buildStudyPathFromResearchInput(
    researchInput,
    timeline.totalAttempts > 0,
    Boolean(studio.lesson?.lesson_markdown?.trim()),
    studio.proof?.summary?.release_gate_status === "PASS" || studio.proof?.status === "PASS",
  );

  return (
    <PageShell>
      <PageHeader
        title={
          <>
            {LIBRARY_TERMS.readingRoom}{" "}
            <span className="sl-gradient-text">{run.topic || run.run_id}</span>
          </>
        }
        subtitle={run.run_id}
      >
        <Link href="/runs" className="sl-btn px-3 py-1.5 text-xs">
          ← All sessions
        </Link>
        <div className="flex overflow-hidden rounded-lg border border-[var(--sl-border-strong)]">
          {(["library", "research", "operations", "detailed", "forensic"] as DisplayMode[]).map(
            (option) => (
              <button
                key={option}
                type="button"
                onClick={() => handleModeChange(option)}
                className={`px-3 py-1.5 text-xs capitalize transition-colors ${
                  mode === option
                    ? "bg-[rgba(212,175,106,0.16)] text-white"
                    : "text-[var(--sl-text-dim)] hover:text-white"
                }`}
              >
                {option === "library" ? "Reading Room" : option}
              </button>
            ),
          )}
        </div>
      </PageHeader>

      <RunRefreshBar
        lastUpdated={lastUpdated}
        refreshing={refreshing}
        autoRefresh={autoRefresh}
        intervalMs={intervalMs}
        offline={Boolean(error)}
        onToggleAuto={setAutoRefresh}
        onRefresh={refresh}
      />

      {error && data && (
        <div className="mb-4 rounded-xl border border-[rgba(244,63,94,0.3)] bg-[rgba(244,63,94,0.07)] px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill
              tone="blocked"
              label={error.isConnectionError ? "API OFFLINE" : `ERROR ${error.status}`}
            />
            <span className="text-xs text-[var(--sl-text-dim)]">
              {error.message} Showing the last successfully loaded snapshot — press Refresh to retry.
            </span>
          </div>
        </div>
      )}

      <TopStatusBar
        run={run}
        selectedAttempt={viewingHistoricalAttempt ? selectedAttemptSummary : null}
        viewMode={viewingHistoricalAttempt ? "attempt" : "latest"}
      />

      {showResearch ? (
        <div className="mt-4 space-y-4">
          <ResearchOverviewPanel input={researchInput} />
          <div className="grid gap-4 xl:grid-cols-2">
            <SourceCoveragePanel input={researchInput} />
            <ClaimValidationPanel input={researchInput} />
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <LessonPlanQualityPanel input={researchInput} />
            <ResearchGapsPanel input={researchInput} />
          </div>
          <NextResearchActionsPanel input={researchInput} runId={run.run_id} />
          <ResearchEnginePanels
            researchPlan={studio.researchPlan}
            retrievalStrategy={studio.retrievalStrategy}
            sourceCoverageReport={studio.sourceCoverageReport}
            evidenceBoundLessonPlan={studio.evidenceBoundLessonPlan}
            genericnessReport={studio.genericnessReport}
            topicProfileUpdate={studio.topicProfileUpdate}
            sourceExpansionSuggestions={studio.sourceExpansionSuggestions}
            lessonEvolutionReport={studio.lessonEvolutionReport}
            libraryExpansionPlan={studio.libraryExpansionPlan}
            libraryExpansionExecution={studio.libraryExpansionExecution}
            libraryImprovementReport={studio.libraryImprovementReport}
            sourcePromotionReport={studio.sourcePromotionReport}
            gapClosureReport={studio.gapClosureReport}
            gapClosureOrchestration={studio.gapClosureOrchestration}
          />
          <Panel title="Operations shortcut" hint="Research mode does not replace operations views">
            <p className="mb-3 text-sm text-[var(--sl-text-dim)]">
              Switch to Operations for attempts, proof stabilization, and harness checks.
            </p>
            <button type="button" className="sl-btn text-xs" onClick={() => handleModeChange("operations")}>
              Back to operations
            </button>
          </Panel>
        </div>
      ) : showLibrary ? (
        <div className="mt-4 space-y-4">
          <ResearchPathMap steps={studyPathSteps} title={LIBRARY_TERMS.studyPath} />

          <div className="flex overflow-x-auto rounded-lg border border-[var(--sl-border-strong)]">
            {READING_ROOM_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleLibraryTabChange(tab.id)}
                className={`whitespace-nowrap px-4 py-2 text-xs transition-colors ${
                  libraryTab === tab.id
                    ? "bg-[rgba(212,175,106,0.14)] text-white"
                    : "text-[var(--sl-text-dim)] hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {libraryTab === "reading-room" && (
            <Panel title={LIBRARY_TERMS.readingRoom} hint="Source-grounded lesson" glow="cyan">
              <LessonReader lesson={studio.lesson} lessonPackage={studio.lessonPackage} />
            </Panel>
          )}

          {libraryTab === "sources" && (
            <EvidenceDrawer chunks={studio.chunks} diagnostics={studio.diagnostics} />
          )}

          {libraryTab === "claims" && <ClaimReviewDesk input={researchInput} />}

          {libraryTab === "proof" && (
            <div className="grid gap-4 xl:grid-cols-2">
              <Panel title="Proof stabilization">
                <ProofBundlePanel proof={studio.proof} />
              </Panel>
              <Panel title="Citation locking" glow="violet">
                <CitationLockPanel citation={studio.citation} grounding={studio.grounding} />
              </Panel>
            </div>
          )}

          {libraryTab === "journal" && (
            <StudyJournalPanel summary={timeline} attempts={attemptSummaries}>
              <div className="mb-3 flex overflow-hidden rounded-lg border border-[var(--sl-border-strong)]">
                {(
                  [
                    { key: "submit", label: "Submit" },
                    { key: "history", label: "History" },
                    { key: "diff", label: "Diff" },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => handleAttemptsTabChange(tab.key)}
                    className={`flex-1 px-3 py-1.5 text-xs transition-colors ${
                      attemptsTab === tab.key
                        ? "bg-[rgba(168,85,247,0.16)] text-white"
                        : "text-[var(--sl-text-dim)] hover:text-white"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              {attemptsTab === "submit" && (
                <AnswerSubmissionPanel
                  runId={run.run_id}
                  topic={run.topic}
                  onSubmitted={handleAnswerSubmitted}
                />
              )}
              {attemptsTab === "history" && (
                <AnswerHistoryPanel
                  runId={run.run_id}
                  attempts={attemptSummaries}
                  selectedAttemptId={selectedAttemptId}
                  selectedAttemptDetail={selectedAttemptDetail}
                  summary={timeline}
                  loading={historyLoading}
                  error={historyError}
                  detailLoading={detailLoading}
                  detailError={detailError}
                  invalidAttemptWarning={invalidAttemptWarning}
                  onSelectAttempt={handleSelectAttempt}
                  onClearSelection={handleBackToLatestSnapshot}
                  onRefreshHistory={refreshHistory}
                  focusedRowIndex={focusedRowIndex}
                  onFocusedRowIndexChange={setFocusedRowIndex}
                  historyFilter={historyFilter}
                  onHistoryFilterChange={handleHistoryFilterChange}
                  historySearchQuery={historySearchQuery}
                  onHistorySearchQueryChange={handleHistorySearchQueryChange}
                  hasAttemptNote={attemptNotes.hasNote}
                  getAttemptNote={attemptNotes.getNote}
                  notesStore={attemptNotes.notes}
                  onSaveAttemptNote={attemptNotes.saveNote}
                  noteLastSavedAt={attemptNotes.lastSavedAt}
                  onExportNotes={attemptNotes.exportNotesJson}
                  onImportNotes={attemptNotes.importNotesJson}
                  onClearAllNotes={attemptNotes.clearAllNotes}
                  workspaceTab={attemptsTab}
                  workspaceFromAttemptId={comparePinned ? diffFromId : null}
                  workspaceToAttemptId={comparePinned ? diffToId : null}
                  workspacePreset={comparePinned ? null : comparePreset}
                />
              )}
              {attemptsTab === "diff" && (
                <AnswerDiffPanel
                  runId={run.run_id}
                  attempts={attemptSummaries}
                  fromAttemptId={diffFromId ?? selectedAttemptId}
                  toAttemptId={diffToId ?? latestAttemptId}
                  selectedAttemptId={selectedAttemptId}
                  comparePinned={comparePinned}
                  invalidCompareWarning={invalidCompareWarning}
                  onFromChange={handleDiffFromChange}
                  onToChange={handleDiffToChange}
                  onQuickCompare={handleQuickCompare}
                  onPinComparison={handlePinComparison}
                  onClearComparison={handleClearComparison}
                />
              )}
            </StudyJournalPanel>
          )}

          {libraryTab === "artifacts" && (
            <Panel title="Artifact matrix">
              <ArtifactMatrix artifacts={studio.artifacts} />
            </Panel>
          )}
        </div>
      ) : showOperations ? (
      <div className="mt-4 grid gap-4 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-3">
          <Panel title="Diffusion timeline" hint="Source field → proof → learning update" glow="cyan">
            <DiffusionTimeline
              run={run}
              artifacts={studio.artifacts}
              citation={studio.citation}
              attemptLane={
                timeline.totalAttempts > 0
                  ? {
                      attemptCount: timeline.totalAttempts,
                      latestScore: timeline.latestScore,
                      bestScore: timeline.bestScore,
                      needsReviewCount: timeline.needsReviewCount,
                      selectedAttemptId: viewingHistoricalAttempt ? selectedAttemptId : null,
                    }
                  : null
              }
            />
          </Panel>

          <Panel title="Field parameters">
            <div className="space-y-0">
              <InfoRow label="Source policy" value={studio.manifest?.source_policy ?? "—"} />
              <InfoRow
                label="Retrieval"
                value={studio.manifest?.retrieval_mode ?? studio.diagnostics?.mode ?? "—"}
              />
              <InfoRow
                label="Retriever"
                value={`${studio.diagnostics?.backend ?? "—"} / ${studio.diagnostics?.store ?? "—"}`}
              />
              <InfoRow
                label="Generation"
                value={studio.manifest?.generation_backend ?? "—"}
              />
              <InfoRow
                label="Model mode"
                value={studio.modelConfig ? `${studio.modelConfig.mode}` : "—"}
              />
              <InfoRow
                label="Model backend"
                value={studio.modelConfig?.backend ?? "—"}
              />
              <InfoRow label="Verification" value={studio.manifest?.verification_version ?? "—"} />
            </div>
          </Panel>

          <Panel title="Next task" hint="Skill profile → next focus" glow="violet">
            {studio.nextTask && (studio.nextTask.focus || studio.nextTask.reason) ? (
              <div className="space-y-2">
                <div className="text-sm font-medium text-white">
                  {studio.nextTask.focus || "—"}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <span className="sl-pill sl-pill--neutral">
                    {humanize(studio.nextTask.task_format)}
                  </span>
                  <span className="sl-pill sl-pill--neutral">difficulty {studio.nextTask.difficulty}</span>
                  <span className="sl-pill sl-pill--neutral">guidance {studio.nextTask.guidance_level}</span>
                </div>
                {studio.nextTask.reason && (
                  <p className="text-xs leading-relaxed text-[var(--sl-text-dim)]">
                    {studio.nextTask.reason}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--sl-text-faint)]">No next-task recommendation.</p>
            )}
          </Panel>
        </div>

        <div className="space-y-4 xl:col-span-5">
          <Panel title="Generated lesson" hint="Source-grounded draft" glow="cyan">
            <GeneratedLessonPanel lesson={studio.lesson} />
          </Panel>

          <Panel title="Attempts" hint="Submit · history · diff · ↑↓ navigate" glow="violet" id="attempts-workspace">
            <div className="mb-3 flex overflow-hidden rounded-lg border border-[var(--sl-border-strong)]">
              {(
                [
                  { key: "submit", label: "Submit" },
                  { key: "history", label: "History" },
                  { key: "diff", label: "Diff" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => handleAttemptsTabChange(tab.key)}
                  className={`flex-1 px-3 py-1.5 text-xs transition-colors ${
                    attemptsTab === tab.key
                      ? "bg-[rgba(168,85,247,0.16)] text-white"
                      : "text-[var(--sl-text-dim)] hover:text-white"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {timeline.totalAttempts > 0 && (
              <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.4)] px-3 py-2 text-[0.72rem] text-[var(--sl-text-dim)]">
                <span>
                  First{" "}
                  <span className="font-mono text-white">{formatScore(timeline.firstScore)}</span>
                </span>
                <span className="text-[var(--sl-text-faint)]">|</span>
                <span>
                  Selected{" "}
                  <span className="font-mono text-[var(--sl-violet)]">
                    {formatScore(selectedScore)}
                  </span>
                </span>
                <span className="text-[var(--sl-text-faint)]">|</span>
                <span>
                  Latest{" "}
                  <span className="font-mono text-white">{formatScore(timeline.latestScore)}</span>
                </span>
                <span className="text-[var(--sl-text-faint)]">|</span>
                <span>
                  Best{" "}
                  <span className="font-mono text-[var(--sl-emerald)]">
                    {formatScore(timeline.bestScore)}
                  </span>
                </span>
                {viewingHistoricalAttempt && scoreDelta !== null && (
                  <>
                    <span className="text-[var(--sl-text-faint)]">|</span>
                    <span>
                      Δ selected→latest{" "}
                      <span className={`font-mono ${deltaToneClass(scoreDelta)}`}>
                        {formatScoreDelta(scoreDelta)}
                      </span>
                    </span>
                  </>
                )}
                {timeline.needsReviewCount > 0 && (
                  <>
                    <span className="text-[var(--sl-text-faint)]">|</span>
                    <span className="text-[var(--sl-amber)]">
                      {timeline.needsReviewCount} review
                    </span>
                  </>
                )}
                {timeline.cappedCount > 0 && (
                  <>
                    <span className="text-[var(--sl-text-faint)]">|</span>
                    <span className="text-[var(--sl-amber)]">{timeline.cappedCount} capped</span>
                  </>
                )}
              </div>
            )}

            {attemptsTab === "submit" && (
              <AnswerSubmissionPanel
                runId={run.run_id}
                topic={run.topic}
                onSubmitted={handleAnswerSubmitted}
              />
            )}
            {attemptsTab === "history" && (
              <AnswerHistoryPanel
                runId={run.run_id}
                attempts={attemptSummaries}
                selectedAttemptId={selectedAttemptId}
                selectedAttemptDetail={selectedAttemptDetail}
                summary={timeline}
                loading={historyLoading}
                error={historyError}
                detailLoading={detailLoading}
                detailError={detailError}
                invalidAttemptWarning={invalidAttemptWarning}
                onSelectAttempt={handleSelectAttempt}
                onClearSelection={handleBackToLatestSnapshot}
                onRefreshHistory={refreshHistory}
                focusedRowIndex={focusedRowIndex}
                onFocusedRowIndexChange={setFocusedRowIndex}
                historyFilter={historyFilter}
                onHistoryFilterChange={handleHistoryFilterChange}
                historySearchQuery={historySearchQuery}
                onHistorySearchQueryChange={handleHistorySearchQueryChange}
                hasAttemptNote={attemptNotes.hasNote}
                getAttemptNote={attemptNotes.getNote}
                notesStore={attemptNotes.notes}
                onSaveAttemptNote={attemptNotes.saveNote}
                noteLastSavedAt={attemptNotes.lastSavedAt}
                onExportNotes={attemptNotes.exportNotesJson}
                onImportNotes={attemptNotes.importNotesJson}
                onClearAllNotes={attemptNotes.clearAllNotes}
                workspaceTab={attemptsTab}
                workspaceFromAttemptId={comparePinned ? diffFromId : null}
                workspaceToAttemptId={comparePinned ? diffToId : null}
                workspacePreset={comparePinned ? null : comparePreset}
              />
            )}
            {attemptsTab === "diff" && (
              <AnswerDiffPanel
                runId={run.run_id}
                attempts={attemptSummaries}
                fromAttemptId={diffFromId ?? selectedAttemptId}
                toAttemptId={diffToId ?? latestAttemptId}
                selectedAttemptId={selectedAttemptId}
                comparePinned={comparePinned}
                invalidCompareWarning={invalidCompareWarning}
                onFromChange={handleDiffFromChange}
                onToChange={handleDiffToChange}
                onQuickCompare={handleQuickCompare}
                onPinComparison={handlePinComparison}
                onClearComparison={handleClearComparison}
              />
            )}
          </Panel>

          <Panel title="Claim denoising" hint="Supported vs unsupported claims">
            <ClaimDenoisingTable claims={studio.claimMap} evidenceMatches={studio.evidence} />
          </Panel>

          <Panel title="Citation locking" glow="violet" id="citation-locking">
            <CitationLockPanel citation={studio.citation} grounding={studio.grounding} />
          </Panel>
        </div>

        <div className="space-y-4 xl:col-span-4">
          <Panel title="Evidence field" hint="Retrieved source particles" glow="cyan">
            <EvidenceField chunks={studio.chunks} diagnostics={studio.diagnostics} />
          </Panel>

          <Panel title="Proof stabilization">
            <ProofBundlePanel proof={studio.proof} />
          </Panel>

          <Panel title="Learning update" glow="violet">
            {learningPanelUsesAttempt &&
              selectedScore !== null &&
              latestScore !== null &&
              viewingHistoricalAttempt && (
                <div className="mb-3 rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] px-3 py-2 text-xs text-[var(--sl-text-dim)]">
                  Selected {formatScore(selectedScore)} · Latest {formatScore(latestScore)} · Delta{" "}
                  <span className={deltaToneClass(scoreDelta)}>
                    {formatScoreDelta(scoreDelta)}
                  </span>
                </div>
              )}
            <LearningScorePanel
              run={run}
              learningJson={studio.learning?.report_json ?? null}
              selectedAttempt={learningPanelAttempt}
              onBackToLatest={handleBackToLatestSnapshot}
            />
          </Panel>

          <Panel title="Artifact matrix">
            <ArtifactMatrix artifacts={studio.artifacts} />
          </Panel>
        </div>
      </div>
      ) : null}

      {showDetailed && studio.harness && (
        <div className="mt-4">
          <Panel
            title="Harness checks"
            hint={`${studio.harness.checks.length} checks · ${studio.harness.blocking_failures.length} blocking`}
          >
            <div className="grid gap-1.5 md:grid-cols-2">
              {studio.harness.checks.map((check) => (
                <div
                  key={check.check_name}
                  className="flex items-start justify-between gap-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.4)] px-3 py-2"
                >
                  <div className="min-w-0">
                    <div className="font-mono text-[0.72rem] text-[var(--sl-text)]">
                      {check.check_name}
                    </div>
                    <div className="truncate text-[0.7rem] text-[var(--sl-text-faint)]" title={check.message}>
                      {check.message}
                    </div>
                  </div>
                  <StatusPill status={check.passed} label={check.passed ? "PASS" : "FAIL"} />
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {showForensic && (
        <div className="mt-4 space-y-3">
          <h2 className="sl-panel-title">Forensic · artifacts</h2>
          <Panel title="Artifact loader" hint="Load raw artifact content from the API">
            <ArtifactViewer runId={run.run_id} />
          </Panel>
          <div className="grid gap-3 lg:grid-cols-2">
            <ForensicJson title="run_manifest.json" value={studio.manifest} />
            <ForensicJson title="proof bundle" value={studio.proof} />
            <ForensicJson title="harness_report" value={studio.harness} />
            <ForensicJson title="learning_report.json" value={studio.learning?.report_json} />
            <ForensicJson title="verification_report.json" value={studio.verification} />
            <ForensicJson title="human_review_queue.json" value={studio.humanReviewQueue} />
            <ForensicJson title="generated_lesson_package.json" value={studio.lessonPackage} />
            <ForensicJson title="atomic_claims.json" value={studio.atomicClaims} />
            <ForensicJson title="claim_map.json" value={studio.claimMap} />
            <ForensicJson title="evidence_matches.json" value={studio.evidence} />
            <ForensicJson title="citation_resolution.json" value={studio.citation} />
            <ForensicJson title="source_grounding_review.json" value={studio.grounding} />
            <ForensicJson title="retrieved_chunks.json" value={studio.chunks} />
            <ForensicJson title="retrieval_diagnostics.json" value={studio.diagnostics} />
            <ForensicJson title="answer_review.json" value={studio.answerReview} />
          </div>
        </div>
      )}
    </PageShell>
  );
}

export default function RunStudioPage() {
  return (
    <Suspense
      fallback={
        <PageShell>
          <PageHeader title="Run Studio" subtitle="Loading…" />
          <LoadingPanel />
        </PageShell>
      }
    >
      <RunStudioPageInner />
    </Suspense>
  );
}
