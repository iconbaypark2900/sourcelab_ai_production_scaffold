"use client";

import {
  formatDelta,
  trendArrow,
  trendLabel,
  type TrendDirection,
} from "@/lib/evals-history";
import StatusPill, { type PillTone } from "@/components/StatusPill";

interface TrendBadgeProps {
  direction: TrendDirection;
  delta: number | null;
  deltaPercent: number | null;
}

function trendTone(direction: TrendDirection): PillTone {
  switch (direction) {
    case "up":
      return "pass";
    case "down":
      return "blocked";
    case "flat":
      return "info";
    default:
      return "missing";
  }
}

export default function TrendBadge({
  direction,
  delta,
  deltaPercent,
}: TrendBadgeProps) {
  const label = `${trendArrow(direction)} ${trendLabel(direction)} ${formatDelta(delta)}`;
  const hint =
    deltaPercent !== null && deltaPercent !== undefined
      ? `Δ ${deltaPercent > 0 ? "+" : ""}${deltaPercent.toFixed(1)}% vs previous`
      : undefined;
  return (
    <StatusPill tone={trendTone(direction)} label={label} title={hint} dot={false} />
  );
}
