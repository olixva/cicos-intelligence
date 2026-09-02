import json
import shutil
from collections.abc import Mapping
from typing import Any, Literal

import pytest


def test_missing_container_engine_is_not_reported_as_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing Docker from PATH must keep the environment from being ready."""
    from infrastructure.adapters.inbound.cli.doctor import check_environment

    def missing_docker(command: str, mode: int = 0, path: str | None = None) -> str | None:
        del command, mode, path
        return None

    monkeypatch.setattr(shutil, "which", missing_docker)

    status = check_environment()

    assert status["containers_available"] is False
    assert status["ready"] is False


def test_unknown_operation_is_rejected_before_any_readiness_check() -> None:
    """The public helper must fail clearly even when called outside argparse."""
    from infrastructure.adapters.inbound.cli.doctor import check_environment

    with pytest.raises(ValueError, match="Unsupported doctor operation"):
        check_environment(operation="unsupported")  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    ("operation", "qdrant", "langfuse", "environment", "expected"),
    [
        ("retrieval", True, False, {}, True),
        ("retrieval", False, True, {}, False),
        (
            "evaluation",
            False,
            True,
            {"LANGFUSE_PUBLIC_KEY": "present", "LANGFUSE_SECRET_KEY": "present"},
            True,
        ),
        (
            "evaluation",
            True,
            True,
            {"LANGFUSE_PUBLIC_KEY": "present", "LANGFUSE_SECRET_KEY": " "},
            False,
        ),
        ("generation", False, False, {"OPENAI_API_KEY": "present"}, True),
        ("generation", True, True, {"OPENAI_API_KEY": ""}, False),
    ],
)
def test_readiness_depends_on_the_selected_operation(
    monkeypatch: pytest.MonkeyPatch,
    operation: Literal["retrieval", "evaluation", "generation"],
    qdrant: bool,
    langfuse: bool,
    environment: Mapping[str, str],
    expected: bool,
) -> None:
    """Each operation must require only its actual service and credential boundaries."""
    from infrastructure.adapters.inbound.cli import doctor

    def docker_path(command: str, mode: int = 0, path: str | None = None) -> str:
        del command, mode, path
        return "/usr/bin/docker"

    def available_engine(*, context: str, timeout: float) -> bool:
        del context, timeout
        return True

    def health(url: str, *, timeout: float) -> bool:
        del timeout
        return qdrant if "6333" in url else langfuse

    monkeypatch.setattr(shutil, "which", docker_path)
    monkeypatch.setattr(doctor, "_container_engine_is_available", available_engine)
    monkeypatch.setattr(doctor, "_service_is_healthy", health)

    status = doctor.check_environment(operation=operation, environ=environment)

    assert status["ready"] is expected
    assert status["operation"] == operation


def test_default_services_check_requires_engine_and_both_health_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reachable process on one port must not hide a failed local dependency."""
    from infrastructure.adapters.inbound.cli import doctor

    def docker_path(command: str, mode: int = 0, path: str | None = None) -> str:
        del command, mode, path
        return "/usr/bin/docker"

    def available_engine(*, context: str, timeout: float) -> bool:
        del context, timeout
        return True

    def health(url: str, *, timeout: float) -> bool:
        del timeout
        return "6333" in url

    monkeypatch.setattr(shutil, "which", docker_path)
    monkeypatch.setattr(doctor, "_container_engine_is_available", available_engine)
    monkeypatch.setattr(doctor, "_service_is_healthy", health)

    status = doctor.check_environment()

    assert status["containers_available"] is True
    assert status["qdrant_healthy"] is True
    assert status["langfuse_healthy"] is False
    assert status["ready"] is False


def test_container_engine_check_uses_the_active_docker_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor must not revive a retired named Docker context."""
    from infrastructure.adapters.inbound.cli import doctor

    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> object:
        calls.append(command)
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(doctor.subprocess, "run", run)

    assert doctor._container_engine_is_available(context="colima-allianz", timeout=1)
    assert calls == [["docker", "info", "--format", "{{.ServerVersion}}"]]


def test_service_health_treats_timeout_as_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stalled health endpoint must fail closed within the configured timeout."""
    from infrastructure.adapters.inbound.cli import doctor

    def timeout(*args: Any, **kwargs: Any) -> None:
        raise TimeoutError

    monkeypatch.setattr(doctor.urllib.request, "urlopen", timeout)

    status = doctor.check_environment(operation="retrieval", timeout=0.01)

    assert status["qdrant_healthy"] is False
    assert status["ready"] is False


def test_doctor_cli_returns_json_and_nonzero_without_printing_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Doctor output must be machine-readable and contain no credential values."""
    from infrastructure.adapters.inbound.cli import doctor
    from infrastructure.adapters.inbound.cli.main import main

    private_value = "must-never-appear"

    def unavailable(**kwargs: Any) -> dict[str, bool | str]:
        return {
            "operation": "evaluation",
            "containers_available": True,
            "qdrant_healthy": True,
            "langfuse_healthy": True,
            "langfuse_credentials_available": False,
            "provider_credentials_available": False,
            "ready": False,
        }

    monkeypatch.setattr(doctor, "check_environment", unavailable)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", private_value)

    result = main(["doctor", "--operation", "evaluation"])

    captured = capsys.readouterr()
    assert result == 1
    assert json.loads(captured.out)["ready"] is False
    assert private_value not in captured.out
    assert private_value not in captured.err
    assert captured.err == ""
