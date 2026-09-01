"""Pure grounding rules for document answers."""

from collections.abc import Sequence

from application.models.query import AnswerBlock, ContextEvidence, QuestionAnswer


def validate_grounded_answer(
    answer: QuestionAnswer, context: Sequence[ContextEvidence]
) -> QuestionAnswer:
    """Remove unsupported citations and downgrade any affected factual answer."""

    allowed_ids = {item.evidence_id for item in context}
    validated: list[AnswerBlock] = []
    rejected = False
    for block in answer.blocks:
        supported_ids = tuple(
            evidence_id for evidence_id in block.evidence_ids if evidence_id in allowed_ids
        )
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
