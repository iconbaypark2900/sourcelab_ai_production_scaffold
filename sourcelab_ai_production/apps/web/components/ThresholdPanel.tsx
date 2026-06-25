"use client";

import {
  complianceLabel,
  complianceTone,
  failingChecks,
  formatThresholdCheckValue,
  passingChecks,
  thresholdSummary,
} from "@/lib/eval-thresholds";
import { formatScore } from "@/lib/format";
import type { PackThresholdResponse } from "@/lib/types";
import { Panel } from "@/components/Chrome";
import StatusPill, { type PillTone } from "@/components/StatusPill";

interface ThresholdPanelProps {
  response: PackThresholdResponse | null;
  compact?: boolean;
}

function toneToPillTone(tone: string): PillTone {
  if (tone === "pass") return "pass";
  if (tone === "review") return "review";
  if (tone === "blocked") return "blocked";
  return "missing";
}

export default function ThresholdPanel({ response, compact }: ThresholdPanelProps) {
  if (!response) {
    return (
      <Panel title="Eval thresholds">
        <p className="text-sm text-[var(--sl-text-faint)]">
          Threshold information unavailable for this pack.
        </p>
      </Panel>
    );
  }

  const tone = complianceTone(response);
  const passing = passingChecks(response);
  const failing = failingChecks(response);
  const thresholds = response.thresholds;
  const required = thresholds.required_evals;

  if (compact) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] px-3 py-2">
        <div className="flex items-center gap-2">
          <StatusPill
            tone={toneToPillTone(tone)}
            dot={false}
            label={complianceLabel(response)}
          />
          <span className="text-xs text-[var(--sl-text-dim)]">
            {thresholdSummary(response)}
          </span>
        </div>
        {response.overall_pass_rate !== null && (
          <span className="font-mono text-xs text-[var(--sl-cyan)]">
            {formatScore(response.overall_pass_rate)}
          </span>
        )}
      </div>
    );
  }

  return (
    <Panel
      title="Eval thresholds"
      hint={thresholdSummary(response)}
      glow={tone === "pass" ? "cyan" : tone === "blocked" ? "violet" : undefined}
    >
      <div className="mb-3 flex items-center justify-between">
        <StatusPill
          tone={toneToPillTone(tone)}
          label={complianceLabel(response)}
        />
        {response.overall_pass_rate !== null && (
          <span className="text-2xl font-semibold text-white">
            {formatScore(response.overall_pass_rate)}
          </span>
        )}
      </div>

      <ul className="space-y-1.5 text-sm">
        {passing.map((check) => (
          <li
            key={check.name}
            className="flex items-center justify-between gap-2 rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] px-3 py-1.5"
          >
            <div className="flex items-center gap-2">
              <StatusPill tone="pass" dot={false} label="PASS" />
              <span className="text-[var(--sl-text-dim)]">{check.name}</span>
            </div>
            <span className="font-mono text-xs text-[var(--sl-text-faint)]">
              {formatThresholdCheckValue(check.actual)}/
              {formatThresholdCheckValue(check.required)}
            </span>
          </li>
        ))}
        {failing.map((check) => (
          <li
            key={check.name}
            className="flex items-center justify-between gap-2 rounded-lg border border-[var(--sl-rose)] bg-[rgba(244,63,94,0.08)] px-3 py-1.5"
          >
            <div className="flex items-center gap-2">
              <StatusPill tone="blocked" dot={false} label="FAIL" />
              <span className="text-[var(--sl-text-dim)]">{check.name}</span>
            </div>
            <span
              className="font-mono text-xs text-[var(--sl-rose)]"
              title={check.message}
            >
              {formatThresholdCheckValue(check.actual)}/
              {formatThresholdCheckValue(check.required)}
            </span>
          </li>
        ))}
      </ul>

      {required.length > 0 && (
        <p className="mt-3 text-xs text-[var(--sl-text-faint)]">
          Required evals: {required.join(", ")}
        </p>
      )}
    </Panel>
  );
}
