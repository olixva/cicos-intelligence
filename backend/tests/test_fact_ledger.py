from __future__ import annotations

from domain.models.claim import ClaimFact
from domain.services.fact_ledger import FactLedger


def _fact(value: str | None, *, actor: str | None = "A", text: str | None = None) -> ClaimFact:
    return ClaimFact("traffic_light", value, actor, text or f"señal={value}")


def test_conflicting_assertions_are_order_independent_and_not_usable_as_known() -> None:
    first = _fact("green", actor="A")
    second = _fact("red", actor="B")

    forward = FactLedger.from_facts((first, second)).resolve("traffic_light")
    reversed_ledger = FactLedger.from_facts((second, first)).resolve("traffic_light")

    assert forward == reversed_ledger
    assert forward is not None
    assert forward.status == "contradicted"
    assert forward.value is None
    assert forward.assertions == tuple(
        sorted((first, second), key=lambda x: (x.asserted_by or "", x.source_text))
    )


def test_unknown_assertion_does_not_become_false_or_overwrite_known_value() -> None:
    unknown = ClaimFact("one_vehicle_parked", None, None, "no consta si estaba aparcado")
    known = ClaimFact("one_vehicle_parked", "true", None, "estaba aparcado")

    state = FactLedger.from_facts((known, unknown)).resolve("one_vehicle_parked")

    assert state is not None
    assert state.status == "unknown"
    assert state.value is None


def test_identical_assertions_resolve_to_known_independent_of_order() -> None:
    first = _fact("green", actor="A", text="A: verde")
    second = _fact("green", actor="B", text="B: verde")

    left = FactLedger.from_facts((first, second)).resolve("traffic_light")
    right = FactLedger.from_facts((second, first)).resolve("traffic_light")

    assert left == right
    assert left is not None
    assert left.status == "known"
    assert left.value == "green"
