"use client";

import { useMemo, useState } from "react";

import type { ArtifactRow } from "@/lib/types";
import { formatBytes, shortHash } from "@/lib/format";

interface ArtifactMatrixProps {
  artifacts: ArtifactRow[];
}

type ArtifactFilter = "all" | "required" | "missing" | "failed";

const FILTERS: Array<{ key: ArtifactFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: "required", label: "Required only" },
  { key: "missing", label: "Missing only" },
  { key: "failed", label: "Failed validation" },
];

function Flag({ ok, trueLabel, falseLabel }: { ok: boolean; trueLabel: string; falseLabel: string }) {
  return (
    <span className={`sl-pill ${ok ? "sl-pill--pass" : "sl-pill--missing"}`} >
      {ok ? trueLabel : falseLabel}
    </span>
  );
}

export default function ArtifactMatrix({ artifacts }: ArtifactMatrixProps) {
  const [filter, setFilter] = useState<ArtifactFilter>("all");

  const filtered = useMemo(() => {
    switch (filter) {
      case "required":
        return artifacts.filter((a) => a.required);
      case "missing":
        return artifacts.filter((a) => !a.exists);
      case "failed":
        return artifacts.filter((a) => a.required && a.exists && !a.validated);
      default:
        return artifacts;
    }
  }, [artifacts, filter]);

  if (!artifacts.length) {
    return <p className="text-sm text-[var(--sl-text-faint)]">No artifacts recorded for this run.</p>;
  }

  const missing = artifacts.filter((a) => !a.exists).length;
  const failed = artifacts.filter((a) => a.required && a.exists && !a.validated).length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-[var(--sl-text-dim)]">
          {artifacts.length} artifacts · {missing} missing · {failed} failed
        </span>
        <div className="ml-auto flex flex-wrap gap-1">
          {FILTERS.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => setFilter(option.key)}
              className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
                filter === option.key
                  ? "bg-[rgba(34,211,238,0.14)] text-white"
                  : "text-[var(--sl-text-dim)] hover:text-white"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="max-h-[420px] overflow-auto rounded-xl border border-[var(--sl-border)]">
        <table className="sl-table">
          <thead>
            <tr>
              <th>Artifact</th>
              <th>Required</th>
              <th>Exists</th>
              <th>Validated</th>
              <th>sha256</th>
              <th className="text-right">Size</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((artifact) => (
              <tr key={artifact.name}>
                <td className="font-mono text-xs text-[var(--sl-text)]">{artifact.name}</td>
                <td>
                  <Flag ok={artifact.required} trueLabel="REQ" falseLabel="opt" />
                </td>
                <td>
                  <Flag ok={artifact.exists} trueLabel="yes" falseLabel="MISSING" />
                </td>
                <td>
                  <Flag ok={artifact.validated} trueLabel="valid" falseLabel="—" />
                </td>
                <td className="font-mono text-[0.68rem] text-[var(--sl-text-faint)]">
                  {shortHash(artifact.sha256)}
                </td>
                <td className="text-right font-mono text-xs text-[var(--sl-text-dim)]">
                  {artifact.exists ? formatBytes(artifact.size) : "—"}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center text-sm text-[var(--sl-text-faint)]">
                  No artifacts match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
