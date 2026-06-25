"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

import type { LessonShowResponse } from "@/lib/types";
import { clamp } from "@/lib/format";
import SourceChip from "@/components/SourceChip";

interface GeneratedLessonPanelProps {
  lesson: LessonShowResponse | null;
}

/* Minimal, dependency-free markdown rendering for trusted local content.
 * Text is rendered via React nodes (no dangerouslySetInnerHTML). */
function parseInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const regex = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("`")) {
      nodes.push(<code key={`${keyPrefix}-c${i}`}>{token.slice(1, -1)}</code>);
    } else {
      nodes.push(<strong key={`${keyPrefix}-b${i}`}>{token.slice(2, -2)}</strong>);
    }
    lastIndex = match.index + token.length;
    i += 1;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function renderMarkdown(md: string): ReactNode[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: string[] | null = null;
  let listType: "ul" | "ol" = "ul";
  let key = 0;

  const flushPara = () => {
    if (para.length) {
      blocks.push(<p key={`b${key}`}>{parseInline(para.join(" "), `p${key}`)}</p>);
      key += 1;
      para = [];
    }
  };
  const flushList = () => {
    if (list && list.length) {
      const items = list.map((item, idx) => (
        <li key={`li${key}-${idx}`}>{parseInline(item, `li${key}-${idx}`)}</li>
      ));
      blocks.push(listType === "ul" ? <ul key={`b${key}`}>{items}</ul> : <ol key={`b${key}`}>{items}</ol>);
      key += 1;
    }
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushPara();
      flushList();
      continue;
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      flushPara();
      flushList();
      const level = heading[1].length;
      const content = parseInline(heading[2], `h${key}`);
      if (level === 1) {
        blocks.push(<h1 key={`b${key}`}>{content}</h1>);
      } else if (level === 2) {
        blocks.push(<h2 key={`b${key}`}>{content}</h2>);
      } else {
        blocks.push(<h3 key={`b${key}`}>{content}</h3>);
      }
      key += 1;
      continue;
    }
    const ul = /^[-*]\s+(.*)$/.exec(line);
    const ol = /^\d+\.\s+(.*)$/.exec(line);
    if (ul) {
      flushPara();
      if (!list || listType !== "ul") {
        flushList();
        list = [];
        listType = "ul";
      }
      list.push(ul[1]);
      continue;
    }
    if (ol) {
      flushPara();
      if (!list || listType !== "ol") {
        flushList();
        list = [];
        listType = "ol";
      }
      list.push(ol[1]);
      continue;
    }
    flushList();
    para.push(line.trim());
  }
  flushPara();
  flushList();
  return blocks;
}

export default function GeneratedLessonPanel({ lesson }: GeneratedLessonPanelProps) {
  const [reveal, setReveal] = useState(45);
  const [showFull, setShowFull] = useState(false);
  const [fullHeight, setFullHeight] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);

  const markdown = lesson?.lesson_markdown ?? "";

  useLayoutEffect(() => {
    if (contentRef.current) {
      setFullHeight(contentRef.current.scrollHeight);
    }
  }, [markdown]);

  useEffect(() => {
    function onResize() {
      if (contentRef.current) {
        setFullHeight(contentRef.current.scrollHeight);
      }
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  if (!lesson || !markdown.trim()) {
    return (
      <p className="text-sm text-[var(--sl-text-faint)]">No generated lesson available for this run.</p>
    );
  }

  const effectiveReveal = showFull ? 100 : reveal;
  const visibleHeight = showFull
    ? undefined
    : Math.max(140, (fullHeight * clamp(reveal, 0, 100)) / 100);

  return (
    <div className="space-y-3">
      {lesson.sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {lesson.sources.map((source) => (
            <SourceChip key={source} sourceId={source} />
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-3 py-2.5">
        <span className="text-[0.66rem] uppercase tracking-[0.12em] text-[var(--sl-text-faint)]">
          Reveal field
        </span>
        <input
          type="range"
          min={0}
          max={100}
          value={effectiveReveal}
          disabled={showFull}
          onChange={(event) => setReveal(Number(event.target.value))}
          className="sl-range flex-1"
          aria-label="Lesson reveal percentage"
        />
        <span className="w-10 text-right font-mono text-xs text-[var(--sl-cyan)]">
          {effectiveReveal}%
        </span>
        <button
          type="button"
          className="sl-btn"
          onClick={() => setShowFull((value) => !value)}
        >
          {showFull ? "Collapse" : "Show full"}
        </button>
      </div>

      <div
        className={`sl-reveal-mask ${showFull || effectiveReveal >= 100 ? "sl-reveal-mask--full" : ""}`}
        style={visibleHeight ? { maxHeight: `${visibleHeight}px` } : undefined}
      >
        <div ref={contentRef} className="sl-prose">
          {renderMarkdown(markdown)}
        </div>
      </div>
    </div>
  );
}
