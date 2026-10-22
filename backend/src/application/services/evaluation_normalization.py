"""Small normalizers for per-case evaluation outcomes."""

from collections.abc import Mapping


def evaluation_error(evaluation: Mapping[str, object]) -> str | None:
    """Return an evaluator error if present, even when nested in its result."""

    error = evaluation.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if error is not None:
        return "evaluator returned a malformed error value"
    return None
