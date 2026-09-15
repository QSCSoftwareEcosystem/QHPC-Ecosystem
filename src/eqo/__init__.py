"""Public Python client for the EQO control plane.

The SDK is intentionally a client: scientific code and services continue to
run only through EQO's admitted workers and OCI service profiles.
"""

from .client import (
    Artifact,
    ArtifactCollection,
    EQOAPIError,
    EQOClient,
    EQOConnectionError,
    EQOError,
    EQOProtocolError,
    EQOTimeoutError,
    Run,
)
from .notebook import NotebookView, render_artifact, render_citations, render_run

__all__ = [
    "Artifact",
    "ArtifactCollection",
    "EQOAPIError",
    "EQOClient",
    "EQOConnectionError",
    "EQOError",
    "EQOProtocolError",
    "EQOTimeoutError",
    "NotebookView",
    "Run",
    "render_artifact",
    "render_citations",
    "render_run",
]
