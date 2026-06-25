"use client";

import Link from "next/link";

import StatusPill from "@/components/StatusPill";
import { Panel } from "@/components/Chrome";
import type { BatchListItem } from "@/lib/types";
import { timeAgo } from "@/lib/format";

interface BatchRunListProps {
  batches: BatchListItem[];
}

export default function BatchRunList({ batches }: BatchRunListProps) {
  if (batches.length === 0) {
    return (
      <p className="text-sm text-[var(--sl-text-faint)]">
        No batches yet. Create one from{" "}
        <Link href="/batches/new" className="text-[var(--sl-cyan)] hover:underline">
          New batch
        </Link>
        .
      </p>
    );
  }

  return (
    <Panel>
      <div className="overflow-auto">
        <table className="sl-table">
          <thead>
            <tr>
              <th>Batch ID</th>
              <th>Name</th>
              <th>Status</th>
              <th>Runs</th>
              <th>Topics</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {[...batches].reverse().map((batch) => (
              <tr key={batch.batch_id}>
                <td>
                  <Link
                    href={`/batches/${batch.batch_id}`}
                    className="font-mono text-xs text-[var(--sl-cyan)] hover:underline"
                  >
                    {batch.batch_id}
                  </Link>
                </td>
                <td className="max-w-[220px] truncate">{batch.batch_name}</td>
                <td>
                  <StatusPill
                    tone={batch.status === "complete" ? "pass" : batch.status === "partial" ? "review" : "blocked"}
                    label={batch.status.toUpperCase()}
                    dot={false}
                  />
                </td>
                <td>
                  {batch.run_count}
                  {batch.failure_count > 0 && (
                    <span className="ml-1 text-[var(--sl-rose)]">({batch.failure_count} failed)</span>
                  )}
                </td>
                <td className="max-w-[200px] truncate text-xs text-[var(--sl-text-dim)]">
                  {batch.topics.join("; ")}
                </td>
                <td className="text-xs text-[var(--sl-text-dim)]">{timeAgo(batch.created_at)}</td>
                <td>
                  <Link href={`/batches/${batch.batch_id}`} className="sl-btn text-xs">
                    Open
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
