"""Safe repository inspection and draft scaffolding for EQO components.

This module deliberately stops before any repository code is built, imported,
or executed.  It resolves a public Git source to an immutable commit, inspects
only its tree metadata, and writes a reviewable integration draft.  A separate
isolated build-and-admission pipeline is required before a draft can publish a
capability or influence an active runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence
from urllib.parse import urlparse, urlunparse


REVISION = re.compile(r"^[0-9a-fA-F]{40,64}$")
REF_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ARTIFACT_TYPE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,127}@[1-9][0-9]*$")
TEMPLATES = {
    "python-operation",
    "container-cli",
    "compiler-transpiler",
    "simulator",
    "http-service",
}
DEFAULT_PUBLIC_GIT_HOSTS = frozenset({"github.com", "gitlab.com"})
MAX_DISCOVERED_FILES = 240


class ComponentOnboardingError(Exception):
    """Raised when an onboarding request cannot pass its non-execution gates."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_component_id(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (cleaned or "component")[:48]


def _safe_subdirectory(value: str) -> str:
    raw = value.strip().replace("\\", "/")
    if not raw or raw == ".":
        return ""
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or any(part in {"", "."} for part in path.parts):
        raise ComponentOnboardingError(
            "subdirectory must be a relative path contained in the repository"
        )
    return path.as_posix()


def _normalise_ref(value: str) -> str:
    ref = value.strip()
    if not ref:
        return "HEAD"
    if REVISION.fullmatch(ref):
        return ref.lower()
    if ref == "HEAD":
        return ref
    if ref.startswith("refs/heads/") or ref.startswith("refs/tags/"):
        candidate = ref.removeprefix("refs/heads/").removeprefix("refs/tags/")
        if not REF_NAME.fullmatch(candidate) or ".." in candidate or "//" in candidate:
            raise ComponentOnboardingError("repository ref has an unsupported format")
        return ref
    if not REF_NAME.fullmatch(ref) or ".." in ref or "//" in ref:
        raise ComponentOnboardingError("repository ref has an unsupported format")
    return f"refs/heads/{ref}"


def normalise_public_repository_url(
    value: str,
    *,
    allowed_hosts: frozenset[str] = DEFAULT_PUBLIC_GIT_HOSTS,
    allow_local_sources: bool = False,
) -> str:
    """Validate a public HTTPS source while refusing credentials and private paths."""
    raw = value.strip()
    parsed = urlparse(raw)
    if allow_local_sources and not parsed.scheme:
        local = Path(raw).expanduser().resolve()
        if not local.is_dir():
            raise ComponentOnboardingError("local test repository does not exist")
        return str(local)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ComponentOnboardingError(
            "repository URL must be an HTTPS URL from an admitted public Git host"
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ComponentOnboardingError(
            "repository URL must not contain credentials, query parameters, or fragments"
        )
    hostname = (parsed.hostname or "").lower()
    if hostname not in allowed_hosts:
        raise ComponentOnboardingError(
            "repository host is not admitted for public onboarding"
        )
    if parsed.port not in {None, 443}:
        raise ComponentOnboardingError("repository URL must use the default HTTPS port")
    path = parsed.path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) != 2 or any(part in {".", ".."} for part in parts):
        raise ComponentOnboardingError(
            "repository URL must identify exactly one owner and repository"
        )
    return urlunparse(("https", hostname, f"/{'/'.join(parts)}", "", "", ""))


class ComponentOnboardingManager:
    """Inspect public repositories and create immutable, non-executable drafts."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        state_root: str | Path = ".qhpc/component-onboarding",
        allowed_hosts: frozenset[str] = DEFAULT_PUBLIC_GIT_HOSTS,
        allow_local_sources: bool = False,
        git_timeout_seconds: float = 30.0,
    ) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        configured_state = Path(state_root).expanduser()
        self.state_root = (
            configured_state.resolve()
            if configured_state.is_absolute()
            else (self.workspace_root / configured_state).resolve()
        )
        self.allowed_hosts = allowed_hosts
        self.allow_local_sources = allow_local_sources
        if git_timeout_seconds <= 0:
            raise ComponentOnboardingError("Git timeout must be greater than zero")
        self.git_timeout_seconds = git_timeout_seconds
        self._lock = threading.RLock()

    def _git(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path | None = None,
    ) -> str:
        environment = dict(os.environ)
        # Inspection must neither prompt for nor inherit credentials.  The
        # accepted URL policy restricts the remote to public HTTPS hosts.
        environment.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "/bin/false",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
            }
        )
        try:
            result = subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", *arguments],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=self.git_timeout_seconds,
                env=environment,
            )
        except FileNotFoundError as error:
            raise ComponentOnboardingError("Git is required for repository onboarding") from error
        except subprocess.TimeoutExpired as error:
            raise ComponentOnboardingError("repository metadata inspection timed out") from error
        if result.returncode:
            detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "Git command failed"
            raise ComponentOnboardingError(f"repository metadata inspection failed: {detail}")
        return result.stdout

    def _state_path(self) -> Path:
        return self.state_root / "state.json"

    def _load_state(self) -> dict[str, Any]:
        path = self._state_path()
        if not path.is_file():
            return {"version": 1, "drafts": {}}
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ComponentOnboardingError("component onboarding state is invalid") from error
        if (
            not isinstance(state, dict)
            or state.get("version") != 1
            or not isinstance(state.get("drafts"), dict)
        ):
            raise ComponentOnboardingError("component onboarding state has an unsupported format")
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
            os.replace(temporary, self._state_path())
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _source_key(repository_url: str) -> str:
        return hashlib.sha256(repository_url.encode("utf-8")).hexdigest()[:24]

    def _resolve_revision(self, repository_url: str, requested_ref: str) -> str:
        lines = self._git(["ls-remote", "--refs", repository_url]).splitlines()
        advertised: dict[str, str] = {}
        for line in lines:
            parts = line.split("\t", 1)
            if len(parts) != 2 or not REVISION.fullmatch(parts[0]):
                continue
            advertised[parts[1]] = parts[0].lower()
        if requested_ref == "HEAD":
            head = self._git(["ls-remote", "--symref", repository_url, "HEAD"])
            for line in head.splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2 and REVISION.fullmatch(parts[0]):
                    return parts[0].lower()
            raise ComponentOnboardingError("public repository did not advertise HEAD")
        if REVISION.fullmatch(requested_ref):
            if requested_ref.lower() in advertised.values():
                return requested_ref.lower()
            raise ComponentOnboardingError(
                "selected commit is not advertised by the public repository"
            )
        revision = advertised.get(requested_ref)
        if revision is None:
            raise ComponentOnboardingError("selected branch or tag was not found")
        return revision

    def _bare_repository(self, repository_url: str, revision: str) -> Path:
        source_root = self.state_root / "objects" / self._source_key(repository_url)
        repository = source_root / "repository.git"
        if not repository.exists():
            source_root.mkdir(parents=True, exist_ok=True)
            self._git(["init", "--bare", str(repository)])
            self._git(["--git-dir", str(repository), "remote", "add", "origin", repository_url])
        origin = self._git(["--git-dir", str(repository), "remote", "get-url", "origin"]).strip()
        if origin != repository_url:
            raise ComponentOnboardingError("repository object cache identity mismatch")
        # Fetch an advertised object by exact ID.  No checkout, hooks, build,
        # package manager, or repository-provided command is invoked.
        self._git([
            "--git-dir",
            str(repository),
            "fetch",
            "--no-tags",
            "--depth=1",
            "origin",
            revision,
        ])
        resolved = self._git([
            "--git-dir",
            str(repository),
            "rev-parse",
            "FETCH_HEAD",
        ]).strip().lower()
        if resolved != revision:
            raise ComponentOnboardingError("repository fetch did not resolve the selected commit")
        return repository

    def _repository_metadata(
        self,
        repository: Path,
        revision: str,
        subdirectory: str,
    ) -> tuple[list[str], dict[str, str]]:
        prefix = [subdirectory] if subdirectory else []
        output = self._git([
            "--git-dir",
            str(repository),
            "ls-tree",
            "-r",
            "--name-only",
            revision,
            "--",
            *prefix,
        ])
        files = [line for line in output.splitlines() if line][:MAX_DISCOVERED_FILES]
        if subdirectory and not files:
            raise ComponentOnboardingError("selected subdirectory contains no tracked files")
        commit = self._git([
            "--git-dir",
            str(repository),
            "show",
            "-s",
            "--format=%cI%x00%s",
            revision,
        ]).strip()
        date, _, subject = commit.partition("\0")
        return files, {"date": date, "message": subject[:300]}

    @staticmethod
    def _detected_templates(files: Sequence[str]) -> list[str]:
        names = {Path(name).name.lower() for name in files}
        lower_paths = " ".join(files).lower()
        detected: list[str] = []
        if names & {"pyproject.toml", "setup.py", "requirements.txt"}:
            detected.append("python-operation")
        if "dockerfile" in names or "containerfile" in names:
            detected.append("container-cli")
        if any(token in lower_paths for token in ("transpil", "compiler", "qiskit", "pytket", "cirq", "openqasm", "quantinuum")):
            detected.append("compiler-transpiler")
        if any(token in lower_paths for token in ("simulator", "simulat", "stim", "aer", "nwq")):
            detected.append("simulator")
        if any(name in names for name in ("openapi.yaml", "openapi.yml", "main.py", "app.py")):
            detected.append("http-service")
        return detected or ["python-operation"]

    @staticmethod
    def _draft_template(template: str, component_id: str) -> dict[str, Any]:
        return {
            "template": template,
            "capability_interface": {
                "id": component_id,
                "version": "0.1.0-draft",
                "operation_id": "run",
                "input_artifact": "qhpc.quantum-circuit@1",
                "output_artifact": "qhpc.result@1",
            },
            "runtime_contract": {
                "execution_target": "local-development",
                "image_digest": None,
                "admission": "not-built",
            },
            "build_recipe": {
                "state": "not-run",
                "isolation": "required before any build",
                "host_credentials": "never exposed",
                "smoke_test": "required before local activation",
            },
        }

    def inspect(
        self,
        repository_url: str,
        *,
        ref: str = "HEAD",
        subdirectory: str = "",
        template: str | None = None,
    ) -> dict[str, Any]:
        """Resolve and inspect a repository without executing its source code."""
        source = normalise_public_repository_url(
            repository_url,
            allowed_hosts=self.allowed_hosts,
            allow_local_sources=self.allow_local_sources,
        )
        selected_ref = _normalise_ref(ref)
        selected_subdirectory = _safe_subdirectory(subdirectory)
        if template is not None and template not in TEMPLATES:
            raise ComponentOnboardingError("component template is not supported")
        with self._lock:
            revision = self._resolve_revision(source, selected_ref)
            bare_repository = self._bare_repository(source, revision)
            files, commit = self._repository_metadata(
                bare_repository,
                revision,
                selected_subdirectory,
            )
            detected_templates = self._detected_templates(files)
            selected_template = template or detected_templates[0]
            draft_key = hashlib.sha256(
                f"{source}\0{revision}\0{selected_subdirectory}\0{selected_template}".encode("utf-8")
            ).hexdigest()[:20]
            repository_name = Path(urlparse(source).path).name if source.startswith("https://") else Path(source).name
            component_id = _safe_component_id(repository_name.removesuffix(".git"))
            draft = {
                "id": f"onboarding-{draft_key}",
                "status": "inspected",
                "created_at": _timestamp(),
                "source": {
                    "repository_url": source,
                    "requested_ref": selected_ref,
                    "resolved_revision": revision,
                    "subdirectory": selected_subdirectory or None,
                    "commit_date": commit["date"],
                    "commit_message": commit["message"],
                },
                "inspection": {
                    "executed_repository_code": False,
                    "host_credentials_exposed": False,
                    "detected_templates": detected_templates,
                    "recognized_files": files,
                    "recognized_file_count": len(files),
                },
                "draft": self._draft_template(selected_template, component_id),
                "activation": {
                    "state": "blocked",
                    "reason": "Isolated build, smoke test, immutable image digest, and admission are required before activation.",
                },
            }
            state = self._load_state()
            state["drafts"][draft["id"]] = draft
            self._write_state(state)
            return draft

    def list(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            drafts = sorted(
                state["drafts"].values(),
                key=lambda item: item.get("created_at", ""),
                reverse=True,
            )
            return {"enabled": True, "items": drafts}

    def update_draft(self, draft_id: str, changes: dict[str, str]) -> dict[str, Any]:
        """Edit only the non-executable interface portion of an inspected draft."""
        if not isinstance(draft_id, str) or not draft_id.startswith("onboarding-"):
            raise ComponentOnboardingError("component draft identifier is invalid")
        allowed = {"template", "capability_id", "operation_id", "input_artifact", "output_artifact"}
        unexpected = sorted(set(changes) - allowed)
        if unexpected:
            raise ComponentOnboardingError(
                "unsupported draft fields: " + ", ".join(unexpected)
            )
        with self._lock:
            state = self._load_state()
            draft = state["drafts"].get(draft_id)
            if not isinstance(draft, dict):
                raise ComponentOnboardingError("component draft was not found")
            definition = draft.get("draft")
            if not isinstance(definition, dict):
                raise ComponentOnboardingError("component draft has no editable interface")
            interface = definition.get("capability_interface")
            if not isinstance(interface, dict):
                raise ComponentOnboardingError("component draft has an invalid interface")
            template = changes.get("template")
            if template is not None:
                if template not in TEMPLATES:
                    raise ComponentOnboardingError("component template is not supported")
                definition["template"] = template
            for field, key in (("capability_id", "id"), ("operation_id", "operation_id")):
                value = changes.get(field)
                if value is not None:
                    if not IDENTIFIER.fullmatch(value):
                        raise ComponentOnboardingError(
                            f"{field} must use lowercase letters, digits, and hyphens"
                        )
                    interface[key] = value
            for field, key in (("input_artifact", "input_artifact"), ("output_artifact", "output_artifact")):
                value = changes.get(field)
                if value is not None:
                    if not ARTIFACT_TYPE.fullmatch(value):
                        raise ComponentOnboardingError(
                            f"{field} must be a versioned artifact type"
                        )
                    interface[key] = value
            draft["updated_at"] = _timestamp()
            state["drafts"][draft_id] = draft
            self._write_state(state)
            return draft
