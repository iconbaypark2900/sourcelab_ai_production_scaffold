"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import AttemptDetailPanel from "@/components/AttemptDetailPanel";
import AttemptScoreSparkline from "@/components/AttemptScoreSparkline";
import CopyAttemptLinkButton from "@/components/CopyAttemptLinkButton";
import CopyWorkspaceLinkButton from "@/components/CopyWorkspaceLinkButton";
import type { AttemptsTab, ComparePreset } from "@/lib/attempt-url";
import {
  countAttemptsWithNotes,
  countVisibleNotes,
  getVisibleHistoryAttempts,
} from "@/lib/attempt-filters";
import { getAnswerAttempt, getAnswerHistory, SourceLabApiError } from "@/lib/sourcelab-api";
import {
  computeAttemptTimelineSummary,
  deltaToneClass,
  formatScoreDelta,
  type AttemptTimelineSummary,
  type HistoryFilter,
} from "@/lib/attempt-summary";
import { exportFilteredAttemptNotes } from "@/lib/use-attempt-notes";
import type { AttemptNotesStore } from "@/lib/use-attempt-notes";
import type { AnswerAttemptDetail, AnswerAttemptSummary } from "@/lib/types";
import { formatScore } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

interface AnswerHistoryPanelProps {
  runId: string;
  /** Controlled: attempt list from parent hook. */
  attempts?: AnswerAttemptSummary[];
  selectedAttemptId?: string | null;
  selectedAttemptDetail?: AnswerAttemptDetail | null;
  summary?: AttemptTimelineSummary;
  loading?: boolean;
  error?: SourceLabApiError | null;
  detailLoading?: boolean;
  detailError?: SourceLabApiError | null;
  invalidAttemptWarning?: string | null;
  onSelectAttempt?: (attemptId: string) => void;
  onClearSelection?: () => void;
  onRefreshHistory?: () => void;
  /** @deprecated Use controlled props from useAnswerHistory. */
  onDetailChange?: (detail: AnswerAttemptDetail | null) => void;
  /** @deprecated Use onRefreshHistory from parent. */
  refreshKey?: number;
  /** Keyboard focus: index of row receiving roving focus (-1 = none). */
  focusedRowIndex?: number;
  onFocusedRowIndexChange?: (index: number) => void;
  /** Controlled history filter (for filter-aware keyboard nav in parent). */
  historyFilter?: HistoryFilter;
  onHistoryFilterChange?: (filter: HistoryFilter) => void;
  /** Controlled search query synced to URL `q` param. */
  historySearchQuery?: string;
  onHistorySearchQueryChange?: (query: string) => void;
  hasAttemptNote?: (attemptId: string) => boolean;
  getAttemptNote?: (attemptId: string) => string;
  notesStore?: AttemptNotesStore;
  onSaveAttemptNote?: (attemptId: string, note: string) => void;
  noteLastSavedAt?: string | null;
  onExportNotes?: () => string;
  onImportNotes?: (jsonText: string) => { ok: true } | { ok: false; error: string };
  onClearAllNotes?: () => void;
  workspaceTab?: AttemptsTab;
  workspaceFromAttemptId?: string | null;
  workspaceToAttemptId?: string | null;
  workspacePreset?: ComparePreset | null;
}

const FILTER_LABELS: Record<HistoryFilter, string> = {
  all: "All",
  needs_review: "Needs review",
  passed: "Passed",
  capped: "Capped only",
  has_notes: "Has notes",
  no_notes: "No notes",
};

export default function AnswerHistoryPanel({
  runId,
  attempts: controlledAttempts,
  selectedAttemptId,
  selectedAttemptDetail,
  summary: controlledSummary,
  loading: controlledLoading,
  error: controlledError,
  detailLoading: controlledDetailLoading,
  detailError: controlledDetailError,
  invalidAttemptWarning,
  onSelectAttempt,
  onClearSelection,
  onRefreshHistory,
  onDetailChange,
  refreshKey = 0,
  focusedRowIndex = -1,
  onFocusedRowIndexChange,
  historyFilter: controlledFilter,
  onHistoryFilterChange,
  historySearchQuery: controlledSearchQuery,
  onHistorySearchQueryChange,
  hasAttemptNote,
  getAttemptNote,
  notesStore,
  onSaveAttemptNote,
  noteLastSavedAt,
  onExportNotes,
  onImportNotes,
  onClearAllNotes,
  workspaceTab = "history",
  workspaceFromAttemptId,
  workspaceToAttemptId,
  workspacePreset,
}: AnswerHistoryPanelProps) {
  const importInputRef = useRef<HTMLInputElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [notesImportError, setNotesImportError] = useState<string | null>(null);
  const [notesImportSuccess, setNotesImportSuccess] = useState(false);
  const [uncontrolledSearchQuery, setUncontrolledSearchQuery] = useState("");
  const isControlled = controlledAttempts !== undefined;
  const detailRef = useRef<HTMLDivElement>(null);

  const [uncontrolledAttempts, setUncontrolledAttempts] = useState<AnswerAttemptSummary[]>([]);
  const [uncontrolledLoading, setUncontrolledLoading] = useState(!isControlled);
  const [uncontrolledError, setUncontrolledError] = useState<SourceLabApiError | null>(null);
  const [uncontrolledFilter, setUncontrolledFilter] = useState<HistoryFilter>("all");
  const [uncontrolledDetail, setUncontrolledDetail] = useState<AnswerAttemptDetail | null>(null);
  const [uncontrolledDetailLoading, setUncontrolledDetailLoading] = useState(false);
  const [uncontrolledDetailError, setUncontrolledDetailError] = useState<SourceLabApiError | null>(
    null,
  );

  const attempts = isControlled ? controlledAttempts : uncontrolledAttempts;
  const loading = isControlled ? (controlledLoading ?? false) : uncontrolledLoading;
  const error = isControlled ? (controlledError ?? null) : uncontrolledError;
  const detail = isControlled ? (selectedAttemptDetail ?? null) : uncontrolledDetail;
  const detailLoading = isControlled ? (controlledDetailLoading ?? false) : uncontrolledDetailLoading;
  const detailError = isControlled ? (controlledDetailError ?? null) : uncontrolledDetailError;

  const loadHistory = useCallback(async () => {
    if (isControlled) {
      return;
    }
    setUncontrolledLoading(true);
    setUncontrolledError(null);
    try {
      const history = await getAnswerHistory(runId);
      setUncontrolledAttempts(history.attempts);
    } catch (err: unknown) {
      setUncontrolledError(
        err instanceof SourceLabApiError
          ? err
          : new SourceLabApiError({
              message: err instanceof Error ? err.message : "Failed to load history",
              status: -1,
            }),
      );
    } finally {
      setUncontrolledLoading(false);
    }
  }, [runId, isControlled]);

  useEffect(() => {
    if (!isControlled) {
      void loadHistory();
    }
  }, [loadHistory, refreshKey, isControlled]);

  useEffect(() => {
    if (isControlled) {
      onDetailChange?.(selectedAttemptDetail ?? null);
      return;
    }

    if (!selectedAttemptId) {
      setUncontrolledDetail(null);
      setUncontrolledDetailError(null);
      onDetailChange?.(null);
      return;
    }

    let cancelled = false;
    setUncontrolledDetailLoading(true);
    setUncontrolledDetailError(null);

    getAnswerAttempt(runId, selectedAttemptId)
      .then((result) => {
        if (!cancelled) {
          setUncontrolledDetail(result);
          onDetailChange?.(result);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setUncontrolledDetail(null);
          setUncontrolledDetailError(
            err instanceof SourceLabApiError
              ? err
              : new SourceLabApiError({
                  message: err instanceof Error ? err.message : "Failed to load attempt detail",
                  status: -1,
                }),
          );
          onDetailChange?.(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setUncontrolledDetailLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runId, selectedAttemptId, isControlled, selectedAttemptDetail, onDetailChange]);

  const filter = controlledFilter ?? uncontrolledFilter;
  const setFilter = onHistoryFilterChange ?? setUncontrolledFilter;
  const searchQuery = controlledSearchQuery ?? uncontrolledSearchQuery;
  const setSearchQuery = onHistorySearchQueryChange ?? setUncontrolledSearchQuery;

  const searchContext = useMemo(
    () => ({ getNote: getAttemptNote, hasNote: hasAttemptNote }),
    [getAttemptNote, hasAttemptNote],
  );

  const visibleAttempts = useMemo(
    () => getVisibleHistoryAttempts(attempts, filter, searchQuery, searchContext),
    [attempts, filter, searchQuery, searchContext],
  );
  const reversedVisible = useMemo(() => [...visibleAttempts].reverse(), [visibleAttempts]);

  const timeline =
    controlledSummary ?? computeAttemptTimelineSummary(attempts, selectedAttemptId);

  const totalNoteCount = useMemo(
    () => countAttemptsWithNotes(attempts, hasAttemptNote),
    [attempts, hasAttemptNote],
  );
  const visibleNoteCount = useMemo(
    () => countVisibleNotes(visibleAttempts, hasAttemptNote),
    [visibleAttempts, hasAttemptNote],
  );

  const filters: Array<{ key: HistoryFilter; label: string }> = [
    { key: "all", label: FILTER_LABELS.all },
    { key: "needs_review", label: FILTER_LABELS.needs_review },
    { key: "passed", label: FILTER_LABELS.passed },
    { key: "capped", label: FILTER_LABELS.capped },
    { key: "has_notes", label: FILTER_LABELS.has_notes },
    { key: "no_notes", label: FILTER_LABELS.no_notes },
  ];

  const handleSelect = (attemptId: string) => {
    onSelectAttempt?.(attemptId);
  };

  const handleExportNotes = () => {
    if (!onExportNotes) {
      return;
    }
    const json = onExportNotes();
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `sourcelab_attempt_notes_${runId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleExportVisibleNotes = () => {
    if (!notesStore) {
      return;
    }
    const visibleIds = visibleAttempts.map((a) => a.attempt_id);
    const json = exportFilteredAttemptNotes(notesStore, visibleIds, {
      runId,
      filter,
      query: searchQuery.trim(),
    });
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `sourcelab_attempt_notes_${runId}_filtered.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleImportNotesFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !onImportNotes) {
      return;
    }
    setNotesImportError(null);
    setNotesImportSuccess(false);
    const text = await file.text();
    const result = onImportNotes(text);
    if (result.ok) {
      setNotesImportSuccess(true);
      window.setTimeout(() => setNotesImportSuccess(false), 2500);
    } else {
      setNotesImportError(result.error);
    }
  };

  const handleClearAllNotes = () => {
    if (!onClearAllNotes) {
      return;
    }
    if (
      window.confirm(
        "Clear all local attempt notes for this run? This cannot be undone and does not affect proof artifacts.",
      )
    ) {
      onClearAllNotes();
      setNotesImportError(null);
      setNotesImportSuccess(false);
    }
  };

  const focusDetail = useCallback(() => {
    detailRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    detailRef.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    (window as Window & { __slFocusAttemptDetail?: () => void }).__slFocusAttemptDetail =
      focusDetail;
    return () => {
      delete (window as Window & { __slFocusAttemptDetail?: () => void }).__slFocusAttemptDetail;
    };
  }, [focusDetail]);

  const compareSummaryLabel = workspacePreset
    ? workspacePreset.replace(/_/g, " → ")
    : workspaceFromAttemptId && workspaceToAttemptId
      ? `${workspaceFromAttemptId.replace("attempt_", "")} → ${workspaceToAttemptId.replace("attempt_", "")}`
      : "none";

  if (loading && attempts.length === 0) {
    return <p className="text-xs text-[var(--sl-text-faint)]">Loading attempt history…</p>;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-[rgba(244,63,94,0.32)] bg-[rgba(244,63,94,0.08)] p-3">
        <p className="text-xs text-[var(--sl-text-dim)]">{error.message}</p>
        {onRefreshHistory && (
          <button
            type="button"
            className="sl-btn mt-2 px-2 py-1 text-xs"
            onClick={onRefreshHistory}
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  if (attempts.length === 0) {
    return (
      <p className="text-xs text-[var(--sl-text-faint)]">
        No answer attempts yet. Submit an answer to start the timeline.
      </p>
    );
  }

  return (
    <div className="space-y-3" role="region" aria-label="Answer attempt history">
      {invalidAttemptWarning && (
        <div className="rounded-lg border border-[rgba(251,191,36,0.32)] bg-[rgba(251,191,36,0.08)] px-3 py-2 text-xs text-[var(--sl-amber)]">
          {invalidAttemptWarning}
        </div>
      )}

      <div className="rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.45)] p-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-[0.62rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
              Attempt trajectory
            </div>
            <div className="mt-0.5 text-sm font-medium text-white">
              {timeline.totalAttempts} attempt{timeline.totalAttempts === 1 ? "" : "s"}
            </div>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[0.68rem] text-[var(--sl-text-dim)]">
            <span>
              Latest{" "}
              <span className="font-mono text-white">{formatScore(timeline.latestScore)}</span>
            </span>
            <span>
              Best{" "}
              <span className="font-mono text-[var(--sl-emerald)]">
                {formatScore(timeline.bestScore)}
              </span>
            </span>
            <span>
              First→Latest{" "}
              <span className={`font-mono ${deltaToneClass(timeline.firstToLatestDelta)}`}>
                {formatScoreDelta(timeline.firstToLatestDelta)}
              </span>
            </span>
            {timeline.needsReviewCount > 0 && (
              <span className="text-[var(--sl-amber)]">
                {timeline.needsReviewCount} review
              </span>
            )}
            {timeline.cappedCount > 0 && (
              <span className="text-[var(--sl-amber)]">{timeline.cappedCount} capped</span>
            )}
          </div>
        </div>
        <div className="mt-2">
          <AttemptScoreSparkline
            attempts={attempts}
            selectedAttemptId={selectedAttemptId}
            latestAttemptId={timeline.latestAttemptId}
            bestAttemptId={timeline.bestAttemptId}
            onSelectAttempt={handleSelect}
            focusedAttemptId={
              focusedRowIndex >= 0 && focusedRowIndex < reversedVisible.length
                ? reversedVisible[focusedRowIndex].attempt_id
                : selectedAttemptId
            }
          />
        </div>
      </div>

      <label className="block">
        <span className="sr-only">Search attempts and notes</span>
        <input
          ref={searchInputRef}
          type="search"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Search attempts / notes…"
          className="w-full rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.6)] px-3 py-2 text-xs text-[var(--sl-text)] placeholder:text-[var(--sl-text-faint)]"
        />
      </label>

      <div className="flex flex-wrap gap-1.5">
        {filters.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`sl-btn px-2.5 py-1 text-xs ${
              filter === item.key ? "sl-btn--primary" : ""
            }`}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
          </button>
        ))}
        <span className="ml-auto self-center text-[0.7rem] text-[var(--sl-text-faint)]">
          {visibleAttempts.length} of {attempts.length}
        </span>
      </div>

      {(onExportNotes || onImportNotes || onClearAllNotes) && (
        <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(4,7,16,0.35)] px-3 py-2.5">
          <div className="text-[0.62rem] uppercase tracking-[0.1em] text-[var(--sl-text-faint)]">
            Local annotations (browser-only · not proof artifacts)
          </div>

          <div className="mt-2 rounded-md border border-[var(--sl-border)] bg-[rgba(9,14,28,0.35)] px-2.5 py-2 text-[0.68rem] text-[var(--sl-text-dim)]">
            <div className="text-[0.6rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
              Workspace summary
            </div>
            <div className="mt-1 grid gap-0.5 sm:grid-cols-2">
              <span>
                Tab: <span className="text-white">{workspaceTab}</span>
              </span>
              <span>
                Filter: <span className="text-white">{FILTER_LABELS[filter]}</span>
              </span>
              <span>
                Search:{" "}
                <span className="font-mono text-white">
                  {searchQuery.trim() ? `"${searchQuery.trim()}"` : "(none)"}
                </span>
              </span>
              <span>
                Selected:{" "}
                <span className="font-mono text-white">
                  {selectedAttemptId?.replace("attempt_", "") ?? "—"}
                </span>
              </span>
              <span>
                Compare: <span className="font-mono text-white">{compareSummaryLabel}</span>
              </span>
              <span>
                Notes:{" "}
                <span className="text-white">
                  {visibleNoteCount} visible / {totalNoteCount} total
                </span>
              </span>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {onExportNotes && (
              <button
                type="button"
                className="sl-btn px-2 py-0.5 text-[0.68rem]"
                onClick={handleExportNotes}
              >
                Export all notes
              </button>
            )}
            {notesStore && (
              <button
                type="button"
                className="sl-btn px-2 py-0.5 text-[0.68rem]"
                onClick={handleExportVisibleNotes}
                disabled={visibleNoteCount === 0}
                title={
                  visibleNoteCount === 0
                    ? "No notes among visible attempts"
                    : "Export notes for attempts matching current filter/search"
                }
              >
                Export visible notes
              </button>
            )}
            {onImportNotes && (
              <>
                <button
                  type="button"
                  className="sl-btn px-2 py-0.5 text-[0.68rem]"
                  onClick={() => importInputRef.current?.click()}
                >
                  Import notes JSON
                </button>
                <input
                  ref={importInputRef}
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={(event) => void handleImportNotesFile(event)}
                />
              </>
            )}
            {onClearAllNotes && (
              <button
                type="button"
                className="sl-btn px-2 py-0.5 text-[0.68rem]"
                onClick={handleClearAllNotes}
              >
                Clear local notes
              </button>
            )}
            <CopyWorkspaceLinkButton
              runId={runId}
              attemptId={selectedAttemptId}
              fromAttemptId={workspaceFromAttemptId}
              toAttemptId={workspaceToAttemptId}
              tab={workspaceTab}
              filter={filter}
              query={searchQuery}
              preset={workspacePreset}
            />
          </div>
          {notesImportSuccess && (
            <p className="mt-2 text-[0.68rem] text-[var(--sl-emerald)]">Notes imported and merged.</p>
          )}
          {notesImportError && (
            <p className="mt-2 text-[0.68rem] text-[var(--sl-rose)]">{notesImportError}</p>
          )}
        </div>
      )}

      <div
        className="space-y-1.5"
        role="listbox"
        aria-label="Attempt list"
        aria-activedescendant={
          selectedAttemptId ? `attempt-row-${selectedAttemptId}` : undefined
        }
      >
        {reversedVisible.length === 0 ? (
          <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.35)] px-3 py-4 text-center">
            <p className="text-xs text-[var(--sl-text-faint)]">
              {searchQuery.trim()
                ? "No attempts match your search and filter."
                : "No attempts match the current filter."}
            </p>
            {(searchQuery.trim() || filter !== "all") && (
              <button
                type="button"
                className="sl-btn mt-2 px-2 py-1 text-xs"
                onClick={() => {
                  setSearchQuery("");
                  setFilter("all");
                }}
              >
                Clear search & filter
              </button>
            )}
          </div>
        ) : (
          reversedVisible.map((attempt, rowIndex) => {
            const selected = selectedAttemptId === attempt.attempt_id;
            const focused = focusedRowIndex === rowIndex;
            return (
              <button
                key={attempt.attempt_id}
                id={`attempt-row-${attempt.attempt_id}`}
                type="button"
                role="option"
                aria-selected={selected}
                tabIndex={focused || (focusedRowIndex < 0 && selected) ? 0 : -1}
                onClick={() => handleSelect(attempt.attempt_id)}
                onFocus={() => onFocusedRowIndexChange?.(rowIndex)}
                className={`w-full rounded-lg border px-3 py-2.5 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[rgba(168,85,247,0.65)] focus-visible:ring-offset-1 focus-visible:ring-offset-[rgba(4,7,16,0.9)] ${
                  selected
                    ? "border-[rgba(34,211,238,0.45)] bg-[rgba(34,211,238,0.08)]"
                    : "border-[var(--sl-border)] bg-[rgba(9,14,28,0.4)] hover:border-[rgba(34,211,238,0.25)]"
                } ${focused && !selected ? "border-[rgba(168,85,247,0.35)]" : ""}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-[0.72rem] text-[var(--sl-text)]">
                    {attempt.attempt_id.replace("attempt_", "")}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {hasAttemptNote?.(attempt.attempt_id) && (
                      <span
                        className="text-[0.62rem] text-[var(--sl-violet)]"
                        title="Private local note"
                        aria-label="Has private note"
                      >
                        ✎
                      </span>
                    )}
                    <span className="font-mono text-sm font-semibold sl-gradient-text">
                      {formatScore(attempt.overall_score)}
                    </span>
                    {attempt.needs_review ? (
                      <StatusPill tone="review" label="REVIEW" />
                    ) : (
                      <StatusPill tone="pass" label="CLEAR" />
                    )}
                  </div>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[0.68rem] text-[var(--sl-text-faint)]">
                  <span>uncapped {formatScore(attempt.uncapped_score)}</span>
                  <span>rubric {formatScore(attempt.rubric_alignment_score)}</span>
                  {attempt.cap_reason && (
                    <span className="text-[var(--sl-amber)]">capped</span>
                  )}
                </div>
                {attempt.next_task_focus && (
                  <p className="mt-1 truncate text-[0.68rem] text-[var(--sl-text-dim)]">
                    Next: {attempt.next_task_focus}
                  </p>
                )}
              </button>
            );
          })
        )}
      </div>

      {selectedAttemptId && detailLoading && (
        <p className="text-xs text-[var(--sl-text-faint)]">Loading attempt detail…</p>
      )}

      {detailError && (
        <div className="rounded-lg border border-[rgba(244,63,94,0.32)] bg-[rgba(244,63,94,0.08)] p-3">
          <p className="text-xs text-[var(--sl-text-dim)]">{detailError.message}</p>
        </div>
      )}

      {detail && !detailLoading && (
        <div
          ref={detailRef}
          tabIndex={-1}
          className="outline-none focus-visible:ring-2 focus-visible:ring-[rgba(34,211,238,0.5)] rounded-xl"
        >
          <div className="mb-2 flex flex-wrap items-center justify-end gap-2">
            <CopyAttemptLinkButton runId={runId} attemptId={detail.attempt_id} />
            {onClearSelection && (
              <button
                type="button"
                className="sl-btn px-2 py-0.5 text-[0.68rem]"
                onClick={onClearSelection}
              >
                Back to latest snapshot
              </button>
            )}
          </div>
          <AttemptDetailPanel
            detail={detail}
            runId={runId}
            note={getAttemptNote?.(detail.attempt_id) ?? ""}
            onSaveNote={(note) => onSaveAttemptNote?.(detail.attempt_id, note)}
            noteLastSavedAt={noteLastSavedAt}
          />
        </div>
      )}
    </div>
  );
}
