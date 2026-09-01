"""Pure grounding rules for document answers."""

from collections.abc import Sequence

from application.models.query import AnswerBlock, ContextEvidence, QuestionAnswer


def validate_grounded_answer(
    answer: QuestionAnswer, context: Sequence[ContextEvidence]
) -> QuestionAnswer:
    """Remove unsupported citations and downgrade any affected factual answer."""

    delivered_groups = tuple(frozenset(item.evidence_ids) for item in context)
    validated: list[AnswerBlock] = []
    rejected = False
    for block in answer.blocks:
        claimed_ids = frozenset(block.evidence_ids)
        complete_groups = tuple(group for group in delivered_groups if group <= claimed_ids)
        supported_set: frozenset[str] = frozenset(
            evidence_id for group in complete_groups for evidence_id in group
        )
        supported_ids = tuple(item for item in block.evidence_ids if item in supported_set)
        if supported_ids != block.evidence_ids:
            rejected = True
        if not supported_ids:
            rejected = True
            continue
        validated.append(AnswerBlock(block.text, supported_ids))

    blocks = tuple(validated)
    if answer.status in ("answered", "partial"):
        if not blocks:
            return QuestionAnswer("insufficient_evidence", ())
        return QuestionAnswer("partial" if rejected else answer.status, blocks)
    return QuestionAnswer(answer.status, blocks)
