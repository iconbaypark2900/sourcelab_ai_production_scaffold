"use client";

import Link from "next/link";

import StatusPill from "@/components/StatusPill";
import { formatScore } from "@/lib/format";
import type { CollectionCardModel } from "@/lib/library-theme";

interface LibraryCollectionCardProps {
  collection: CollectionCardModel;
  compact?: boolean;
}

export default function LibraryCollectionCard({ collection, compact = false }: LibraryCollectionCardProps) {
  const { pack, status, passRate, domain, topics, badgeLabel, badgeTone, readyToStudy } = collection;
  const sourceLabel = status
    ? `${status.installed_count}/${status.total_sources} sources`
    : `${pack.source_count} sources`;

  return (
    <article
      className={`sl-library-card flex flex-col ${compact ? "p-3" : "p-4"} ${readyToStudy ? "sl-library-card--ready" : ""}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-white" title={pack.title || pack.pack_name}>
            {pack.title || pack.pack_name}
          </h3>
          <p className="mt-0.5 font-mono text-[0.68rem] text-[var(--sl-parchment-dim)]">
            {pack.pack_name} · v{pack.version}
          </p>
        </div>
        <StatusPill tone={badgeTone} label={badgeLabel} dot={false} />
      </div>

      {!compact && pack.description && (
        <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-[var(--sl-text-dim)]">
          {pack.description}
        </p>
      )}

      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="sl-library-tag">{domain}</span>
        {topics.slice(0, compact ? 2 : 3).map((topic) => (
          <span key={topic} className="sl-library-tag sl-library-tag--muted">
            {topic}
          </span>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="sl-library-stat">
          <div className="sl-library-stat__value">{sourceLabel}</div>
          <div className="sl-library-stat__label">Sources</div>
        </div>
        <div className="sl-library-stat">
          <div className="sl-library-stat__value">{pack.eval_count}</div>
          <div className="sl-library-stat__label">Evals</div>
        </div>
        <div className="sl-library-stat">
          <div className="sl-library-stat__value">{formatScore(passRate)}</div>
          <div className="sl-library-stat__label">Pass rate</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 border-t border-[var(--sl-border)] pt-3">
        <Link href="/source-packs" className="sl-btn flex-1 justify-center text-xs">
          Browse shelf
        </Link>
        {readyToStudy && (
          <Link
            href={`/runs/new?pack=${encodeURIComponent(pack.pack_name)}`}
            className="sl-btn sl-btn--primary flex-1 justify-center text-xs"
          >
            Start lesson
          </Link>
        )}
      </div>
    </article>
  );
}
