"use client";

import { useEffect, useState } from "react";

import { timeAgo } from "@/lib/format";
import StatusPill from "@/components/StatusPill";

interface RunRefreshBarProps {
  lastUpdated: Date | null;
  refreshing: boolean;
  autoRefresh: boolean;
  intervalMs: number;
  /** True when the most recent refresh failed (cached data may still show). */
  offline: boolean;
  onToggleAuto: (on: boolean) => void;
  onRefresh: () => void;
}

/**
 * Run Studio live-update control strip: connection status, last-updated time,
 * a manual refresh button, and an auto-refresh toggle. Polling only — no
 * WebSockets. When `offline` is true the page keeps cached data on screen and
 * this bar surfaces the disconnect.
 */
export default function RunRefreshBar({
  lastUpdated,
  refreshing,
  autoRefresh,
  intervalMs,
  offline,
  onToggleAuto,
  onRefresh,
}: RunRefreshBarProps) {
  // Re-render the relative timestamp every second without re-fetching.
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const intervalSeconds = Math.round(intervalMs / 1000);

  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-[var(--sl-border)] bg-[rgba(8,12,24,0.55)] px-3.5 py-2.5">
      {offline ? (
        <StatusPill tone="blocked" label="API OFFLINE" title="The last refresh failed" />
      ) : (
        <StatusPill tone="pass" label="LIVE" title="Connected to the SourceLab API" />
      )}

      <span className="text-[0.72rem] text-[var(--sl-text-faint)]">
        {lastUpdated ? (
          <>
            Updated <span className="text-[var(--sl-text-dim)]">{timeAgo(lastUpdated.toISOString())}</span>
          </>
        ) : (
          "Not yet updated"
        )}
        {refreshing && <span className="ml-2 text-[var(--sl-cyan)]">· refreshing…</span>}
      </span>

      {offline && (
        <span className="text-[0.72rem] text-[var(--sl-amber)]">
          Showing cached data — auto-refresh paused.
        </span>
      )}

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onToggleAuto(!autoRefresh)}
          aria-pressed={autoRefresh}
          className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs transition-colors ${
            autoRefresh
              ? "border-[rgba(34,211,238,0.45)] bg-[rgba(34,211,238,0.14)] text-white"
              : "border-[var(--sl-border-strong)] text-[var(--sl-text-dim)] hover:text-white"
          }`}
        >
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${
              autoRefresh ? "bg-[var(--sl-cyan)]" : "bg-[var(--sl-text-faint)]"
            }`}
            aria-hidden
          />
          Auto-refresh {autoRefresh ? `on · ${intervalSeconds}s` : "off"}
        </button>

        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="sl-btn px-3 py-1.5 text-xs"
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>
    </div>
  );
}
