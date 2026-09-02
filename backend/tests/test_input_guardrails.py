from application.services.input_guardrails import guardrail_message


def test_rejects_weather_request_before_document_workflow() -> None:
    message = guardrail_message("¿Qué tiempo hace hoy en Madrid?")
    assert message is not None
    assert "manual" in message.lower()


def test_rejects_insult_without_retrieving_document_evidence() -> None:
    message = guardrail_message("Eres un inútil")
    assert message is not None
    assert "respetuosa" in message.lower()


def test_keeps_domain_question_in_scope_for_normal_workflow() -> None:
    assert guardrail_message("¿Qué indica el manual sobre alcoholemia?") is None
