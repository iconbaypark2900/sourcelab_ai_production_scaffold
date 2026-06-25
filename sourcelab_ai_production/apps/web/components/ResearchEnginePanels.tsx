"use client";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import ExpansionExecutionPanel from "@/components/ExpansionExecutionPanel";
import LessonEvolutionPanel from "@/components/LessonEvolutionPanel";
import LibraryExpansionPlanPanel from "@/components/LibraryExpansionPlanPanel";
import LibraryImprovementPanel from "@/components/LibraryImprovementPanel";
import SourcePromotionPanel from "@/components/SourcePromotionPanel";
import GapClosurePanel from "@/components/GapClosurePanel";
import TopicMemoryPanel from "@/components/TopicMemoryPanel";
import type {
  EvidenceBoundLessonPlanArtifact,
  GapClosureReportArtifact,
  GapClosureOrchestrationArtifact,
  GenericnessReportArtifact,
  LessonEvolutionReportArtifact,
  LibraryExpansionExecutionArtifact,
  LibraryExpansionPlanArtifact,
  LibraryImprovementReportArtifact,
  ResearchPlanArtifact,
  RetrievalStrategyArtifact,
  SourceCoverageReportArtifact,
  SourceExpansionSuggestionsArtifact,
  SourcePromotionReportArtifact,
  TopicProfileUpdateArtifact,
} from "@/lib/types";

interface ResearchEnginePanelsProps {
  researchPlan: ResearchPlanArtifact | null;
  retrievalStrategy: RetrievalStrategyArtifact | null;
  sourceCoverageReport: SourceCoverageReportArtifact | null;
  evidenceBoundLessonPlan: EvidenceBoundLessonPlanArtifact | null;
  genericnessReport: GenericnessReportArtifact | null;
  topicProfileUpdate: TopicProfileUpdateArtifact | null;
  sourceExpansionSuggestions: SourceExpansionSuggestionsArtifact | null;
  lessonEvolutionReport?: LessonEvolutionReportArtifact | null;
  libraryExpansionPlan?: LibraryExpansionPlanArtifact | null;
  libraryExpansionExecution?: LibraryExpansionExecutionArtifact | null;
  libraryImprovementReport?: LibraryImprovementReportArtifact | null;
  sourcePromotionReport?: SourcePromotionReportArtifact | null;
  gapClosureReport?: GapClosureReportArtifact | null;
  gapClosureOrchestration?: GapClosureOrchestrationArtifact | null;
}

export default function ResearchEnginePanels({
  researchPlan,
  retrievalStrategy,
  sourceCoverageReport,
  evidenceBoundLessonPlan,
  genericnessReport,
  topicProfileUpdate,
  sourceExpansionSuggestions,
  lessonEvolutionReport,
  libraryExpansionPlan,
  libraryExpansionExecution,
  libraryImprovementReport,
  sourcePromotionReport,
  gapClosureReport,
  gapClosureOrchestration,
}: ResearchEnginePanelsProps) {
  if (
    !researchPlan &&
    !retrievalStrategy &&
    !sourceCoverageReport &&
    !evidenceBoundLessonPlan &&
    !genericnessReport
  ) {
    return null;
  }

  return (
    <div className="space-y-4">
      {researchPlan && (
        <Panel title="Research plan" hint="Pack-aware subtopics and questions" glow="cyan" id="research-plan">
          {researchPlan.profile_context_used && (
            <div className="mb-2">
              <StatusPill tone="info" label="adaptive profile" dot={false} />
            </div>
          )}
          <ul className="space-y-1 text-sm text-[var(--sl-text-dim)]">
            {(researchPlan.research_questions ?? []).map((q) => (
              <li key={q}>• {q}</li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap gap-1">
            {(researchPlan.pack_focus_areas ?? []).map((area) => (
              <span key={area} className="sl-pill sl-pill--neutral text-xs">
                {area}
              </span>
            ))}
          </div>
        </Panel>
      )}

      {retrievalStrategy && (
        <Panel title="Retrieval strategy" hint="Library-aware queries and origins" glow="violet" id="research-retrieval">
          <div className="mb-3 grid gap-2 sm:grid-cols-3">
            <Stat label="Pack sources" value={String(retrievalStrategy.source_pack_source_count ?? 0)} />
            <Stat label="Silver cards" value={String(retrievalStrategy.library_silver_card_count ?? 0)} />
            <Stat label="Promoted" value={String(retrievalStrategy.promoted_candidate_count ?? 0)} />
          </div>
          <div className="space-y-2 text-xs text-[var(--sl-text-dim)]">
            {(retrievalStrategy.queries ?? []).slice(0, 6).map((q) => (
              <div key={q.query_id} className="font-mono">
                {q.text} <span className="text-[var(--sl-text-faint)]">({q.priority})</span>
              </div>
            ))}
          </div>
          {(retrievalStrategy.hits ?? []).length > 0 && (
            <div className="mt-3 border-t border-[var(--sl-border)] pt-3">
              <div className="mb-2 text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
                Labeled hits
              </div>
              <ul className="space-y-1 text-xs font-mono text-[var(--sl-text-dim)]">
                {(retrievalStrategy.hits ?? []).map((hit) => (
                  <li key={hit.chunk_id}>
                    {hit.chunk_id} · {hit.origin} · {hit.score.toFixed(3)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      )}

      {sourceCoverageReport && (
        <Panel title="Source coverage (engine)" hint="Coverage score and weak labels" glow="cyan" id="research-coverage-engine">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="text-2xl font-semibold text-white">
              {(sourceCoverageReport.coverage_score * 100).toFixed(0)}%
            </span>
            {(sourceCoverageReport.weak_labels ?? []).map((label) => (
              <StatusPill key={label} tone="blocked" label={label} dot={false} />
            ))}
          </div>
          {(sourceCoverageReport.gaps ?? []).length > 0 && (
            <ul className="space-y-1 text-sm text-[var(--sl-text-dim)]">
              {(sourceCoverageReport.gaps ?? []).map((gap) => (
                <li key={gap}>• {gap}</li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      {evidenceBoundLessonPlan && (
        <Panel title="Evidence-bound lesson" hint="Sections with chunk and card bindings" id="research-lesson-plan">
          <div className="mb-2 text-xs text-[var(--sl-text-dim)]">
            Overall strength:{" "}
            <span className="font-mono text-white">{evidenceBoundLessonPlan.overall_evidence_strength}</span>
          </div>
          <ul className="space-y-2 text-sm text-[var(--sl-text-dim)]">
            {(evidenceBoundLessonPlan.sections ?? []).map((section) => (
              <li key={section.section_id} className="rounded border border-[var(--sl-border)] p-2">
                <div className="font-medium text-white">{section.title}</div>
                <div className="text-xs">
                  chunks: {(section.chunk_ids ?? []).join(", ") || "—"} · strength: {section.evidence_strength}
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {genericnessReport && (
        <Panel title="Genericness" hint="Topic specificity check" id="research-genericness">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <StatusPill
              tone={
                genericnessReport.verdict === "specific"
                  ? "pass"
                  : genericnessReport.verdict === "somewhat_generic"
                    ? "review"
                    : "blocked"
              }
              label={genericnessReport.verdict}
            />
            <span className="text-xs text-[var(--sl-text-dim)]">
              score {genericnessReport.genericness_score.toFixed(2)}
            </span>
          </div>
          <ul className="space-y-1 text-sm text-[var(--sl-text-dim)]">
            {(genericnessReport.recommendations ?? []).map((rec) => (
              <li key={rec}>• {rec}</li>
            ))}
          </ul>
        </Panel>
      )}

      <TopicMemoryPanel
        researchPlan={researchPlan}
        topicProfileUpdate={topicProfileUpdate}
        gapClosureOrchestration={gapClosureOrchestration}
      />
      <LessonEvolutionPanel report={lessonEvolutionReport ?? null} />
      <LibraryExpansionPlanPanel plan={libraryExpansionPlan ?? null} />
      <ExpansionExecutionPanel report={libraryExpansionExecution ?? null} />
      <LibraryImprovementPanel report={libraryImprovementReport ?? null} />
      <SourcePromotionPanel report={sourcePromotionReport ?? null} />
      <GapClosurePanel report={gapClosureReport ?? null} orchestration={gapClosureOrchestration ?? null} />

      {sourceExpansionSuggestions && (sourceExpansionSuggestions.suggestions ?? []).length > 0 && (
        <Panel title="Expansion suggestions" hint="Library collector hints" id="research-expansion">
          <ul className="space-y-2 text-sm text-[var(--sl-text-dim)]">
            {(sourceExpansionSuggestions.suggestions ?? []).map((s) => (
              <li key={s.suggestion_id}>
                <span className="font-mono text-white">{s.collector}</span> — {s.reason}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-2.5 py-2">
      <div className="text-base font-semibold text-white">{value}</div>
      <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">{label}</div>
    </div>
  );
}
