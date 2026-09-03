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


def test_lets_through_claim_with_incidental_tiempo_mention() -> None:
    """Caso real reportado: el texto contiene 'no consigue detenerse a
    tiempo' en un relato de alcance trasero. La palabra 'tiempo' no
    debe disparar el guardrail de clima si el texto es claramente un
    relato de siniestro."""
    text = (
        "El vehículo A está detenido ante un semáforo en rojo cuando el "
        "vehículo B no consigue detenerse a tiempo y choca por detrás "
        "contra el vehículo A. Ambos conductores afirman que estaban "
        "prestando atención, pero el conductor del vehículo B insiste en "
        "que el vehículo A frenó de forma repentina."
    )
    assert guardrail_message(text) is None


def test_lets_through_claim_with_parte_mention() -> None:
    """'parte amistoso' es vocabulario de CIDE, no debe bloquearse."""
    text = (
        "Siniestro entre dos vehículos en un cruce. Se firmó parte "
        "amistoso. ¿Quién es culpable según el manual CIDE?"
    )
    assert guardrail_message(text) is None


def test_still_rejects_weather_when_no_claim_vocabulary() -> None:
    """Una pregunta puramente meteorológica con un solo vocablo de
    relato no debe saltarse el guardrail — la heurística exige 2+
    matches para evitar falsos positivos."""
    # 'tiempo' + 'semaforo' (1 solo match de claim vocabulary)
    # En realidad tiene 2: semáforo (1) + ¿no aparece vehículo? → 1 solo.
    # Ajusto el texto para que tenga 1 match → debería bloquear.
    assert guardrail_message("¿qué tiempo hace en el semáforo?") is not None
