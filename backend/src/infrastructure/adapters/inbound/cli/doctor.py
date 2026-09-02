"""Safe, bounded preflight checks for local services."""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Final, Literal

DoctorOperation = Literal["services", "containers", "retrieval", "evaluation", "generation", "all"]

_QDRANT_HEALTH_URL: Final = "http://127.0.0.1:6333/readyz"
_LANGFUSE_HEALTH_URL: Final = "http://127.0.0.1:3000/api/public/health"
_OPERATIONS: Final = frozenset(
    {"services", "containers", "retrieval", "evaluation", "generation", "all"}
)


def check_environment(
    operation: DoctorOperation = "services",
    *,
    environ: Mapping[str, str] | None = None,
    timeout: float = 2.0,
) -> dict[str, bool | str]:
    """Report only readiness booleans and public endpoint/context metadata.

    Credentials are checked for non-empty presence. Their values are never returned and no
    model or cloud-provider request is made.
    """
    if operation not in _OPERATIONS:
        raise ValueError(f"Unsupported doctor operation: {operation}")
    environment = os.environ if environ is None else environ
    docker_path = shutil.which("docker")
    check_containers = operation in {"services", "containers", "all"}
    check_qdrant = operation in {"services", "retrieval", "all"}
    check_langfuse = operation in {"services", "evaluation", "all"}
    docker_context = "active"

    containers_available: bool | str = "not_checked"
    if check_containers:
        containers_available = docker_path is not None and _container_engine_is_available(
            context=docker_context,
            timeout=timeout,
        )

    qdrant_healthy: bool | str = "not_checked"
    if check_qdrant:
        qdrant_healthy = _service_is_healthy(_QDRANT_HEALTH_URL, timeout=timeout)

    langfuse_healthy: bool | str = "not_checked"
    if check_langfuse:
        langfuse_healthy = _service_is_healthy(_LANGFUSE_HEALTH_URL, timeout=timeout)

    langfuse_credentials = _all_present(
        environment,
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    )
    provider_credentials = _all_present(environment, "OPENAI_API_KEY")
    ready_by_operation = {
        "services": (
            containers_available is True and qdrant_healthy is True and langfuse_healthy is True
        ),
        "containers": containers_available is True,
        "retrieval": qdrant_healthy is True,
        "evaluation": langfuse_healthy is True and langfuse_credentials,
        "generation": provider_credentials,
        "all": (
            containers_available is True
            and qdrant_healthy is True
            and langfuse_healthy is True
            and langfuse_credentials
            and provider_credentials
        ),
    }
    return {
        "operation": operation,
        "container_cli_available": docker_path is not None,
        "containers_available": containers_available,
        "docker_context": docker_context,
        "qdrant_healthy": qdrant_healthy,
        "langfuse_healthy": langfuse_healthy,
        "langfuse_credentials_available": langfuse_credentials,
        "provider_credentials_available": provider_credentials,
        "ready": ready_by_operation[operation],
    }


def _container_engine_is_available(*, context: str, timeout: float) -> bool:
    """Check Docker's active context without changing global configuration."""
    del context
    try:
        completed = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except OSError, subprocess.TimeoutExpired:
        return False
    return completed.returncode == 0


def _service_is_healthy(url: str, *, timeout: float) -> bool:
    """Require an HTTP 200 from a service's native health endpoint."""
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except OSError, TimeoutError, urllib.error.URLError:
        return False


def _all_present(environment: Mapping[str, str], *names: str) -> bool:
    return all(bool(environment.get(name, "").strip()) for name in names)
