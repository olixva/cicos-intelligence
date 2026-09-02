"""Interview-plan values keep the LLM conversation bounded and renderable."""

import pytest


def test_interview_plan_rejects_an_ask_state_without_questions() -> None:
    from application.models.claim import InterviewPlan

    with pytest.raises(ValueError, match="requires at least one question"):
        InterviewPlan(status="ask")


def test_interview_question_rejects_duplicate_options() -> None:
    from application.models.claim import InterviewQuestion

    with pytest.raises(ValueError, match="unique"):
        InterviewQuestion(
            id="vehicle_a_signal",
            prompt="¿Qué color tenía el semáforo de A?",
            reason="Puede cambiar la prioridad.",
            answer_kind="choice",
            options=("Rojo", "Rojo"),
        )


def test_ready_interview_plan_has_no_questions() -> None:
    from application.models.claim import InterviewPlan, InterviewQuestion

    question = InterviewQuestion(
        id="vehicle_a_signal",
        prompt="¿Qué color tenía el semáforo de A?",
        reason="Puede cambiar la prioridad.",
        answer_kind="choice",
        options=("Rojo", "Verde", "No se sabe"),
    )

    with pytest.raises(ValueError, match="cannot carry questions"):
        InterviewPlan(status="ready", questions=(question,))
