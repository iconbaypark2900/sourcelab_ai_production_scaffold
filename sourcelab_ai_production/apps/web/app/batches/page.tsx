"use client";

import Link from "next/link";

import BatchRunList from "@/components/BatchRunList";
import {
  ConnectionCard,
  LoadingPanel,
  PageHeader,
  PageShell,
} from "@/components/Chrome";
import { STUDY_SET_TERMS } from "@/lib/library-theme";
import { listBatches } from "@/lib/sourcelab-api";
import { useApi } from "@/lib/use-api";

export default function BatchesPage() {
  const { data, error, loading, reload } = useApi(() => listBatches(), []);

  return (
    <PageShell>
      <PageHeader
        title={STUDY_SET_TERMS.batches}
        subtitle="Filesystem-backed study sets under artifacts/batches/."
      >
        <Link href="/batches/new" className="sl-btn sl-btn--primary">
          {STUDY_SET_TERMS.newBatch}
        </Link>
        {data && (
          <span className="sl-pill sl-pill--neutral">
            <span className="sl-pill__dot" /> {data.total} study sets
          </span>
        )}
      </PageHeader>

      {loading && <LoadingPanel label={`Loading ${STUDY_SET_TERMS.batches.toLowerCase()}…`} />}
      {error && <ConnectionCard error={error} onRetry={reload} />}
      {data && <BatchRunList batches={data.batches} />}
    </PageShell>
  );
}
