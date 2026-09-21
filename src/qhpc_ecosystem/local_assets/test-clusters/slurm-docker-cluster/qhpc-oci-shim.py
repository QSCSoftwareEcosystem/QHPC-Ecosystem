#!/usr/bin/env python3
"""Development-only Apptainer-shaped adapter for the Docker Engine API."""

import http.client
import json
import os
import re
import signal
import struct
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote


SOCKET_PATH = "/var/run/docker.sock"
API_PREFIX = "/v1.41"
IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ShimError(RuntimeError):
    pass


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str) -> None:
        super().__init__("localhost", timeout=30)
        self.socket_path = socket_path

    def connect(self) -> None:
        import socket

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


class DockerAPI:
    def __init__(self, socket_path: str = SOCKET_PATH) -> None:
        self.socket_path = socket_path

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        expected: Tuple[int, ...] = (200,),
    ) -> bytes:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(
                payload, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            }
        connection = UnixHTTPConnection(self.socket_path)
        try:
            connection.request(method, API_PREFIX + path, body=body, headers=headers)
            response = connection.getresponse()
            content = response.read()
        except OSError as error:
            raise ShimError(f"cannot access Docker Engine: {error}") from error
        finally:
            connection.close()
        if response.status not in expected:
            detail = content.decode("utf-8", errors="replace").strip()
            raise ShimError(
                f"Docker API {method} {path} returned {response.status}: {detail}"
            )
        return content


def _parse_command(
    argv: List[str],
) -> Tuple[str, List[str], str, List[str]]:
    if not argv or argv.pop(0) != "exec":
        raise ShimError("the development OCI shim supports only 'exec'")
    binds = []
    working_directory = "/work"
    network = None
    no_value = {"--containall", "--cleanenv", "--net", "--no-home"}
    while argv:
        token = argv[0]
        if token in no_value:
            argv.pop(0)
            continue
        if token in {"--network", "--pwd", "--bind"}:
            argv.pop(0)
            if not argv:
                raise ShimError(f"missing value for {token}")
            value = argv.pop(0)
            if token == "--network":
                network = value
            elif token == "--pwd":
                working_directory = value
            else:
                binds.append(value)
            continue
        if token.startswith("-"):
            raise ShimError(f"unsupported execution option: {token}")
        break
    if network != "none":
        raise ShimError("development OCI execution requires network=none")
    if not argv:
        raise ShimError("missing OCI descriptor")
    descriptor = argv.pop(0)
    if not argv:
        raise ShimError("missing operation entrypoint")
    return descriptor, binds, working_directory, argv


def _descriptor(path: str) -> Dict[str, Any]:
    descriptor_path = Path(path)
    try:
        value = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ShimError(f"invalid development OCI descriptor: {path}") from error
    required = {
        "kind",
        "image",
        "digest",
        "host_shared_root",
        "scheduler_shared_root",
    }
    if set(value) != required or value["kind"] != "QHPCDevelopmentOCIImage":
        raise ShimError("development OCI descriptor has an invalid shape")
    if not isinstance(value["image"], str) or not value["image"]:
        raise ShimError("development OCI descriptor has no image")
    if not IMAGE_DIGEST.fullmatch(value["digest"]):
        raise ShimError("development OCI descriptor has an invalid image digest")
    for name in ("host_shared_root", "scheduler_shared_root"):
        root = value[name]
        if not isinstance(root, str):
            raise ShimError(f"development OCI descriptor {name} must be text")
        parsed = PurePosixPath(root)
        if not parsed.is_absolute() or ".." in parsed.parts:
            raise ShimError(f"development OCI descriptor {name} is invalid")
    return value


def _docker_binds(
    values: List[str], descriptor: Dict[str, Any]
) -> List[str]:
    scheduler_root = PurePosixPath(descriptor["scheduler_shared_root"])
    host_root = Path(descriptor["host_shared_root"]).resolve()
    rendered = []
    for value in values:
        parts = value.split(":")
        if len(parts) != 3:
            raise ShimError(f"invalid bind mapping: {value}")
        source, destination, mode = parts
        if mode not in {"ro", "rw"}:
            raise ShimError(f"invalid bind mode: {mode}")
        source_path = PurePosixPath(source)
        destination_path = PurePosixPath(destination)
        try:
            relative = source_path.relative_to(scheduler_root)
        except ValueError as error:
            raise ShimError(f"bind source is outside shared storage: {source}") from error
        if (
            not destination_path.is_absolute()
            or ".." in relative.parts
            or ".." in destination_path.parts
        ):
            raise ShimError(f"invalid bind mapping: {value}")
        host_source = host_root.joinpath(*relative.parts).resolve()
        try:
            host_source.relative_to(host_root)
        except ValueError as error:
            raise ShimError(f"bind source escapes shared storage: {source}") from error
        if not Path(source).is_dir():
            raise ShimError(f"bind source is not a directory: {source}")
        rendered.append(f"{host_source}:{destination_path}:{mode}")
    return rendered


def _write_logs(payload: bytes) -> None:
    offset = 0
    while offset + 8 <= len(payload):
        stream = payload[offset]
        length = struct.unpack(">I", payload[offset + 4 : offset + 8])[0]
        offset += 8
        if offset + length > len(payload):
            break
        content = payload[offset : offset + length]
        offset += length
        target = sys.stderr.buffer if stream == 2 else sys.stdout.buffer
        target.write(content)
        target.flush()
    if offset == 0 and payload:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()


def run(argv: List[str]) -> int:
    descriptor_path, raw_binds, working_directory, command = _parse_command(argv)
    descriptor = _descriptor(descriptor_path)
    binds = _docker_binds(raw_binds, descriptor)
    api = DockerAPI()

    image_path = "/images/" + quote(descriptor["image"], safe="") + "/json"
    image = json.loads(api.request("GET", image_path))
    if image.get("Id") != descriptor["digest"]:
        raise ShimError(
            "local OCI image digest mismatch: "
            f"expected {descriptor['digest']}, found {image.get('Id', 'missing')}"
        )

    suffix = re.sub(r"[^A-Za-z0-9_.-]", "-", os.environ.get("SLURM_JOB_ID", "job"))
    name = f"qhpc-slurm-{suffix}-{os.getpid()}"
    created = json.loads(
        api.request(
            "POST",
            "/containers/create?name=" + quote(name, safe=""),
            payload={
                "Image": descriptor["image"],
                "Entrypoint": command[:1],
                "Cmd": command[1:],
                "WorkingDir": working_directory,
                "Labels": {
                    "org.qscsoftware.scope": "development-slurm-test",
                    "org.qscsoftware.slurm-job-id": os.environ.get(
                        "SLURM_JOB_ID", "unknown"
                    ),
                },
                "HostConfig": {
                    "AutoRemove": False,
                    "Binds": binds,
                    "CapDrop": ["ALL"],
                    "NetworkMode": "none",
                    "PidsLimit": 512,
                    "ReadonlyRootfs": True,
                    "SecurityOpt": ["no-new-privileges"],
                    "Tmpfs": {
                        "/tmp": "rw,noexec,nosuid,size=67108864",
                    },
                },
            },
            expected=(201,),
        )
    )
    container_id = created.get("Id")
    if not isinstance(container_id, str) or not container_id:
        raise ShimError("Docker Engine did not return a container ID")

    def remove(*, force: bool) -> None:
        query = "?force=1&v=1" if force else "?v=1"
        api.request(
            "DELETE",
            f"/containers/{container_id}{query}",
            expected=(204, 404),
        )

    def terminate(signum: int, _frame: object) -> None:
        try:
            remove(force=True)
        finally:
            raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)
    try:
        api.request("POST", f"/containers/{container_id}/start", expected=(204,))
        result = json.loads(
            api.request(
                "POST",
                f"/containers/{container_id}/wait?condition=not-running",
            )
        )
        logs = api.request(
            "GET",
            f"/containers/{container_id}/logs?stdout=1&stderr=1",
        )
        _write_logs(logs)
        status = result.get("StatusCode")
        if not isinstance(status, int):
            raise ShimError("Docker Engine returned no container exit status")
        return status
    finally:
        remove(force=True)


def main() -> int:
    try:
        return run(sys.argv[1:])
    except ShimError as error:
        print(f"qhpc-oci-shim: {error}", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
