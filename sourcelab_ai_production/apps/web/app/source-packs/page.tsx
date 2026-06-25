"use client";

import Link from "next/link";

import LibraryCollectionCard from "@/components/LibraryCollectionCard";
import {
  getLatestEvals,
  getSourcePackStatus,
  getSourcePacks,
  validateSourcePack,
} from "@/lib/sourcelab-api";
import { useApi } from "@/lib/use-api";
import {
  buildCollectionCardModel,
  COLLECTION_SECTION_LABELS,
  groupCollectionsBySection,
  isTemplatePack,
  LIBRARY_EMPTY_STATES,
  LIBRARY_TERMS,
  type CollectionSection,
} from "@/lib/library-theme";
import {
  ConnectionCard,
  EmptyState,
  LoadingPanel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";

async function settle<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

const SECTION_ORDER: CollectionSection[] = [
  "strict_release",
  "validated",
  "starter",
  "collection_health",
];

export default function SourcePacksPage() {
  const { data, error, loading, reload } = useApi(async () => {
    const packsRes = await getSourcePacks();
    const collections = await Promise.all(
      packsRes.packs.map(async (pack) => {
        const [status, evals, validation] = await Promise.all([
          settle(getSourcePackStatus(pack.pack_name)),
          settle(getLatestEvals(pack.pack_name)),
          settle(validateSourcePack(pack.pack_name)),
        ]);
        return buildCollectionCardModel(
          pack,
          status,
          validation,
          evals?.summary?.overall_pass_rate ?? null,
        );
      }),
    );
    return { collections, total: packsRes.total };
  }, []);

  const sections = data ? groupCollectionsBySection(data.collections) : null;
  const readyCount =
    data?.collections.filter((c) => c.readyToStudy && !isTemplatePack(c.pack.pack_name)).length ??
    0;

  return (
    <PageShell>
      <PageHeader
        title={LIBRARY_TERMS.collections}
        subtitle="Curated source collections on the library shelves. pqc_v1 is required for strict release."
      >
        {data && (
          <span className="sl-pill sl-pill--neutral">
            <span className="sl-pill__dot" /> {readyCount} ready-to-study
          </span>
        )}
        <Link href="/runs/new" className="sl-btn sl-btn--primary">
          Start study session
        </Link>
      </PageHeader>

      {loading && <LoadingPanel label="Cataloging collections…" />}
      {error && <ConnectionCard error={error} onRetry={reload} />}

      {data && data.collections.length === 0 && (
        <EmptyState
          title={LIBRARY_EMPTY_STATES.noCollections.title}
          message={LIBRARY_EMPTY_STATES.noCollections.message}
        />
      )}

      {sections && (
        <div className="space-y-8">
          {SECTION_ORDER.map((sectionKey) => {
            const items = sections[sectionKey].filter(
              (c) => sectionKey !== "collection_health" || !isTemplatePack(c.pack.pack_name),
            );
            if (items.length === 0) {
              return null;
            }
            return (
              <section key={sectionKey}>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-[0.12em] text-[var(--sl-parchment-dim)]">
                  {COLLECTION_SECTION_LABELS[sectionKey]}
                </h2>
                <div className="grid gap-4 lg:grid-cols-2">
                  {items.map((collection) => (
                    <LibraryCollectionCard key={collection.pack.pack_name} collection={collection} />
                  ))}
                </div>
              </section>
            );
          })}

          {sections.collection_health.some((c) => isTemplatePack(c.pack.pack_name)) && (
            <section>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-[0.12em] text-[var(--sl-text-faint)]">
                Scaffolding (hidden from study views)
              </h2>
              <div className="grid gap-4 lg:grid-cols-2">
                {sections.collection_health
                  .filter((c) => isTemplatePack(c.pack.pack_name))
                  .map((collection) => (
                    <LibraryCollectionCard key={collection.pack.pack_name} collection={collection} />
                  ))}
              </div>
            </section>
          )}
        </div>
      )}

      <p className="mt-6 text-xs text-[var(--sl-text-faint)]">
        Collection health:{" "}
        <code className="text-[var(--sl-cyan)]">sourcelab source-pack doctor &lt;pack&gt;</code>
      </p>
    </PageShell>
  );
}
