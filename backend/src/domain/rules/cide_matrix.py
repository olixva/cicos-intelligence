"""Safe lookup over a reviewed CIDE matrix; never infer missing prerequisites."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from domain.models.claim import MatrixCell
from domain.models.decision import MatrixLookup

_PARTIES = frozenset({"A", "B"})


@dataclass(frozen=True, slots=True)
class MatrixException:
    """One of the four observations printed under the table.

    They read «A2 + B4 = Culpable B, salvo que el A abra la puerta»: an
    attribution that a second fact can withdraw. The trigger lives in the signed
    artifact, not here, so a reviewer reads what the system will decide.
    """

    note_id: str
    text: str
    #: 1-based ``(a, b)`` positions the observation governs.
    positions: tuple[tuple[int, int], ...]
    #: Fact that decides whether the exception applies, e.g. ``door_opened_by``.
    fact: str
    #: Party whose action triggers the exception.
    actor: str
    #: Party the table blames while the exception does not hold.
    liable_unless_exception: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.actor not in _PARTIES or self.liable_unless_exception not in _PARTIES:
            raise ValueError("matrix exception actor and liable party must be A or B")
        if not self.positions:
            raise ValueError("a matrix exception must govern at least one position")


@dataclass(frozen=True, slots=True)
class MatrixDecision:
    """What the reviewed table says, including when it says nothing."""

    status: Literal[
        "attributes",  # la tabla atribuye la responsabilidad
        "no_attribution",  # celda «-»: la tabla no atribuye para ese par
        "exception_applies",  # observación cumplida: la atribución decae
        "needs_exception_fact",  # falta el hecho que decide la observación
        "undetermined",  # sin casillas declaradas, sin celda o sin requisitos
    ]
    liable_party: str | None = None
    cell: MatrixCell | None = None
    evidence_ids: tuple[str, ...] = ()
    exception_text: str | None = None
    missing_fact: str | None = None


def lookup_matrix(
    cells: Mapping[tuple[int, int], MatrixCell],
    *,
    a: int | None,
    b: int | None,
    prerequisites_confirmed: bool,
) -> MatrixLookup:
    """Return a cell only after explicit prerequisites and both table positions exist."""
    if not prerequisites_confirmed or a is None or b is None:
        return MatrixLookup(status="undetermined", cell=None)
    cell = cells.get((a, b))
    return (
        MatrixLookup(status="resolved", cell=cell)
        if cell is not None
        else MatrixLookup(status="undetermined", cell=None)
    )


def lookup_daa_matrix(
    cells: Mapping[tuple[int, int], MatrixCell],
    *,
    facts: Mapping[str, str],
    prerequisites_confirmed: bool,
) -> MatrixLookup:
    """Resolve a matrix cell only from an explicit pair of D.A.A. box codes.

    The D.A.A. form has boxes 1–17; matrix label 0 is the reviewed local
    convention for an absent declaration. A free-text manoeuvre is never
    converted here: callers must provide the checked ``A<n>`` and ``B<n>``
    values and confirm that section 12 is the deciding D.A.A. evidence.
    """
    if facts.get("daa_section_12_only", "").strip().lower() != "true":
        return MatrixLookup(status="undetermined", cell=None)
    a = _daa_position(facts.get("daa_box_a"), party="A")
    b = _daa_position(facts.get("daa_box_b"), party="B")
    return lookup_matrix(cells, a=a, b=b, prerequisites_confirmed=prerequisites_confirmed)


def _daa_position(value: str | None, *, party: str) -> int | None:
    """Translate an explicit D.A.A. label into the one-based artifact position."""
    if value is None:
        return None
    code = value.strip().upper()
    if not code.startswith(party):
        return None
    try:
        index = int(code[1:])
    except ValueError:
        return None
    return index + 1 if 0 <= index <= 17 else None


def decide_from_daa_matrix(
    cells: Mapping[tuple[int, int], MatrixCell],
    *,
    exceptions: Sequence[MatrixException],
    facts: Mapping[str, str],
    prerequisites_confirmed: bool,
) -> MatrixDecision:
    """Turn an explicit D.A.A. pair into what the table actually supports.

    Four outcomes the caller must keep apart: the table attributes liability,
    the cell is a printed «-» and attributes nothing, an observation withdraws
    the attribution, or the observation cannot be settled because its deciding
    fact is missing. Only the first one may resolve a claim.
    """
    lookup = lookup_daa_matrix(cells, facts=facts, prerequisites_confirmed=prerequisites_confirmed)
    cell = lookup.cell
    if lookup.status != "resolved" or cell is None:
        return MatrixDecision(status="undetermined")

    outcome = cell.outcome.strip()
    if outcome.startswith("-"):
        return MatrixDecision(
            status="no_attribution", cell=cell, evidence_ids=tuple(cell.evidence_ids)
        )

    exception = _exception_for(exceptions, cell)
    if exception is not None:
        evidence = tuple(dict.fromkeys((*cell.evidence_ids, *exception.evidence_ids)))
        declared = facts.get(exception.fact, "").strip().upper()
        if not declared:
            return MatrixDecision(
                status="needs_exception_fact",
                cell=cell,
                evidence_ids=evidence,
                exception_text=exception.text,
                missing_fact=exception.fact,
            )
        if declared == exception.actor:
            # «Culpable B, salvo que el A abra la puerta»: si A la abre, el
            # manual no dice quién responde. No se completa por analogía.
            return MatrixDecision(
                status="exception_applies",
                cell=cell,
                evidence_ids=evidence,
                exception_text=exception.text,
            )
        return MatrixDecision(
            status="attributes",
            liable_party=exception.liable_unless_exception,
            cell=cell,
            evidence_ids=evidence,
            exception_text=exception.text,
        )

    party = outcome[0].upper()
    if party not in _PARTIES:
        return MatrixDecision(status="undetermined", cell=cell)
    return MatrixDecision(
        status="attributes",
        liable_party=party,
        cell=cell,
        evidence_ids=tuple(cell.evidence_ids),
    )


def _exception_for(
    exceptions: Sequence[MatrixException], cell: MatrixCell
) -> MatrixException | None:
    """An observation governs a cell only where the artifact says it does.

    A printed asterisk without a matching observation is a transcription gap,
    not licence to decide: the caller sees ``needs_exception_fact`` only for
    cells a reviewer actually annotated.
    """
    for exception in exceptions:
        if (cell.a, cell.b) in exception.positions:
            return exception
    return None
