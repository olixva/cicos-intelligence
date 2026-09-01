"""Deterministic chunkers that retain source-page evidence identities."""

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

from application.models.retrieval import Chunk
from domain.models.evidence import PageEvidence

_STRUCTURED_POLICY = "ordered-section-tables-observation-block-atomic-v2"
_SEPARATOR = "\n\n"
_HEADER_KINDS = frozenset({"heading", "section_header", "title"})
_NOTE_KINDS = frozenset({"footnote", "note", "table_note"})


@dataclass(frozen=True, slots=True)
class _TextUnit:
    text: str
    evidence_ids: tuple[str, ...]
    kind: str
    section: str | None
    content_layer: str
    element_ids: tuple[str, ...]
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
                    section=unit.section,
                    content_layer=unit.content_layer,
                    element_ids=unit.element_ids,
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
            for element in page.elements:
                kind = _normalize_kind(element.kind)
                content_layer = _normalize_kind(element.content_layer)
                if not element.text or kind == "page_footer":
                    continue
                if content_layer == "furniture" and kind not in _NOTE_KINDS:
                    continue
                units.append(
                    _TextUnit(
                        text=element.text,
                        evidence_ids=(page.evidence_id,),
                        kind=kind,
                        section=element.section,
                        content_layer=content_layer,
                        element_ids=(element.element_id,),
                    )
                )
        elif page.text:
            units.append(
                _TextUnit(
                    text=page.text,
                    evidence_ids=(page.evidence_id,),
                    kind="text",
                    section=None,
                    content_layer="body",
                    element_ids=(),
                )
            )
    return tuple(units)


def _group_table_context(units: Sequence[_TextUnit]) -> tuple[_TextUnit, ...]:
    grouped: list[_TextUnit] = []
    index = 0
    while index < len(units):
        unit = units[index]
        table_index = index
        context: list[_TextUnit] = []
        if unit.kind == "table":
            context.append(unit)
            table_index += 1
        elif (
            unit.kind in _HEADER_KINDS
            and index + 1 < len(units)
            and units[index + 1].kind == "table"
            and _same_context(unit.section, unit.evidence_ids, units[index + 1])
        ):
            context.extend((unit, units[index + 1]))
            table_index += 2

        if not context:
            grouped.append(unit)
            index += 1
            continue

        anchor_section = context[0].section
        context_evidence = _ordered_evidence(context)
        while (
            table_index < len(units)
            and units[table_index].kind == "table"
            and _same_context(anchor_section, context_evidence, units[table_index])
        ):
            context.append(units[table_index])
            context_evidence = _ordered_evidence(context)
            table_index += 1

        while (
            table_index < len(units)
            and units[table_index].kind in _NOTE_KINDS
            and _same_context(anchor_section, context_evidence, units[table_index])
        ):
            context.append(units[table_index])
            context_evidence = _ordered_evidence(context)
            table_index += 1

        if (
            table_index < len(units)
            and units[table_index].kind == "text"
            and _is_note_marker(units[table_index].text)
            and _same_context(anchor_section, context_evidence, units[table_index])
        ):
            context.append(units[table_index])
            context_evidence = _ordered_evidence(context)
            table_index += 1
            while (
                table_index < len(units)
                and units[table_index].kind in ({"text"} | _NOTE_KINDS)
                and _same_context(anchor_section, context_evidence, units[table_index])
            ):
                context.append(units[table_index])
                context_evidence = _ordered_evidence(context)
                table_index += 1

        grouped.append(_as_atomic(_join_units(context)))
        index = table_index
    return tuple(grouped)


def _as_atomic(unit: _TextUnit) -> _TextUnit:
    return _TextUnit(
        text=unit.text,
        evidence_ids=unit.evidence_ids,
        kind="table_group",
        section=unit.section,
        content_layer=unit.content_layer,
        element_ids=unit.element_ids,
        atomic=True,
    )


def _join_units(units: Sequence[_TextUnit]) -> _TextUnit:
    return _TextUnit(
        text=_SEPARATOR.join(unit.text for unit in units),
        evidence_ids=_ordered_evidence(units),
        kind="group",
        section=_shared_value(tuple(unit.section for unit in units)),
        content_layer=_shared_value(tuple(unit.content_layer for unit in units)) or "mixed",
        element_ids=tuple(
            dict.fromkeys(element_id for unit in units for element_id in unit.element_ids)
        ),
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


def _same_context(
    anchor_section: str | None,
    context_evidence: tuple[str, ...],
    candidate: _TextUnit,
) -> bool:
    if anchor_section is not None:
        return candidate.section == anchor_section
    return candidate.section is None and bool(
        set(context_evidence).intersection(candidate.evidence_ids)
    )


def _is_note_marker(text: str) -> bool:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", text).casefold()
        if not unicodedata.combining(character)
    )
    return re.fullmatch(r"[\W_]*(?:observacion(?:es)?|nota(?:s)?)[\W_]*", normalized) is not None


def _shared_value(values: tuple[str | None, ...]) -> str | None:
    unique = set(values)
    if len(unique) == 1:
        return next(iter(unique))
    return None


def _require_positive_int(name: str, value: object) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _require_nonnegative_int(name: str, value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
