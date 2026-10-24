"""Order-independent ledger for extracted claim assertions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from domain.models.claim import ClaimFact

FactStatus = Literal["known", "unknown", "contradicted"]


@dataclass(frozen=True, slots=True)
class FactState:
    """Resolved view of all assertions for one fact name."""

    name: str
    value: str | None
    status: FactStatus
    assertions: tuple[ClaimFact, ...]


@dataclass(frozen=True, slots=True)
class FactLedger:
    """Immutable, deterministic grouping of extracted fact assertions."""

    states: tuple[FactState, ...]

    @classmethod
    def from_facts(cls, facts: tuple[ClaimFact, ...]) -> FactLedger:
        grouped: dict[str, list[ClaimFact]] = {}
        for fact in facts:
            grouped.setdefault(fact.name, []).append(fact)

        states: list[FactState] = []
        for name in sorted(grouped):
            assertions = tuple(
                sorted(
                    grouped[name],
                    key=lambda item: (
                        item.asserted_by or "",
                        item.value or "",
                        item.source_text,
                    ),
                )
            )
            values = {
                fact.value.strip()
                for fact in assertions
                if fact.value is not None and fact.value.strip()
            }
            has_unknown = any(fact.value is None or not fact.value.strip() for fact in assertions)
            if len(values) > 1:
                status: FactStatus = "contradicted"
                value = None
            elif has_unknown:
                status = "unknown"
                value = None
            elif values:
                status = "known"
                value = next(iter(values))
            else:
                status = "unknown"
                value = None
            states.append(FactState(name, value, status, assertions))
        return cls(tuple(states))

    def resolve(self, name: str) -> FactState | None:
        """Return a field's state, or ``None`` when it was never extracted."""
        return next((state for state in self.states if state.name == name), None)

    def known_values(self) -> dict[str, str]:
        """Expose only single, explicit, noncontradictory values to rule engines."""
        return {
            state.name: state.value
            for state in self.states
            if state.status == "known" and state.value is not None
        }

    def contradictions(self) -> tuple[tuple[str, tuple[ClaimFact, ...]], ...]:
        """Return stable, attributed conflicting assertions."""
        return tuple(
            (state.name, state.assertions)
            for state in self.states
            if state.status == "contradicted"
        )
