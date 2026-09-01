"""Controlled discovery and staging of repository updates."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.parse import unquote, urlparse

REVISION = re.compile(r"^[0-9a-fA-F]{40,64}$")
COMPONENT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
STATE_VERSION = 1


class RepositoryUpdateError(Exception):
    """Raised when an update cannot be checked or staged safely."""


@dataclass(frozen=True)
class RepositoryTarget:
    component_id: str
    name: str
    role: str
    catalog_repository: str
    repository_url: str
    current_repository_url: str
    tracked_ref: str
    current_revision: str
    capability_ids: tuple[str, ...]
    activation: str
    next_action: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def split_repository_source(value: str) -> tuple[str, str]:
    """Return a cloneable repository URL and an explicit tracked Git ref."""
    source = value.strip().rstrip("/")
    parsed = urlparse(source)
    if parsed.username or parsed.password:
        raise RepositoryUpdateError(
            "repository URLs containing credentials are not allowed"
        )

    if parsed.scheme in {"http", "https"}:
        path = parsed.path.rstrip("/")
        github_parts = path.lstrip("/").split("/")
        if (
            parsed.netloc.lower() == "github.com"
            and len(github_parts) >= 4
            and github_parts[2] == "tree"
        ):
            repository_path = "/".join(github_parts[:2])
            branch = unquote("/".join(github_parts[3:]))
            if not branch:
                raise RepositoryUpdateError("repository tree URL lacks a branch")
            return (
                f"{parsed.scheme}://{parsed.netloc}/{repository_path}",
                f"refs/heads/{branch}",
            )
        gitlab_marker = "/-/tree/"
        if gitlab_marker in path:
            repository_path, branch = path.split(gitlab_marker, 1)
            if not branch:
                raise RepositoryUpdateError("repository tree URL lacks a branch")
            return (
                f"{parsed.scheme}://{parsed.netloc}{repository_path}",
                f"refs/heads/{unquote(branch)}",
            )

    return (source[:-4] if source.endswith(".git") else source, "HEAD")


def _repository_identity(value: str) -> str:
    repository, _ = split_repository_source(value)
    return repository.rstrip("/").removesuffix(".git").lower()


class RepositoryUpdateManager:
    """Check admitted repositories and prepare immutable candidate checkouts."""

    def __init__(
        self,
        registry: dict[str, Any],
        deployment_profile: dict[str, Any],
        *,
        workspace_root: str | Path,
        state_root: str | Path = ".qhpc/updates",
        git_timeout_seconds: float = 20.0,
    ) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        configured_state = Path(state_root).expanduser()
        self.state_root = (
            configured_state.resolve()
            if configured_state.is_absolute()
            else (self.workspace_root / configured_state).resolve()
        )
        if git_timeout_seconds <= 0:
            raise RepositoryUpdateError("Git timeout must be greater than zero")
        self.git_timeout_seconds = git_timeout_seconds
        self._thread_lock = threading.RLock()
        self.targets = self._build_targets(registry, deployment_profile)
        self._by_id = {target.component_id: target for target in self.targets}

    @staticmethod
    def _build_targets(
        registry: dict[str, Any],
        deployment_profile: dict[str, Any],
    ) -> tuple[RepositoryTarget, ...]:
        entries_by_repository: dict[str, list[dict[str, Any]]] = {}
        for entry in registry["spec"]["entries"]:
            entries_by_repository.setdefault(
                entry["catalog_repository"], []
            ).append(entry)

        targets: list[RepositoryTarget] = []
        for component in deployment_profile["spec"]["components"]:
            component_id = component["id"]
            if COMPONENT_ID.fullmatch(component_id) is None:
                raise RepositoryUpdateError(
                    f"invalid deployment component id: {component_id}"
                )
            catalog_repository = component["catalog_repository"]
            entries = entries_by_repository.get(catalog_repository, [])
            if not entries:
                raise RepositoryUpdateError(
                    f"component {component_id} has no admitted registry capability"
                )

            revisions = {
                entry["capability"]["metadata"]["repository"]["revision"]
                for entry in entries
            }
            if len(revisions) != 1:
                raise RepositoryUpdateError(
                    f"component {component_id} has inconsistent repository revisions"
                )
            release_sources = {
                entry["capability"]["metadata"]["repository"]["url"]
                for entry in entries
            }
            if len({_repository_identity(value) for value in release_sources}) != 1:
                raise RepositoryUpdateError(
                    f"component {component_id} has inconsistent release source URLs"
                )
            canonical_sources = {
                entry["capability"]["metadata"]["repository"].get(
                    "canonical_url",
                    entry["capability"]["metadata"]["repository"]["url"],
                )
                for entry in entries
            }
            if len({_repository_identity(value) for value in canonical_sources}) != 1:
                raise RepositoryUpdateError(
                    f"component {component_id} has inconsistent canonical "
                    "repository URLs"
                )

            profile_source = component["source"]["url"]
            repository_url, profile_ref = split_repository_source(profile_source)
            registry_url, registry_ref = split_repository_source(
                next(iter(canonical_sources))
            )
            if _repository_identity(repository_url) != _repository_identity(
                registry_url
            ):
                raise RepositoryUpdateError(
                    f"component {component_id} deployment and registry sources differ"
                )
            tracked_ref = (
                profile_ref if profile_ref != "HEAD" else registry_ref
            )
            role = component["role"]
            if role == "operation-provider":
                activation = "rebuild-required"
                next_action = "Rebuild and validate runtime before activation"
            elif role == "assistant-service":
                activation = "service-review-required"
                next_action = "Review corpus and restart service before activation"
            elif role == "data-service":
                activation = "data-review-required"
                next_action = "Review schema, provenance, and data access before activation"
            else:
                activation = "registry-review-required"
                next_action = "Review integration and republish registry before activation"

            targets.append(
                RepositoryTarget(
                    component_id=component_id,
                    name=component["name"],
                    role=role,
                    catalog_repository=catalog_repository,
                    repository_url=repository_url,
                    current_repository_url=next(iter(release_sources)),
                    tracked_ref=tracked_ref,
                    current_revision=next(iter(revisions)),
                    capability_ids=tuple(
                        sorted(
                            entry["capability"]["metadata"]["id"]
                            for entry in entries
                        )
                    ),
                    activation=activation,
                    next_action=next_action,
                )
            )
        return tuple(targets)

    @contextmanager
    def _state_lock(self) -> Iterator[None]:
        self.state_root.mkdir(parents=True, exist_ok=True)
        lock_path = self.state_root / ".state.lock"
        with lock_path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _load_state(self) -> dict[str, Any]:
        state_path = self.state_root / "state.json"
        if not state_path.exists():
            return {
                "version": STATE_VERSION,
                "checks": {},
                "staged": {},
            }
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RepositoryUpdateError(
                f"repository update state is invalid: {state_path}"
            ) from error
        if (
            not isinstance(state, dict)
            or state.get("version") != STATE_VERSION
            or not isinstance(state.get("checks"), dict)
            or not isinstance(state.get("staged"), dict)
        ):
            raise RepositoryUpdateError(
                f"repository update state has an unsupported format: {state_path}"
            )
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(state, indent=2, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.state_root,
            prefix="state.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        try:
            os.replace(temporary, self.state_root / "state.json")
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _git(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: float | None = None,
    ) -> str:
        environment = dict(os.environ)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        try:
            result = subprocess.run(
                ["git", *arguments],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=timeout_seconds or self.git_timeout_seconds,
                env=environment,
            )
        except FileNotFoundError as error:
            raise RepositoryUpdateError("Git is required for repository updates") from error
        except subprocess.TimeoutExpired as error:
            raise RepositoryUpdateError("Git repository operation timed out") from error
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            message = detail[-1][:500] if detail else "unknown Git error"
            raise RepositoryUpdateError(f"Git repository operation failed: {message}")
        return result.stdout.strip()

    def _remote_revision(self, target: RepositoryTarget) -> str:
        output = self._git(
            [
                "ls-remote",
                "--exit-code",
                target.repository_url,
                target.tracked_ref,
            ]
        )
        first_line = output.splitlines()[0] if output else ""
        revision = first_line.split(maxsplit=1)[0] if first_line else ""
        if REVISION.fullmatch(revision) is None:
            raise RepositoryUpdateError(
                f"remote ref {target.tracked_ref} did not resolve to a commit"
            )
        return revision.lower()

    def _check_target(self, target: RepositoryTarget) -> dict[str, Any]:
        checked_at = _timestamp()
        try:
            latest = self._remote_revision(target)
            error = None
        except RepositoryUpdateError as exception:
            latest = None
            error = str(exception)
        return {
            "base_revision": target.current_revision,
            "base_repository_url": target.current_repository_url,
            "repository_url": target.repository_url,
            "tracked_ref": target.tracked_ref,
            "latest_revision": latest,
            "checked_at": checked_at,
            "error": error,
        }

    def _target(self, component_id: str) -> RepositoryTarget:
        try:
            return self._by_id[component_id]
        except KeyError as error:
            raise RepositoryUpdateError(
                f"component is not admitted for repository updates: {component_id}"
            ) from error

    def _select_targets(
        self, component_ids: Sequence[str] | None
    ) -> tuple[RepositoryTarget, ...]:
        if not component_ids:
            return self.targets
        if len(component_ids) != len(set(component_ids)):
            raise RepositoryUpdateError("component selection contains duplicates")
        return tuple(self._target(component_id) for component_id in component_ids)

    def _relative_checkout(self, value: str | None) -> str | None:
        if not value:
            return None
        path = Path(value)
        try:
            return str(path.relative_to(self.workspace_root))
        except ValueError:
            return str(path)

    def _item(
        self,
        target: RepositoryTarget,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        check = state["checks"].get(target.component_id)
        if check and (
            check.get("base_revision") != target.current_revision
            or check.get("base_repository_url") != target.current_repository_url
            or check.get("repository_url") != target.repository_url
            or check.get("tracked_ref") != target.tracked_ref
        ):
            check = None
        staged = state["staged"].get(target.component_id)
        if staged and (
            staged.get("base_revision") != target.current_revision
            or staged.get("base_repository_url") != target.current_repository_url
            or staged.get("repository_url") != target.repository_url
            or staged.get("tracked_ref") != target.tracked_ref
        ):
            staged = None

        latest = check.get("latest_revision") if check else None
        error = check.get("error") if check else None
        if staged:
            status = "prepared"
        elif error:
            status = "error"
        elif latest and latest.lower() == target.current_revision.lower():
            status = "up-to-date"
        elif latest:
            status = "update-available"
        else:
            status = "not-checked"

        return {
            "component_id": target.component_id,
            "name": target.name,
            "role": target.role,
            "catalog_repository": target.catalog_repository,
            "repository_url": target.repository_url,
            "current_repository_url": target.current_repository_url,
            "tracked_ref": target.tracked_ref,
            "current_revision": target.current_revision,
            "latest_revision": latest,
            "checked_at": check.get("checked_at") if check else None,
            "status": status,
            "error": error,
            "capability_ids": list(target.capability_ids),
            "activation": target.activation,
            "next_action": target.next_action,
            "staged_revision": staged.get("candidate_revision") if staged else None,
            "staged_at": staged.get("staged_at") if staged else None,
            "checkout": self._relative_checkout(
                staged.get("checkout") if staged else None
            ),
        }

    def list(self) -> dict[str, Any]:
        with self._thread_lock, self._state_lock():
            state = self._load_state()
            return {
                "enabled": True,
                "generated_at": _timestamp(),
                "items": [self._item(target, state) for target in self.targets],
            }

    def check(
        self, component_ids: Sequence[str] | None = None
    ) -> dict[str, Any]:
        selected = self._select_targets(component_ids)
        if not selected:
            return self.list()
        with ThreadPoolExecutor(max_workers=min(4, len(selected))) as executor:
            checks = list(executor.map(self._check_target, selected))
        with self._thread_lock, self._state_lock():
            state = self._load_state()
            for target, result in zip(selected, checks):
                state["checks"][target.component_id] = result
            self._write_state(state)
            return {
                "enabled": True,
                "generated_at": _timestamp(),
                "items": [self._item(target, state) for target in self.targets],
            }

    def _verify_checkout(
        self,
        target: RepositoryTarget,
        checkout: Path,
        candidate_revision: str,
    ) -> None:
        if not (checkout / ".git").is_dir():
            raise RepositoryUpdateError(
                f"prepared checkout is not a Git repository: {checkout}"
            )
        origin = self._git(["-C", str(checkout), "remote", "get-url", "origin"])
        if _repository_identity(origin) != _repository_identity(
            target.repository_url
        ):
            raise RepositoryUpdateError(
                f"prepared checkout has an unexpected origin: {checkout}"
            )
        head = self._git(["-C", str(checkout), "rev-parse", "HEAD"]).lower()
        if head != candidate_revision.lower():
            raise RepositoryUpdateError(
                f"prepared checkout has an unexpected revision: {checkout}"
            )
        status = self._git(
            [
                "-C",
                str(checkout),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ]
        )
        if status:
            raise RepositoryUpdateError(
                f"prepared checkout contains local changes: {checkout}"
            )

    def _prepare_checkout(
        self,
        target: RepositoryTarget,
        candidate_revision: str,
    ) -> Path:
        destination = (
            self.state_root
            / "checkouts"
            / target.component_id
            / candidate_revision.lower()
        )
        if destination.exists():
            self._verify_checkout(target, destination, candidate_revision)
            return destination

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(prefix=".candidate-", dir=destination.parent)
        )
        try:
            self._git(["init", str(temporary)])
            self._git(
                [
                    "-C",
                    str(temporary),
                    "remote",
                    "add",
                    "origin",
                    target.repository_url,
                ]
            )
            self._git(
                [
                    "-C",
                    str(temporary),
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    target.tracked_ref,
                ],
                timeout_seconds=max(120.0, self.git_timeout_seconds),
            )
            fetched = self._git(
                ["-C", str(temporary), "rev-parse", "FETCH_HEAD"]
            ).lower()
            if fetched != candidate_revision.lower():
                raise RepositoryUpdateError(
                    "remote revision changed while preparing the update; check again"
                )
            self._git(
                [
                    "-C",
                    str(temporary),
                    "checkout",
                    "--detach",
                    "FETCH_HEAD",
                ]
            )
            self._verify_checkout(target, temporary, candidate_revision)
            os.replace(temporary, destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return destination

    def stage(
        self,
        component_id: str,
        candidate_revision: str | None = None,
    ) -> dict[str, Any]:
        target = self._target(component_id)
        check = self._check_target(target)
        if check["error"]:
            raise RepositoryUpdateError(check["error"])
        latest = check["latest_revision"]
        assert isinstance(latest, str)
        candidate = candidate_revision or latest
        if REVISION.fullmatch(candidate) is None:
            raise RepositoryUpdateError(
                "candidate revision must be a full Git commit hash"
            )
        candidate = candidate.lower()
        if candidate != latest.lower():
            raise RepositoryUpdateError(
                "candidate revision is no longer the tracked remote revision"
            )
        if candidate == target.current_revision.lower():
            raise RepositoryUpdateError(
                f"component {component_id} is already at the tracked revision"
            )

        checkout = self._prepare_checkout(target, candidate)
        staged = {
            "base_revision": target.current_revision,
            "base_repository_url": target.current_repository_url,
            "repository_url": target.repository_url,
            "tracked_ref": target.tracked_ref,
            "candidate_revision": candidate,
            "checkout": str(checkout),
            "staged_at": _timestamp(),
        }
        with self._thread_lock, self._state_lock():
            state = self._load_state()
            state["checks"][target.component_id] = check
            state["staged"][target.component_id] = staged
            self._write_state(state)
            return self._item(target, state)

    def discard(self, component_id: str) -> dict[str, Any]:
        """Release a prepared candidate without deleting its immutable cache."""
        target = self._target(component_id)
        with self._thread_lock, self._state_lock():
            state = self._load_state()
            state["staged"].pop(target.component_id, None)
            self._write_state(state)
            return self._item(target, state)
