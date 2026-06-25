import type { ArtifactRow, CitationResolution, RunSummary, StageStatus } from "@/lib/types";

interface AttemptLaneSummary {
  attemptCount: number;
  latestScore: number | null;
  bestScore: number | null;
  needsReviewCount: number;
  selectedAttemptId?: string | null;
}

interface DiffusionTimelineProps {
  run: RunSummary;
  artifacts: ArtifactRow[];
  citation: CitationResolution | null;
  attemptLane?: AttemptLaneSummary | null;
}

interface Stage {
  key: string;
  label: string;
  status: StageStatus;
  detail: string;
}

const STAGE_CLASS: Record<StageStatus, string> = {
  PASS: "sl-stage--pass",
  REVIEW: "sl-stage--review",
  BLOCKED: "sl-stage--blocked",
  MISSING: "sl-stage--missing",
};

const STAGE_PILL: Record<StageStatus, string> = {
  PASS: "sl-pill--pass",
  REVIEW: "sl-pill--review",
  BLOCKED: "sl-pill--blocked",
  MISSING: "sl-pill--missing",
};

function present(names: Set<string>, ...candidates: string[]): boolean {
  return candidates.some((name) => names.has(name));
}

/**
 * Derive the diffusion-console stage ladder from real run artifacts + metrics.
 * Vocabulary is a metaphor: SourceLab is a deterministic source-grounded
 * pipeline, not a diffusion model.
 */
function buildStages(
  run: RunSummary,
  artifacts: ArtifactRow[],
  citation: CitationResolution | null,
): Stage[] {
  const have = new Set(artifacts.filter((a) => a.exists).map((a) => a.name));

  const sourceField = present(have, "source_registry_snapshot.json");
  const retrieval = present(have, "retrieved_chunks.json", "retrieval_diagnostics.json");
  const lesson = present(have, "generated_lesson.md", "generated_lesson_package.json");
  const claims = present(have, "atomic_claims.json");
  const claimMap = present(have, "claim_map.json", "verification_report.json");
  const citationArtifact = present(have, "citation_resolution.json");
  const proof = present(have, "proof_summary.json");
  const profile = present(have, "mastery_update.json", "skill_profile_snapshot.json");
  const nextTask = present(have, "next_task_decision.json");

  const citationRate = citation?.resolution_rate ?? run.citation_resolution_rate ?? null;

  const denoiseStatus: StageStatus = !claimMap
    ? "MISSING"
    : run.unsupported_high_risk_claims > 0
      ? "REVIEW"
      : "PASS";

  const citationStatus: StageStatus = !citationArtifact
    ? "MISSING"
    : citationRate === null
      ? "REVIEW"
      : citationRate >= 1
        ? "PASS"
        : "REVIEW";

  const proofGate = (run.proof_bundle_status || "").toUpperCase();
  const proofStatus: StageStatus = !proof
    ? "MISSING"
    : proofGate === "PASS"
      ? "PASS"
      : proofGate === "FAIL"
        ? "BLOCKED"
        : "REVIEW";

  const answerStatus: StageStatus = run.has_answer
    ? run.needs_review === true
      ? "REVIEW"
      : "PASS"
    : "MISSING";

  return [
    {
      key: "source-field",
      label: "Source field initialized",
      status: sourceField ? "PASS" : "MISSING",
      detail: sourceField ? "Approved sources snapshotted" : "No source snapshot",
    },
    {
      key: "retrieval",
      label: "Retrieval signal formed",
      status: retrieval ? "PASS" : "MISSING",
      detail: retrieval ? "Evidence chunks retrieved" : "No retrieval artifact",
    },
    {
      key: "lesson",
      label: "Lesson draft generated",
      status: lesson ? "PASS" : "MISSING",
      detail: lesson ? "Source-grounded lesson drafted" : "No lesson draft",
    },
    {
      key: "claims",
      label: "Claims extracted",
      status: claims ? "PASS" : "MISSING",
      detail: claims ? "Atomic claims isolated" : "No atomic claims",
    },
    {
      key: "denoise",
      label: "Unsupported claims denoised",
      status: denoiseStatus,
      detail:
        denoiseStatus === "REVIEW"
          ? `${run.unsupported_high_risk_claims} high-risk unsupported`
          : denoiseStatus === "PASS"
            ? "No unsupported high-risk claims"
            : "No claim map",
    },
    {
      key: "citation",
      label: "Citations locked",
      status: citationStatus,
      detail:
        citationRate === null
          ? "Resolution rate unknown"
          : `Resolution ${(citationRate * 100).toFixed(0)}%`,
    },
    {
      key: "proof",
      label: "Proof bundle sealed",
      status: proofStatus,
      detail: proof ? `Release gate ${proofGate || "?"}` : "No proof summary",
    },
    {
      key: "answer",
      label: "Learner answer scored",
      status: answerStatus,
      detail: !run.has_answer
        ? "No answer submitted"
        : run.needs_review === true
          ? "Answer flagged for human review"
          : "Answer reviewed",
    },
    {
      key: "profile",
      label: "Skill profile updated",
      status: profile ? "PASS" : "MISSING",
      detail: profile ? "Mastery updated" : "No mastery update",
    },
    {
      key: "next-task",
      label: "Next task selected",
      status: nextTask ? "PASS" : "MISSING",
      detail: run.next_task_focus || (nextTask ? "Next task decided" : "No next task"),
    },
  ];
}

function formatLaneScore(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(0)}%`;
}

export default function DiffusionTimeline({
  run,
  artifacts,
  citation,
  attemptLane,
}: DiffusionTimelineProps) {
  const stages = buildStages(run, artifacts, citation);

  return (
    <ol className="space-y-2">
      {stages.map((stage, index) => (
        <li
          key={stage.key}
          className={`sl-stage ${STAGE_CLASS[stage.status]}`}
          style={{ animationDelay: `${index * 35}ms` }}
        >
          <div className="sl-stage__rail">
            <span className="sl-stage__node" />
            {index < stages.length - 1 && <span className="sl-stage__line" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-white">{stage.label}</span>
              <span className={`sl-pill ${STAGE_PILL[stage.status]}`}>{stage.status}</span>
            </div>
            <p className="mt-0.5 truncate text-xs text-[var(--sl-text-dim)]" title={stage.detail}>
              {stage.detail}
            </p>
            {stage.key === "answer" && attemptLane && attemptLane.attemptCount > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-x-2 gap-y-0.5 rounded-md border border-[rgba(34,211,238,0.15)] bg-[rgba(4,7,16,0.35)] px-2 py-1 text-[0.62rem] text-[var(--sl-text-faint)]">
                <span>{attemptLane.attemptCount} attempts</span>
                <span>latest {formatLaneScore(attemptLane.latestScore)}</span>
                <span className="text-[var(--sl-emerald)]">
                  best {formatLaneScore(attemptLane.bestScore)}
                </span>
                {attemptLane.needsReviewCount > 0 && (
                  <span className="text-[var(--sl-amber)]">
                    {attemptLane.needsReviewCount} review
                  </span>
                )}
                {attemptLane.selectedAttemptId && (
                  <span className="text-[var(--sl-violet)]">
                    sel {attemptLane.selectedAttemptId.replace("attempt_", "")}
                  </span>
                )}
              </div>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
