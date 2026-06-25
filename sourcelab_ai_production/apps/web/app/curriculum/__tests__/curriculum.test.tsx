// @vitest-environment happy-dom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { formatScore } from "@/lib/format";
import type { CurriculumResponse, FullSkillProfile } from "@/lib/types";
import {
  CurriculumDashboard,
  MasteryCard,
  SourceGroundingSparkline,
  avgMastery,
  masteryBand,
  masteryPillTone,
  masteryTone,
} from "../page";

afterEach(cleanup);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

describe("masteryBand", () => {
  it('returns "advanced" for score >= 0.8', () => {
    expect(masteryBand(0.8)).toBe("advanced");
    expect(masteryBand(1.0)).toBe("advanced");
    expect(masteryBand(0.95)).toBe("advanced");
  });

  it('returns "developing" for 0.6 <= score < 0.8', () => {
    expect(masteryBand(0.6)).toBe("developing");
    expect(masteryBand(0.79)).toBe("developing");
    expect(masteryBand(0.7)).toBe("developing");
  });

  it('returns "needs_support" for score < 0.6', () => {
    expect(masteryBand(0.59)).toBe("needs_support");
    expect(masteryBand(0.0)).toBe("needs_support");
    expect(masteryBand(0.3)).toBe("needs_support");
  });
});

describe("masteryTone", () => {
  it('returns "good" for score >= 0.8', () => {
    expect(masteryTone(0.8)).toBe("good");
    expect(masteryTone(1.0)).toBe("good");
  });

  it('returns "warn" for 0.6 <= score < 0.8', () => {
    expect(masteryTone(0.6)).toBe("warn");
    expect(masteryTone(0.75)).toBe("warn");
  });

  it('returns "bad" for score < 0.6', () => {
    expect(masteryTone(0.59)).toBe("bad");
    expect(masteryTone(0.0)).toBe("bad");
  });
});

describe("masteryPillTone", () => {
  it('returns "pass" for score >= 0.8', () => {
    expect(masteryPillTone(0.8)).toBe("pass");
  });

  it('returns "review" for 0.6 <= score < 0.8', () => {
    expect(masteryPillTone(0.6)).toBe("review");
  });

  it('returns "blocked" for score < 0.6', () => {
    expect(masteryPillTone(0.59)).toBe("blocked");
  });
});

describe("avgMastery", () => {
  it("returns 0 for empty profile", () => {
    const profile = makeProfile({ mastery: {} });
    expect(avgMastery(profile)).toBe(0);
  });

  it("averages all mastery values", () => {
    const profile = makeProfile({ mastery: { a: 0.9, b: 0.5, c: 0.7 } });
    expect(avgMastery(profile)).toBeCloseTo(0.7);
  });

  it("handles single topic", () => {
    const profile = makeProfile({ mastery: { only: 0.42 } });
    expect(avgMastery(profile)).toBe(0.42);
  });
});

// ---------------------------------------------------------------------------
// MasteryCard
// ---------------------------------------------------------------------------

describe("MasteryCard", () => {
  it("renders topic name and mastery band", () => {
    render(<MasteryCard topic="PQC" mastery={0.9} criteria={{}} attempts={5} />);
    expect(screen.getByText("PQC")).toBeTruthy();
    const bands = screen.getAllByText("advanced");
    expect(bands.length).toBeGreaterThanOrEqual(1);
  });

  it("renders singular 'attempt' when count is 1", () => {
    const { container } = render(
      <MasteryCard topic="T" mastery={0.5} criteria={{}} attempts={1} />,
    );
    expect(container.textContent).toContain("1 attempt");
  });

  it("renders criteria breakdown when available", () => {
    render(
      <MasteryCard
        topic="PQC"
        mastery={0.7}
        criteria={{ accuracy: 0.85, completeness: 0.6 }}
        attempts={3}
      />,
    );
    expect(screen.getByText("accuracy")).toBeTruthy();
    expect(screen.getByText("completeness")).toBeTruthy();
    expect(screen.getByText(formatScore(0.85))).toBeTruthy();
    expect(screen.getByText(formatScore(0.6))).toBeTruthy();
  });

  it("shows needs_support band for low mastery", () => {
    render(<MasteryCard topic="Hard" mastery={0.3} criteria={{}} attempts={2} />);
    const pills = screen.getAllByText("needs_support");
    expect(pills.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// SourceGroundingSparkline
// ---------------------------------------------------------------------------

describe("SourceGroundingSparkline", () => {
  it("renders latest score and attempt count", () => {
    const { container } = render(
      <SourceGroundingSparkline history={[0.3, 0.5, 0.7]} />,
    );
    expect(container.textContent).toContain("Last 3 attempts");
    expect(screen.getByText("latest")).toBeTruthy();
  });

  it("returns null for empty history", () => {
    const { container } = render(<SourceGroundingSparkline history={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("handles single value history", () => {
    const { container } = render(
      <SourceGroundingSparkline history={[0.6]} />,
    );
    expect(container.textContent).toContain("Last 1 attempt");
  });

  it("renders bar for each entry with correct tooltip", () => {
    render(<SourceGroundingSparkline history={[0.2, 0.9]} />);
    const bars = screen.getAllByTitle(/^Attempt \d+:/);
    expect(bars).toHaveLength(2);
    expect(bars[0].getAttribute("title")).toBe("Attempt 1: 20.0%");
    expect(bars[1].getAttribute("title")).toBe("Attempt 2: 90.0%");
  });
});

// ---------------------------------------------------------------------------
// CurriculumDashboard
// ---------------------------------------------------------------------------

describe("CurriculumDashboard", () => {
  it("renders empty state when no topics practiced", () => {
    const profile = makeProfile({
      mastery: {},
      strengths: [],
      weaknesses: [],
      source_grounding_history: [],
      attempts: [],
    });
    render(<CurriculumDashboard data={{ profile, latest_report: null, latest_next_task: null }} />);
    expect(screen.getByText("No topics practiced yet.")).toBeTruthy();
  });

  it("renders all panels with full data", () => {
    const profile = makeProfile({
      mastery: { PQC: 0.9, Safety: 0.6 },
      criterion_mastery: {
        PQC: { accuracy: 0.95, completeness: 0.85 },
        Safety: { accuracy: 0.6 },
      },
      strengths: ["Strong citation skills"],
      weaknesses: [
        {
          criterion: "completeness",
          topic: "Safety",
          occurrences: 2,
          average_score: 0.4,
          first_seen: "2026-01-01T00:00:00Z",
          last_seen: "2026-01-10T00:00:00Z",
          recommendation: "Practice more",
        },
      ],
      source_grounding_history: [0.5, 0.7, 0.8],
      attempts: [
        { topic: "PQC", score: 0.9, attempt_id: "a1", run_id: "r1", difficulty: 3, task_format: "qa", source_grounding_score: 0.8, timestamp: "2026-01-10T00:00:00Z" },
        { topic: "Safety", score: 0.6, attempt_id: "a2", run_id: "r2", difficulty: 2, task_format: "qa", source_grounding_score: 0.6, timestamp: "2026-01-09T00:00:00Z" },
      ],
    });

    const data: CurriculumResponse = {
      profile,
      latest_report: { run_id: "r2", topic: "Safety", report_json: { overall_score: 0.65, recommended_focus: "Improve citations" } },
      latest_next_task: { difficulty: 3, focus: "Citation accuracy", task_format: "qa", reason: "Focus on area with most room for improvement" },
    };

    const { container } = render(<CurriculumDashboard data={data} />);

    expect(container.textContent).toContain("1 advanced, 0 need support");
    expect(container.textContent).toContain(formatScore(0.75));
    expect(container.textContent).toContain("2");

    // Next-task panel
    expect(screen.getByText("Difficulty 3/5")).toBeTruthy();
    expect(screen.getByText("Citation accuracy")).toBeTruthy();
    expect(screen.getByText("Focus on area with most room for improvement")).toBeTruthy();

    // Latest report
    expect(screen.getByText("Improve citations")).toBeTruthy();

    // Strengths
    expect(screen.getByText("Strong citation skills")).toBeTruthy();

    // Weaknesses
    expect(container.textContent).toContain("completeness");
    expect(container.textContent).toContain("score 40.0%");

    // Topic cards
    expect(screen.getByText("PQC")).toBeTruthy();
    expect(screen.getByText("Safety")).toBeTruthy();

    // Sparkline
    expect(container.textContent).toContain("Last 3 attempts");
  });

  it("renders no-data fallbacks when report and nextTask are null", () => {
    const profile = makeProfile({
      mastery: { PQC: 0.9 },
      strengths: [],
      weaknesses: [],
      source_grounding_history: [],
      attempts: [{ topic: "PQC", score: 0.9, attempt_id: "a1", run_id: "r1", difficulty: 3, task_format: "qa", source_grounding_score: 0.8, timestamp: "2026-01-10T00:00:00Z" }],
    });
    const { container } = render(
      <CurriculumDashboard data={{ profile, latest_report: null, latest_next_task: null }} />,
    );

    expect(container.textContent).toContain("Submit an answer to get a personalized recommendation.");
    expect(container.textContent).toContain("No answers submitted yet.");
    expect(screen.getByText("No strengths or weaknesses tracked yet.")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

function makeProfile(overrides: Partial<FullSkillProfile> = {}): FullSkillProfile {
  return {
    profile_id: "p1",
    topic: null,
    attempts: [],
    mastery: {},
    criterion_mastery: {},
    strengths: [],
    weaknesses: [],
    source_grounding_history: [],
    preferred_next_difficulty: 3,
    preferred_guidance_level: 2,
    last_practiced: "",
    ...overrides,
  };
}
