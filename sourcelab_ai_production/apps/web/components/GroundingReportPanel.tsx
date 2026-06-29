import type {
  ClaimVerificationResult,
  SourceGroundingReview,
  VerificationReport,
} from "@/lib/types";
import { formatScore } from "@/lib/format";
import StatusPill from "@/components/StatusPill";
import SourceChip from "@/components/SourceChip";

interface GroundingReportPanelProps {
  verification: VerificationReport | null;
  grounding?: SourceGroundingReview | null;
}

function supportTone(status: string): "pass" | "review" | "blocked" | "missing" {
  if (status === "supported") return "pass";
  if (status === "uncertain") return "review";
  if (status === "unsupported" || status === "conflicting") return "blocked";
  return "missing";
}

function severityTone(severity: string): "pass" | "review" | "blocked" {
  if (severity === "high") return "blocked";
  if (severity === "medium") return "review";
  return "pass";
}

export default function GroundingReportPanel({
  verification,
  grounding,
}: GroundingReportPanelProps) {
  if (!verification) {
    return (
      <p className="text-sm text-[var(--sl-text-faint)]">
        No verification report available for this run.
      </p>
    );
  }

  const { summary, claims, citation_resolution } = verification;
  const unmatched = claims.filter(
    (c) => c.support_status === "unsupported" || c.support_status === "uncertain",
  );
  const llmEntailed = claims.filter((c) => (c as any).llm_entailment_used);

  return (
    <div className="space-y-4">
      {/* Summary metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard
          label="Support rate"
          value={formatScore(summary.support_rate)}
          tone={summary.support_rate >= 0.8 ? "good" : summary.support_rate >= 0.5 ? "warn" : "bad"}
        />
        <MetricCard
          label="Citation resolution"
          value={formatScore(summary.citation_resolution_rate)}
          tone={
            summary.citation_resolution_rate >= 0.8
              ? "good"
              : summary.citation_resolution_rate >= 0.5
                ? "warn"
                : "bad"
          }
        />
        <MetricCard
          label="Total claims"
          value={String(summary.total_claims)}
          tone="default"
        />
        <MetricCard
          label="High-risk unsupported"
          value={String(summary.high_risk_unsupported)}
          tone={summary.high_risk_unsupported === 0 ? "good" : "bad"}
        />
      </div>

      {/* Release gate status */}
      <div className="flex items-center gap-3 rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] px-4 py-3">
        <span className="text-xs uppercase tracking-wider text-[var(--sl-text-faint)]">
          Release gate
        </span>
        <StatusPill
          tone={
            summary.release_gate_status === "PASS"
              ? "pass"
              : summary.release_gate_status === "FAIL"
                ? "blocked"
                : "review"
          }
          label={summary.release_gate_status}
        />
        {verification.blocking_reasons && verification.blocking_reasons.length > 0 && (
          <div className="ml-auto flex flex-wrap gap-2">
            {verification.blocking_reasons.map((reason, i) => (
              <span
                key={i}
                className="rounded-md bg-[rgba(244,63,94,0.12)] px-2 py-0.5 text-xs text-[var(--sl-rose)]"
              >
                {reason}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Claim support matrix */}
      {claims.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--sl-text-dim)]">
            Claim support matrix
          </p>
          <div className="overflow-hidden rounded-xl border border-[var(--sl-border)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[rgba(9,14,28,0.6)] text-left text-xs text-[var(--sl-text-faint)]">
                  <th className="px-3 py-2 font-medium">Claim</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Severity</th>
                  <th className="px-3 py-2 font-medium">Score</th>
                  {llmEntailed.length > 0 && (
                    <th className="px-3 py-2 font-medium">LLM</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {claims.map((claim, i) => (
                  <tr
                    key={claim.claim_id}
                    className={
                      i % 2 === 0
                        ? "border-t border-[var(--sl-border)]"
                        : "border-t border-[var(--sl-border)] bg-[rgba(9,14,28,0.25)]"
                    }
                  >
                    <td className="max-w-xs truncate px-3 py-2 text-[var(--sl-text)]">
                      {claim.claim_text}
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--sl-text-dim)]">
                      {claim.claim_type.replace(/_/g, " ")}
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill
                        tone={supportTone(claim.support_status)}
                        label={claim.support_status}
                        dot={false}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill
                        tone={severityTone(claim.severity)}
                        label={claim.severity}
                        dot={false}
                      />
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-white">
                      {formatScore(claim.best_match_score)}
                    </td>
                    {llmEntailed.length > 0 && (
                      <td className="px-3 py-2">
                        {(claim as any).llm_entailment_used ? (
                          <div className="flex flex-col gap-0.5">
                            <StatusPill
                              tone={supportTone((claim as any).llm_entailment_label || "neutral")}
                              label={(claim as any).llm_entailment_label || "—"}
                              dot={false}
                            />
                            {(claim as any).blended_score != null && (
                              <span className="font-mono text-[0.62rem] text-[var(--sl-text-dim)]">
                                blend {formatScore((claim as any).blended_score)}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-[var(--sl-text-faint)]">—</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Unmatched claims */}
      {unmatched.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--sl-text-dim)]">
            Unmatched claims ({unmatched.length})
          </p>
          <div className="space-y-2">
            {unmatched.slice(0, 10).map((claim) => (
              <div
                key={claim.claim_id}
                className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.4)] px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-[var(--sl-text)]">{claim.claim_text}</span>
                  <StatusPill
                    tone={supportTone(claim.support_status)}
                    label={claim.support_status}
                    dot={false}
                  />
                </div>
                {claim.review_reason && (
                  <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{claim.review_reason}</p>
                )}
              </div>
            ))}
            {unmatched.length > 10 && (
              <p className="text-xs text-[var(--sl-text-faint)]">
                + {unmatched.length - 10} more unmatched claims
              </p>
            )}
          </div>
        </div>
      )}

      {/* Source grounding review */}
      {grounding && (
        <div className="rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] p-3">
          <div className="flex items-center justify-between">
            <span className="sl-panel-title">Source grounding review</span>
            <span className="font-mono text-xs text-[var(--sl-cyan)]">
              {formatScore(grounding.source_grounding_score, 2)}
            </span>
          </div>
          <p className="mt-1 text-[0.72rem] text-[var(--sl-text-dim)]">
            {grounding.matched_source_concepts}/{grounding.total_source_concepts} source concepts matched
          </p>
          {grounding.matched_source_ids.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {grounding.matched_source_ids.map((source) => (
                <SourceChip key={source} sourceId={source} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Human review items */}
      {verification.human_review_items && verification.human_review_items.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--sl-text-dim)]">
            Human review queue ({verification.human_review_items.length})
          </p>
          <div className="space-y-2">
            {verification.human_review_items.slice(0, 5).map((item) => (
              <div
                key={item.item_id}
                className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.4)] px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-[var(--sl-text)]">{item.claim_text}</span>
                  <StatusPill
                    tone={item.priority === "high" ? "blocked" : item.priority === "medium" ? "review" : "pass"}
                    label={item.priority}
                    dot={false}
                  />
                </div>
                <p className="mt-1 text-xs text-[var(--sl-text-dim)]">{item.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "good" | "warn" | "bad" | "default";
}) {
  const toneClass: Record<string, string> = {
    good: "text-[var(--sl-emerald)]",
    warn: "text-[var(--sl-amber)]",
    bad: "text-[var(--sl-rose)]",
    default: "text-white",
  };
  return (
    <div className="rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-3.5 py-3">
      <div className="text-[0.66rem] uppercase tracking-[0.12em] text-[var(--sl-text-faint)]">
        {label}
      </div>
      <div className={`mt-1 text-xl font-semibold ${toneClass[tone]}`}>{value}</div>
    </div>
  );
}
