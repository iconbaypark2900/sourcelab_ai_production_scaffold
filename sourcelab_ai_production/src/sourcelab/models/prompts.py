"""Prompt templates for the model router.

Instruction:
- All templates must include source/chunk IDs when available.
- All templates must include fail-closed instructions.
- Templates are used by the model router to generate prompts.
"""

from __future__ import annotations

from sourcelab.models.schemas import PromptRenderResult, PromptTemplate


class PromptTemplates:
    """Prompt templates for all model routes."""

    TEMPLATES: dict[str, PromptTemplate] = {
        "scenario_generation": PromptTemplate(
            name="scenario_generation",
            template=(
                "Generate a learning scenario about {topic} at {level} level.\n"
                "Source IDs: {source_ids}\n"
                "Chunk IDs: {chunk_ids}\n"
                "Context: {context}\n"
                "Return JSON with keys: scenario, context, task, constraints.\n"
                "IMPORTANT: Only use information from the provided sources. "
                "If insufficient information, state what is missing."
            ),
            description="Generate a learning scenario from sources",
            expects_json=True,
            source_required=True,
            fail_closed=True,
        ),
        "answer_key_generation": PromptTemplate(
            name="answer_key_generation",
            template=(
                "Generate an answer key for the following scenario:\n"
                "{scenario_text}\n\n"
                "Source IDs: {source_ids}\n"
                "Chunk IDs: {chunk_ids}\n"
                "Difficulty: {difficulty}\n"
                "Return JSON with keys: answers (list of {question_id, answer, points, rationale}).\n"
                "IMPORTANT: All answers must be grounded in the provided sources. "
                "Cite source IDs for each answer."
            ),
            description="Generate an answer key from a scenario",
            expects_json=True,
            source_required=True,
            fail_closed=True,
        ),
        "rubric_generation": PromptTemplate(
            name="rubric_generation",
            template=(
                "Generate a scoring rubric for the following scenario:\n"
                "{scenario_text}\n\n"
                "Source IDs: {source_ids}\n"
                "Chunk IDs: {chunk_ids}\n"
                "Return JSON with keys: criteria (list of {name, description, max_points, weight}).\n"
                "IMPORTANT: Rubric criteria must be derivable from the provided sources."
            ),
            description="Generate a rubric from a scenario",
            expects_json=True,
            source_required=True,
            fail_closed=True,
        ),
        "lesson_package_generation": PromptTemplate(
            name="lesson_package_generation",
            template=(
                "Generate a complete lesson package about {topic} at {level} level.\n"
                "Scenario: {scenario_text}\n"
                "Answer key: {answer_key_text}\n"
                "Rubric: {rubric_text}\n"
                "Source IDs: {source_ids}\n"
                "Chunk IDs: {chunk_ids}\n"
                "Return JSON with keys: title, objective, content, exercises.\n"
                "IMPORTANT: Only use information from the provided sources."
            ),
            description="Generate a full lesson package",
            expects_json=True,
            source_required=True,
            fail_closed=True,
        ),
        "entailment_scoring": PromptTemplate(
            name="entailment_scoring",
            template=(
                "Evaluate whether the following claim is supported by the sources.\n"
                "Claim: {claim}\n"
                "Evidence:\n{evidence}\n\n"
                "Source IDs: {source_ids}\n"
                "Return JSON with keys: score (0.0-1.0), reasoning, supporting_sources.\n"
                "IMPORTANT: Score based ONLY on the provided evidence."
            ),
            description="Score claim entailment against evidence",
            expects_json=True,
            source_required=True,
            fail_closed=True,
        ),
        "answer_judging": PromptTemplate(
            name="answer_judging",
            template=(
                "Judge the following answer against the rubric and source context.\n\n"
                "Topic: {topic}\n"
                "Answer: {answer}\n\n"
                "Rubric Criteria:\n{rubric_text}\n\n"
                "Source Context:\n{source_context}\n"
                "Source IDs: {source_ids}\n\n"
                "Return JSON with exactly these keys:\n"
                "{\n"
                '  "criteria_scores": {\n'
                '    "topic_relevance": 0.0-1.0,\n'
                '    "source_grounding": 0.0-1.0,\n'
                '    "practical_reasoning": 0.0-1.0,\n'
                '    "uncertainty_control": 0.0-1.0,\n'
                '    "trap_avoidance": 0.0-1.0,\n'
                '    "clarity": 0.0-1.0,\n'
                '    "citation_use_of_evidence": 0.0-1.0\n'
                "  },\n"
                '  "feedback": "Overall assessment",\n'
                '  "strengths": ["strength1", "strength2"],\n'
                '  "weaknesses": ["weakness1", "weakness2"]\n'
                "}\n"
                "IMPORTANT: Score each criterion 0.0-1.0 based ONLY on the provided rubric "
                "and source context. Return ONLY valid JSON, no other text."
            ),
            description="Judge an answer against a rubric with per-criterion scores",
            expects_json=True,
            source_required=True,
            fail_closed=True,
        ),
        "general": PromptTemplate(
            name="general",
            template=(
                "{user_prompt}\n\n"
                "Source IDs: {source_ids}\n"
                "Chunk IDs: {chunk_ids}\n"
                "IMPORTANT: Only use information from the provided sources. "
                "If insufficient information, state what is missing."
            ),
            description="General purpose prompt",
            expects_json=False,
            source_required=False,
            fail_closed=True,
        ),
    }

    @classmethod
    def get_template(cls, route: str) -> PromptTemplate:
        return cls.TEMPLATES.get(route, cls.TEMPLATES["general"])

    @classmethod
    def render(
        cls,
        route: str,
        source_ids: list[str] | None = None,
        chunk_ids: list[str] | None = None,
        **kwargs: object,
    ) -> PromptRenderResult:
        template = cls.get_template(route)
        source_ids = source_ids or []
        chunk_ids = chunk_ids or []

        replacements: dict[str, str] = {
            "source_ids": ", ".join(source_ids) if source_ids else "None",
            "chunk_ids": ", ".join(chunk_ids) if chunk_ids else "None",
        }
        for key, value in kwargs.items():
            replacements[key] = str(value) if value is not None else ""

        rendered = template.template
        for key, value in replacements.items():
            rendered = rendered.replace("{" + key + "}", value)

        if template.fail_closed and template.source_required and not source_ids:
            rendered += "\n\nWARNING: No sources provided. Responses must be marked as ungrounded."

        return PromptRenderResult(
            prompt=rendered,
            template_name=route,
            source_ids=source_ids,
            chunk_ids=chunk_ids,
        )
