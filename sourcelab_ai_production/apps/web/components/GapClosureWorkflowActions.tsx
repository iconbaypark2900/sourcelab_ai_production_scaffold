"use client";

import { useCallback, useState } from "react";

import {
  buildAnswerBridgeCommand,
  buildGapClosureReplayCommand,
  buildGapClosureWorkflowCommands,
  buildPanelPrimaryCommand,
  formatWorkflowBlock,
  suggestNextSafeCommandFromOrchestration,
  type GapClosureWorkflowInput,
} from "@/lib/gap-closure-workflow";
import type { GapClosureOrchestrationArtifact } from "@/lib/types";

interface GapClosureWorkflowActionsProps {
  workflow: GapClosureWorkflowInput;
  panel: "expansion" | "improvement" | "promotion" | "gap-closure" | "orchestration";
  orchestrationCommands?: string[];
  orchestration?: GapClosureOrchestrationArtifact | null;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    window.prompt("Copy command:", text);
    return false;
  }
}

export default function GapClosureWorkflowActions({
  workflow,
  panel,
  orchestrationCommands,
  orchestration,
}: GapClosureWorkflowActionsProps) {
  const [copied, setCopied] = useState<
    "none" | "command" | "workflow" | "answer-bridge" | "replay" | "next-safe"
  >("none");

  const primaryCommand = buildPanelPrimaryCommand(panel, workflow);
  const workflowCommands =
    orchestrationCommands && orchestrationCommands.length > 0
      ? orchestrationCommands
      : buildGapClosureWorkflowCommands(workflow);
  const workflowBlock = formatWorkflowBlock(workflowCommands);
  const answerBridgeCommand = buildAnswerBridgeCommand({
    runId: workflow.runId,
    execute: workflow.execute,
    answerText: workflow.answerText,
    answerFile: workflow.answerFile,
    skipAnswerSubmit: workflow.skipAnswerSubmit,
  });
  const replayCommand = buildGapClosureReplayCommand(workflow.runId);
  const nextSafeCommand = orchestration
    ? suggestNextSafeCommandFromOrchestration({
        runId: orchestration.run_id,
        answerSubmitStatus: orchestration.answer_submit_status,
        answerSource: orchestration.answer_source,
        followupRunId: orchestration.followup_run_id,
        steps: orchestration.steps,
      })
    : buildGapClosureReplayCommand(workflow.runId);

  const handleCopy = useCallback(
    async (kind: "command" | "workflow" | "answer-bridge" | "replay" | "next-safe") => {
      const text =
        kind === "command"
          ? primaryCommand
          : kind === "workflow"
            ? workflowBlock
            : kind === "answer-bridge"
              ? answerBridgeCommand
              : kind === "replay"
                ? replayCommand
                : nextSafeCommand;
      const ok = await copyText(text);
      if (ok) {
        setCopied(kind);
        window.setTimeout(() => setCopied("none"), 2000);
      }
    },
    [primaryCommand, workflowBlock, answerBridgeCommand, replayCommand, nextSafeCommand],
  );

  return (
    <div className="mt-3 border-t border-[var(--sl-border)] pt-3">
      <div className="mb-2 flex flex-wrap gap-2">
        <button
          type="button"
          className="sl-btn px-2 py-0.5 text-[0.68rem]"
          onClick={() => void handleCopy("command")}
        >
          {copied === "command" ? "Command copied" : "Copy command"}
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-0.5 text-[0.68rem]"
          onClick={() => void handleCopy("workflow")}
        >
          {copied === "workflow" ? "Workflow copied" : "Copy full workflow"}
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-0.5 text-[0.68rem]"
          onClick={() => void handleCopy("answer-bridge")}
        >
          {copied === "answer-bridge" ? "Answer bridge copied" : "Copy answer-bridge workflow"}
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-0.5 text-[0.68rem]"
          onClick={() => void handleCopy("replay")}
        >
          {copied === "replay" ? "Replay copied" : "Copy replay command"}
        </button>
        <button
          type="button"
          className="sl-btn px-2 py-0.5 text-[0.68rem]"
          onClick={() => void handleCopy("next-safe")}
        >
          {copied === "next-safe" ? "Next command copied" : "Copy next safe command"}
        </button>
      </div>
      <div className="text-[0.62rem] uppercase tracking-[0.08em] text-[var(--sl-text-faint)]">
        Suggested workflow
      </div>
      <pre className="mt-1 overflow-x-auto rounded border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] p-2 font-mono text-[0.65rem] text-[var(--sl-text-dim)] whitespace-pre-wrap">
        {workflowBlock}
      </pre>
      {orchestration && (
        <div className="mt-2 font-mono text-[0.62rem] text-[var(--sl-text-faint)]">
          Next safe: {nextSafeCommand}
        </div>
      )}
    </div>
  );
}
