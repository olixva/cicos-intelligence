"""ASGI factory entry point that wires ``build_api`` with explicit kwargs.

uvicorn's ``--factory`` flag invokes the importable callable with no
arguments, which leaves every profile kwarg at ``None``. Without any
profile, every workflow factory short-circuits to ``None`` and
``build_api`` raises the aggregate-fail ``RuntimeError``. This module
exposes the factory with the local ``baseline`` profile wired in.

The return type is intentionally unannotated: ``build_api.__annotations__["return"]``
contains the literal token ``"return"`` which is not a valid identifier
in a type hint. Letting pyright infer ``FastAPI`` from the implementation
keeps the surface simple.
"""

from __future__ import annotations

from bootstrap import build_api


def app():
    """Return the local FastAPI app with the ``baseline`` profile."""

    return build_api(profile_name="baseline")