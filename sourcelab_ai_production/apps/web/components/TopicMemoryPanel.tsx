"use client";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import type {
  GapClosureOrchestrationArtifact,
  ResearchPlanArtifact,
  TopicProfileUpdateArtifact,
} from "@/lib/types";

interface TopicMemoryPanelProps {
  researchPlan: ResearchPlanArtifact | null;
  topicProfileUpdate: TopicProfileUpdateArtifact | null;
  gapClosureOrchestration?: GapClosureOrchestrationArtifact | null;
}

export default function TopicMemoryPanel({
  researchPlan,
  topicProfileUpdate,
  gapClosureOrchestration,
}: TopicMemoryPanelProps) {
  if (!researchPlan?.profile_context_used && !topicProfileUpdate && !gapClosureOrchestration) {
    return null;
  }

  const orchestrationRuns = gapClosureOrchestration?.run_id
    ? [gapClosureOrchestration.run_id]
    : [];
  const followupChain = [
    ...(gapClosureOrchestration?.run_id ? [gapClosureOrchestration.run_id] : []),
    ...(gapClosureOrchestration?.followup_run_id ? [gapClosureOrchestration.followup_run_id] : []),
  ];

  return (
    <Panel title="Topic memory" hint="Adaptive profile influencing this run" glow="violet" id="research-topic-memory-panel">
      {researchPlan?.profile_context_used && (
        <div className="mb-3">
          <StatusPill tone="info" label="profile context active" dot={false} />
        </div>
      )}

      <div className="grid gap-2 sm:grid-cols-2 text-xs text-[var(--sl-text-dim)]">
        {topicProfileUpdate && (
          <>
            <div>
              Slug: <span className="font-mono text-white">{topicProfileUpdate.topic_slug}</span>
            </div>
            <div>
              Pack: <span className="font-mono text-white">{topicProfileUpdate.source_pack}</span>
            </div>
            <div>
              Coverage:{" "}
              <span className="font-mono text-white">
                {topicProfileUpdate.coverage_score?.toFixed(2) ?? "—"}
              </span>
            </div>
            <div>
              Genericness:{" "}
              <span className="font-mono text-white">{topicProfileUpdate.genericness_verdict ?? "—"}</span>
            </div>
          </>
        )}
      </div>

      {gapClosureOrchestration && (
        <div className="mt-3 space-y-1 text-xs text-[var(--sl-text-dim)]">
          {orchestrationRuns.length > 0 && (
            <div>
              Orchestration runs:{" "}
              <span className="font-mono text-white">{orchestrationRuns.join(" → ")}</span>
            </div>
          )}
          {followupChain.length > 1 && (
            <div>
              Follow-up chain:{" "}
              <span className="font-mono text-white">{followupChain.join(" → ")}</span>
            </div>
          )}
          {gapClosureOrchestration.gap_closure_verdict && (
            <div>
              Last gap closure verdict:{" "}
              <span className="font-mono text-white">{gapClosureOrchestration.gap_closure_verdict}</span>
            </div>
          )}
        </div>
      )}

      {(researchPlan?.follow_up_focus ?? []).length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
            Follow-up focus
          </div>
          <div className="flex flex-wrap gap-1">
            {(researchPlan?.follow_up_focus ?? []).map((focus) => (
              <span key={focus} className="sl-pill sl-pill--info text-xs">
                {focus}
              </span>
            ))}
          </div>
        </div>
      )}

      {(researchPlan?.profile_weak_concepts ?? []).length > 0 && (
        <div className="mt-3 text-xs text-[var(--sl-text-dim)]">
          Weak concepts:{" "}
          <span className="font-mono text-white">
            {(researchPlan?.profile_weak_concepts ?? []).join(", ")}
          </span>
        </div>
      )}

      {(researchPlan?.profile_known_gaps ?? []).length > 0 && (
        <ul className="mt-2 space-y-1 text-sm text-[var(--sl-text-dim)]">
          {(researchPlan?.profile_known_gaps ?? []).map((gap) => (
            <li key={gap}>• {gap}</li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
