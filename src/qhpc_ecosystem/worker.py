"""Separate task worker and deployment-bound runner admission."""

from __future__ import annotations

from threading import Event
from typing import Any

from .contract import validate_contract_data
from .engine import (
    Runner,
    TaskRejectedError,
    TaskRequest,
    TaskResult,
    WorkflowEngine,
)
from .registry import registry_entries


class RegistryBoundRunner:
    """Permit only operations and runtimes published in one registry snapshot."""

    def __init__(self, delegate: Runner, registry: dict[str, Any]) -> None:
        validate_contract_data("registry", registry)
        self.delegate = delegate
        self._operations: dict[
            tuple[str, str, str], tuple[str, str]
        ] = {}
        for entry in registry_entries(registry):
            capability = entry["capability"]
            metadata = capability["metadata"]
            for operation in capability["spec"].get("operations", []):
                runtime = operation["runtime"]
                self._operations[
                    (metadata["id"], metadata["version"], operation["id"])
                ] = (runtime["reference"], runtime["digest"])

    def execute(self, request: TaskRequest) -> TaskResult:
        key = (
            request.capability_id,
            request.capability_version,
            request.operation_id,
        )
        runtime = self._operations.get(key)
        label = f"{key[0]}@{key[1]}/{key[2]}"
        if runtime is None:
            raise TaskRejectedError(
                f"operation is not admitted by the deployment registry: {label}"
            )
        if runtime != (request.runtime_reference, request.runtime_digest):
            raise TaskRejectedError(
                f"runtime does not match the deployment registry: {label}"
            )
        return self.delegate.execute(request)


class Worker:
    """Poll persistent task leases and execute them outside the API process."""

    def __init__(
        self,
        engine: WorkflowEngine,
        runner: Runner,
        *,
        poll_interval_seconds: float = 1.0,
        lease_seconds: int = 300,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("worker poll interval must be greater than zero")
        if lease_seconds <= 0:
            raise ValueError("worker lease duration must be greater than zero")
        self.engine = engine
        self.runner = runner
        self.poll_interval_seconds = poll_interval_seconds
        self.lease_seconds = lease_seconds

    def run_once(self) -> bool:
        return self.engine.run_once(self.runner, lease_seconds=self.lease_seconds)

    def drain(self) -> int:
        return self.engine.run_until_idle(
            self.runner, lease_seconds=self.lease_seconds
        )

    def run_forever(self, stop_event: Event) -> int:
        processed = 0
        while not stop_event.is_set():
            if self.run_once():
                processed += 1
            else:
                stop_event.wait(self.poll_interval_seconds)
        return processed
