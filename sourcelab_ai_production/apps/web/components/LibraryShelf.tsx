"use client";

import LibraryCollectionCard from "@/components/LibraryCollectionCard";
import type { CollectionCardModel, LibraryShelfDefinition } from "@/lib/library-theme";

interface LibraryShelfProps {
  shelf: LibraryShelfDefinition;
  collections: CollectionCardModel[];
  compact?: boolean;
}

export default function LibraryShelf({ shelf, collections, compact = false }: LibraryShelfProps) {
  if (collections.length === 0) {
    return null;
  }

  return (
    <section className="sl-library-shelf sl-fade-up">
      <header className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-white">{shelf.label}</h2>
          <p className="mt-0.5 max-w-2xl text-xs text-[var(--sl-text-dim)]">{shelf.description}</p>
        </div>
        <span className="sl-library-tag">
          {collections.length} collection{collections.length === 1 ? "" : "s"}
        </span>
      </header>
      <div
        className={`grid gap-3 ${compact ? "sm:grid-cols-2 lg:grid-cols-3" : "md:grid-cols-2 xl:grid-cols-3"}`}
      >
        {collections.map((collection) => (
          <LibraryCollectionCard key={collection.pack.pack_name} collection={collection} compact={compact} />
        ))}
      </div>
    </section>
  );
}
