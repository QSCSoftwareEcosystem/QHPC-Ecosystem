"""Separate task worker and deployment-bound runner admission."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from threading import Event
from time import perf_counter
from typing import Any, Iterable, Protocol

from .contract import validate_contract_data
from .engine import (
    Runner,
    TaskRejectedError,
    TaskRequest,
    TaskResult,
    WorkflowEngine,
)
from .registry import registry_entries


@dataclass(frozen=True)
class TargetSubmission:
    handle: str
    state: str = "queued"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TargetStatus:
    state: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AsyncRunner(Protocol):
    def submit(self, request: TaskRequest) -> TargetSubmission: ...

    def poll(self, request: TaskRequest, handle: str) -> TargetStatus: ...

    def collect(self, request: TaskRequest, handle: str) -> TaskResult: ...

    def cancel(self, request: TaskRequest, handle: str) -> None: ...


class TargetExecutionError(RuntimeError):
    """An admitted external target reported a terminal execution failure."""


class _RegistryAdmission:
    """Validate operation and runtime identity against one registry snapshot."""

    def __init__(self, registry: dict[str, Any]) -> None:
        validate_contract_data("registry", registry)
        self._operations: dict[tuple[str, str, str], tuple[str, str]] = {}
        for entry in registry_entries(registry):
            capability = entry["capability"]
            metadata = capability["metadata"]
            for operation in capability["spec"].get("operations", []):
                runtime = operation["runtime"]
                self._operations[
                    (metadata["id"], metadata["version"], operation["id"])
                ] = (runtime["reference"], runtime["digest"])

    def _admit(self, request: TaskRequest) -> None:
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


class RegistryBoundRunner(_RegistryAdmission):
    """Permit only local operations published in one registry snapshot."""

    def __init__(self, delegate: Runner, registry: dict[str, Any]) -> None:
        super().__init__(registry)
        self.delegate = delegate

    def execute(self, request: TaskRequest) -> TaskResult:
        self._admit(request)
        return self.delegate.execute(request)


class RegistryBoundAsyncRunner(_RegistryAdmission):
    """Apply the same immutable registry admission to an external runner."""

    def __init__(self, delegate: AsyncRunner, registry: dict[str, Any]) -> None:
        super().__init__(registry)
        self.delegate = delegate
        self.execution_targets = getattr(delegate, "execution_targets", None)
        self.execution_classes = getattr(delegate, "execution_classes", None)

    def submit(self, request: TaskRequest) -> TargetSubmission:
        self._admit(request)
        return self.delegate.submit(request)

    def poll(self, request: TaskRequest, handle: str) -> TargetStatus:
        self._admit(request)
        return self.delegate.poll(request, handle)

    def collect(self, request: TaskRequest, handle: str) -> TaskResult:
        self._admit(request)
        return self.delegate.collect(request, handle)

    def cancel(self, request: TaskRequest, handle: str) -> None:
        self._admit(request)
        self.delegate.cancel(request, handle)

    def finalize(self, request: TaskRequest, *, succeeded: bool) -> None:
        self._admit(request)
        finalize = getattr(self.delegate, "finalize", None)
        if finalize is not None:
            finalize(request, succeeded=succeeded)


class Worker:
    """Poll persistent task leases and execute them outside the API process."""

    def __init__(
        self,
        engine: WorkflowEngine,
        runner: Runner,
        *,
        poll_interval_seconds: float = 1.0,
        lease_seconds: int = 300,
        worker_id: str | None = None,
        execution_targets: Iterable[str] = ("local-development",),
        execution_classes: Iterable[str] = ("interactive-local",),
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("worker poll interval must be greater than zero")
        if lease_seconds <= 0:
            raise ValueError("worker lease duration must be greater than zero")
        self.engine = engine
        self.runner = runner
        self.poll_interval_seconds = poll_interval_seconds
        self.lease_seconds = lease_seconds
        self.execution_targets = frozenset(execution_targets)
        if not self.execution_targets:
            raise ValueError("worker must admit at least one execution target")
        self.execution_classes = frozenset(execution_classes)
        if not self.execution_classes:
            raise ValueError("worker must admit at least one execution class")
        self.worker_id = worker_id or "local-" + uuid.uuid4().hex
        self.engine.register_worker(
            self.worker_id,
            kind="local",
            metadata={"execution": "synchronous"},
        )

    def run_once(self) -> bool:
        self.engine.heartbeat_worker(self.worker_id)
        return self.engine.run_once(
            self.runner,
            lease_seconds=self.lease_seconds,
            worker_id=self.worker_id,
            execution_targets=self.execution_targets,
            execution_classes=self.execution_classes,
        )

    def drain(self) -> int:
        return self.engine.run_until_idle(
            self.runner,
            lease_seconds=self.lease_seconds,
            worker_id=self.worker_id,
            execution_targets=self.execution_targets,
            execution_classes=self.execution_classes,
        )

    def run_forever(self, stop_event: Event) -> int:
        processed = 0
        try:
            while not stop_event.is_set():
                if self.run_once():
                    processed += 1
                else:
                    stop_event.wait(self.poll_interval_seconds)
        finally:
            self.engine.heartbeat_worker(self.worker_id, state="offline")
        return processed


class AsyncWorker:
    """Reconcile durable target handles one bounded transition at a time."""

    def __init__(
        self,
        engine: WorkflowEngine,
        runner: AsyncRunner,
        *,
        poll_interval_seconds: float = 1.0,
        lease_seconds: int = 300,
        worker_id: str | None = None,
        execution_targets: Iterable[str] | None = None,
        execution_classes: Iterable[str] | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("worker poll interval must be greater than zero")
        if lease_seconds <= 0:
            raise ValueError("worker lease duration must be greater than zero")
        self.engine = engine
        self.runner = runner
        self.poll_interval_seconds = poll_interval_seconds
        self.lease_seconds = lease_seconds
        selected_targets = execution_targets
        if selected_targets is None:
            selected_targets = getattr(runner, "execution_targets", None)
        self.execution_targets = (
            frozenset(selected_targets) if selected_targets is not None else None
        )
        selected_classes = execution_classes
        if selected_classes is None:
            selected_classes = getattr(runner, "execution_classes", None)
        self.execution_classes = (
            frozenset(selected_classes) if selected_classes is not None else None
        )
        self.worker_id = worker_id or "target-" + uuid.uuid4().hex
        self.engine.register_worker(
            self.worker_id,
            kind="target",
            metadata={"execution": "asynchronous"},
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((perf_counter() - started) * 1000))

    def _finalize(
        self,
        lease,
        request: TaskRequest,
        *,
        succeeded: bool,
    ) -> None:
        finalize = getattr(self.runner, "finalize", None)
        if finalize is None:
            return
        started = perf_counter()
        try:
            finalize(request, succeeded=succeeded)
        except Exception as error:
            self.engine.record_stage(
                lease,
                "worker.finalize",
                self._elapsed_ms(started),
                details={"error": str(error), "succeeded": succeeded},
            )

    def _fail(self, lease, request: TaskRequest, error: Exception) -> None:
        self._finalize(lease, request, succeeded=False)
        self.engine.fail_task(lease, error)

    def _cancel(self, lease, request: TaskRequest, handle: str) -> None:
        started = perf_counter()
        try:
            self.runner.cancel(request, handle)
        except Exception as error:
            self.engine.record_stage(
                lease,
                "worker.cancel",
                self._elapsed_ms(started),
                details={"error": str(error)},
            )
            self.engine.release_lease(lease)
            return
        self.engine.record_stage(lease, "worker.cancel", self._elapsed_ms(started))
        self._finalize(lease, request, succeeded=False)
        self.engine.mark_attempt_canceled(lease, details={"target_handle": handle})

    def _collect(self, lease, request: TaskRequest, handle: str) -> None:
        started = perf_counter()
        result = self.runner.collect(request, handle)
        self.engine.record_stage(lease, "worker.collect", self._elapsed_ms(started))
        self.engine.record_reported_stages(lease, result.metadata)
        self._finalize(lease, request, succeeded=True)
        self.engine.complete_task(lease, result)

    def run_once(self) -> bool:
        self.engine.heartbeat_worker(self.worker_id)
        lease = self.engine.claim_task(
            self.worker_id,
            lease_seconds=self.lease_seconds,
            execution_targets=self.execution_targets,
            execution_classes=self.execution_classes,
        )
        if lease is None:
            return False
        request = self.engine.task_request(lease)
        try:
            current_state = self.engine.attempt_state(lease)
            if current_state == "cancel_requested" and lease.target_handle:
                self._cancel(lease, request, lease.target_handle)
                return True
            if current_state == "cancel_requested":
                self.engine.mark_attempt_canceled(
                    lease, details={"reason": "canceled-before-target-submission"}
                )
                return True

            if not lease.target_handle:
                self.engine.mark_submitting(lease)
                started = perf_counter()
                submission = self.runner.submit(request)
                self.engine.record_stage(
                    lease, "worker.submit", self._elapsed_ms(started)
                )
                state = self.engine.record_submission(
                    lease,
                    target_handle=submission.handle,
                    target_state=submission.state,
                    metadata=submission.metadata,
                )
                if state == "cancel_requested":
                    self._cancel(lease, request, submission.handle)
                elif submission.state == "succeeded":
                    self._collect(lease, request, submission.handle)
                elif submission.state in {"failed", "canceled"}:
                    self._fail(
                        lease,
                        request,
                        TargetExecutionError(
                            "target submission recovered terminal state "
                            f"{submission.state}: {submission.handle}"
                        ),
                    )
                else:
                    self.engine.release_lease(lease)
                return True

            started = perf_counter()
            status = self.runner.poll(request, lease.target_handle)
            self.engine.record_stage(lease, "worker.poll", self._elapsed_ms(started))
            self.engine.record_target_status(
                lease,
                target_state=status.state,
                metadata=status.metadata,
            )
            if status.state == "succeeded":
                self._collect(lease, request, lease.target_handle)
            elif status.state == "failed":
                self._fail(
                    lease,
                    request,
                    TargetExecutionError(
                        f"target execution failed: {lease.target_handle}"
                    ),
                )
            elif status.state == "canceled":
                self._fail(
                    lease,
                    request,
                    TargetExecutionError(
                        f"target execution was canceled: {lease.target_handle}"
                    ),
                )
            else:
                self.engine.release_lease(lease)
        except Exception as error:
            self._fail(lease, request, error)
        return True

    def run_forever(self, stop_event: Event) -> int:
        transitions = 0
        try:
            while not stop_event.is_set():
                if self.run_once():
                    transitions += 1
                stop_event.wait(self.poll_interval_seconds)
        finally:
            self.engine.heartbeat_worker(self.worker_id, state="offline")
        return transitions
