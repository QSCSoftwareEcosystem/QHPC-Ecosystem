from __future__ import annotations

from pathlib import Path

import pytest

from qhpc_ecosystem.databucket_stack import (
    DatabucketCredentials,
    DatabucketStackError,
    GarageStack,
)
from qhpc_ecosystem.slurm import CommandResult


def _checkout(tmp_path: Path, *, with_env: bool = True) -> Path:
    checkout = tmp_path / "databucket"
    checkout.mkdir()
    (checkout / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    if with_env:
        (checkout / ".env").write_text("GARAGE_ADMIN_TOKEN=x\n", encoding="utf-8")
    return checkout


def _garage_args(command: list[str]) -> list[str] | None:
    if "/garage" not in command:
        return None
    return command[command.index("/garage") + 1 :]


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.bucket_exists = False
        self.status_output = "Healthy nodes:\n"

    def __call__(self, command: list[str]) -> CommandResult:
        self.calls.append(list(command))
        args = _garage_args(command)
        if args is not None:
            if args[:1] == ["status"]:
                return CommandResult(0, self.status_output)
            if args[:2] == ["bucket", "info"]:
                return CommandResult(0 if self.bucket_exists else 1, "")
            if args[:2] == ["bucket", "create"]:
                self.bucket_exists = True
                return CommandResult(0, "")
            if args[:2] == ["key", "create"]:
                return CommandResult(0, "")
            if args[:2] == ["bucket", "allow"]:
                return CommandResult(0, "")
            if args[:2] == ["key", "info"]:
                return CommandResult(
                    0,
                    "Key ID: GKx-access-key\nSecret key: super-secret\n",
                )
            if args[:2] == ["layout", "assign"]:
                return CommandResult(0, "")
            if args[:2] == ["layout", "apply"]:
                return CommandResult(0, "")
            raise AssertionError(f"unexpected garage args: {args}")
        if "up" in command:
            return CommandResult(0, "")
        if "down" in command:
            return CommandResult(0, "")
        raise AssertionError(f"unexpected command: {command}")


def test_prepare_requires_checkout_directory(tmp_path: Path) -> None:
    stack = GarageStack(tmp_path / "missing")
    with pytest.raises(DatabucketStackError, match="checkout not found"):
        stack.prepare()


def test_prepare_requires_env_file(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path, with_env=False)
    stack = GarageStack(checkout)
    with pytest.raises(DatabucketStackError, match="scripts/setup.sh"):
        stack.prepare()


def test_status_reflects_garage_reachability(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    runner = FakeRunner()
    stack = GarageStack(checkout, runner=runner)
    assert stack.status() is True


def test_ensure_project_creates_bucket_and_key_when_missing(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    runner = FakeRunner()
    stack = GarageStack(checkout, runner=runner)

    credentials = stack.ensure_project("materials-db")

    assert credentials == DatabucketCredentials(
        endpoint="http://127.0.0.1:3900",
        region="garage",
        bucket="proj-materials-db",
        access_key_id="GKx-access-key",
        secret_access_key="super-secret",
    )
    create_calls = [
        call for call in runner.calls if _garage_args(call) == ["bucket", "create", "proj-materials-db"]
    ]
    assert len(create_calls) == 1


def test_ensure_project_is_idempotent_when_bucket_exists(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    runner = FakeRunner()
    runner.bucket_exists = True
    stack = GarageStack(checkout, runner=runner)

    stack.ensure_project("materials-db")

    assert not any(
        (_garage_args(call) or [None])[0] == "create"
        for call in runner.calls
        if _garage_args(call) and _garage_args(call)[:1] == ["bucket"]
    )


def test_ensure_project_rejects_invalid_project_name(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    stack = GarageStack(checkout, runner=FakeRunner())
    with pytest.raises(DatabucketStackError, match="invalid databucket project name"):
        stack.ensure_project("Not Valid!")


def test_ensure_layout_assigns_when_no_role_assigned(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    runner = FakeRunner()
    runner.status_output = (
        "NO ROLE ASSIGNED\n"
        "==== HEALTHY NODES ====\n"
        "ID       Hostname  Address\n"
        "abc123   garage    10.0.0.2:3901\n"
    )
    stack = GarageStack(checkout, runner=runner)

    stack.ensure_layout()

    assign_calls = [
        call for call in runner.calls if _garage_args(call) and _garage_args(call)[:2] == ["layout", "assign"]
    ]
    assert assign_calls
    assert assign_calls[0][-1] == "abc123"


def test_stop_runs_compose_down(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    runner = FakeRunner()
    stack = GarageStack(checkout, runner=runner)

    stack.stop()

    assert any("down" in call for call in runner.calls)
