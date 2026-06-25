"use client";

import type { ReactNode } from "react";

import { Panel } from "@/components/Chrome";
import StatusPill from "@/components/StatusPill";
import {
  computeLessonQualityLabel,
  lessonQualityLabelText,
  lessonQualityLabelTone,
} from "@/lib/research-validation";
import type { ResearchValidationInput } from "@/lib/research-validation";
import { formatScore } from "@/lib/format";

interface LessonPlanQualityPanelProps {
  input: ResearchValidationInput;
}

export default function LessonPlanQualityPanel({ input }: LessonPlanQualityPanelProps) {
  const pkg = input.lessonPackage;
  const label = computeLessonQualityLabel(pkg, input.learning);
  const learning = input.learning?.report_json;

  if (!pkg) {
    return (
      <Panel title="Lesson plan quality" id="research-lesson-quality">
        <p className="text-sm text-[var(--sl-text-faint)]">
          No generated lesson package artifact for this run.
        </p>
      </Panel>
    );
  }

  const checks = [
    { label: "Scenario", ok: Boolean(pkg.scenario?.title && pkg.scenario?.context) },
    {
      label: "Learning objectives",
      ok: Boolean(pkg.lesson?.learning_objectives?.length),
    },
    { label: "Task instructions", ok: Boolean(pkg.lesson?.task_instructions) },
    { label: "Rubric", ok: pkg.rubric != null },
    { label: "Answer key", ok: pkg.answer_key != null },
    { label: "Learning report", ok: Boolean(input.learning) },
  ];

  return (
    <Panel title="Lesson plan quality" hint="Package + learning report" glow="violet" id="research-lesson-quality">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusPill tone={lessonQualityLabelTone(label)} label={lessonQualityLabelText(label)} />
        {pkg.level && <span className="sl-pill sl-pill--neutral">{pkg.level}</span>}
        {pkg.scenario?.task_format && (
          <span className="sl-pill sl-pill--neutral">{pkg.scenario.task_format}</span>
        )}
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        {checks.map((check) => (
          <div
            key={check.label}
            className="flex items-center justify-between rounded-lg border border-[var(--sl-border)] bg-[rgba(9,14,28,0.45)] px-3 py-2"
          >
            <span className="text-xs text-[var(--sl-text-dim)]">{check.label}</span>
            <StatusPill tone={check.ok ? "pass" : "review"} label={check.ok ? "Present" : "Missing"} dot={false} />
          </div>
        ))}
      </div>

      {pkg.scenario?.title && (
        <Block title="Scenario">{pkg.scenario.title}</Block>
      )}
      {pkg.lesson?.learning_objectives?.length ? (
        <Block title="Learning objectives">
          <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--sl-text-dim)]">
            {pkg.lesson.learning_objectives.map((objective) => (
              <li key={objective}>{objective}</li>
            ))}
          </ul>
        </Block>
      ) : null}
      {pkg.lesson?.failure_traps?.length ? (
        <Block title="Failure traps">
          <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--sl-text-dim)]">
            {pkg.lesson.failure_traps.map((trap) => (
              <li key={trap}>{trap}</li>
            ))}
          </ul>
        </Block>
      ) : null}
      {learning && (
        <Block title="Learning report snapshot">
          <div className="flex flex-wrap gap-3 text-xs text-[var(--sl-text-dim)]">
            {learning.overall_score != null && (
              <span>Overall {formatScore(learning.overall_score)}</span>
            )}
            {learning.rubric_alignment_score != null && (
              <span>Rubric {formatScore(learning.rubric_alignment_score)}</span>
            )}
            {learning.recommended_focus && (
              <span>Focus: {learning.recommended_focus}</span>
            )}
          </div>
        </Block>
      )}
    </Panel>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-3 border-t border-[var(--sl-border)] pt-3">
      <div className="mb-1 text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        {title}
      </div>
      {children}
    </div>
  );
}
