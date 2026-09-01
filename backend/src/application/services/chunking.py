"""Deterministic chunkers that retain source-page evidence identities."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

from application.models.retrieval import Chunk
from domain.models.evidence import PageEvidence

_STRUCTURED_POLICY = "ordered-elements-header-table-note-atomic-v1"
_SEPARATOR = "\n\n"
_HEADER_KINDS = frozenset({"heading", "section_header", "title"})
_NOTE_KINDS = frozenset({"footnote", "note", "table_note"})


@dataclass(frozen=True, slots=True)
class _TextUnit:
    text: str
    evidence_ids: tuple[str, ...]
    kind: str
    atomic: bool = False


def chunk_fixed(pages: Sequence[PageEvidence], size: int, overlap: int) -> tuple[Chunk, ...]:
    """Cut the exact page text stream into overlapping character windows."""

    _validate_fixed_window(size, overlap)
    text = "".join(page.text for page in pages if page.text)
    if not text:
        return ()

    spans: list[tuple[int, int, str]] = []
    position = 0
    for page in pages:
        if not page.text:
            continue
        end = position + len(page.text)
        spans.append((position, end, page.evidence_id))
        position = end

    chunks: list[Chunk] = []
    step = size - overlap
    for start in range(0, len(text), step):
        end = min(start + size, len(text))
        chunk_text = text[start:end]
        evidence_ids = tuple(
            evidence_id
            for source_start, source_end, evidence_id in spans
            if source_start < end and source_end > start
        )
        chunks.append(
            _chunk(
                chunk_text,
                evidence_ids,
                strategy="fixed",
                parameters={
                    "overlap": overlap,
                    "page_join": "",
                    "policy": "character-window-v1",
                    "size": size,
                },
            )
        )
        if end == len(text):
            break
    return tuple(chunks)


def chunk_sections(pages: Sequence[PageEvidence], max_size: int) -> tuple[Chunk, ...]:
    """Pack ordered text while keeping table labels and immediate notes atomic."""

    _require_positive_int("max_size", max_size)

    units = _group_table_context(_source_units(pages))
    chunks: list[Chunk] = []
    pending: list[_TextUnit] = []

    def emit_pending() -> None:
        if not pending:
            return
        chunks.append(_structured_chunk(_join_units(pending), max_size))
        pending.clear()

    for unit in units:
        if unit.atomic:
            emit_pending()
            chunks.append(_structured_chunk(unit, max_size))
            continue

        if len(unit.text) > max_size:
            emit_pending()
            for start in range(0, len(unit.text), max_size):
                piece = _TextUnit(
                    text=unit.text[start : start + max_size],
                    evidence_ids=unit.evidence_ids,
                    kind=unit.kind,
                )
                chunks.append(_structured_chunk(piece, max_size))
            continue

        proposed_size = len(unit.text) if not pending else len(_SEPARATOR) + len(unit.text)
        if pending and len(_join_units(pending).text) + proposed_size > max_size:
            emit_pending()
        pending.append(unit)

    emit_pending()
    return tuple(chunks)


def _validate_fixed_window(size: int, overlap: int) -> None:
    _require_positive_int("size", size)
    _require_nonnegative_int("overlap", overlap)
    if not 0 <= overlap < size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")


def _source_units(pages: Sequence[PageEvidence]) -> tuple[_TextUnit, ...]:
    units: list[_TextUnit] = []
    for page in pages:
        if page.elements:
            units.extend(
                _TextUnit(element.text, (page.evidence_id,), _normalize_kind(element.kind))
                for element in page.elements
                if element.text
            )
        elif page.text:
            units.append(_TextUnit(page.text, (page.evidence_id,), "text"))
    return tuple(units)


def _group_table_context(units: Sequence[_TextUnit]) -> tuple[_TextUnit, ...]:
    grouped: list[_TextUnit] = []
    index = 0
    while index < len(units):
        unit = units[index]
        table_index: int | None = None
        if unit.kind == "table":
            table_index = index
        elif (
            unit.kind in _HEADER_KINDS
            and index + 1 < len(units)
            and units[index + 1].kind == "table"
        ):
            table_index = index + 1

        if table_index is None:
            grouped.append(unit)
            index += 1
            continue

        end = table_index + 1
        while end < len(units) and units[end].kind in _NOTE_KINDS:
            end += 1
        grouped.append(_as_atomic(_join_units(units[index:end])))
        index = end
    return tuple(grouped)


def _as_atomic(unit: _TextUnit) -> _TextUnit:
    return _TextUnit(unit.text, unit.evidence_ids, "table_group", atomic=True)


def _join_units(units: Sequence[_TextUnit]) -> _TextUnit:
    return _TextUnit(
        text=_SEPARATOR.join(unit.text for unit in units),
        evidence_ids=_ordered_evidence(units),
        kind="group",
        atomic=any(unit.atomic for unit in units),
    )


def _ordered_evidence(units: Sequence[_TextUnit]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(evidence_id for unit in units for evidence_id in unit.evidence_ids))


def _structured_chunk(unit: _TextUnit, max_size: int) -> Chunk:
    return _chunk(
        unit.text,
        unit.evidence_ids,
        strategy="sections",
        parameters={
            "max_size": max_size,
            "policy": _STRUCTURED_POLICY,
            "separator": _SEPARATOR,
        },
    )


def _chunk(
    text: str,
    evidence_ids: tuple[str, ...],
    *,
    strategy: str,
    parameters: Mapping[str, object],
) -> Chunk:
    payload = {
        "evidence_ids": evidence_ids,
        "parameters": parameters,
        "strategy": strategy,
        "text": text,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return Chunk(sha256(encoded).hexdigest(), text, evidence_ids)


def _normalize_kind(kind: str) -> str:
    return kind.strip().lower().replace("-", "_").replace(" ", "_")


def _require_positive_int(name: str, value: object) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _require_nonnegative_int(name: str, value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
