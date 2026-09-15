"""Safe rich representations for EQO objects in Jupyter frontends.

The SDK deliberately returns renderable values rather than calling IPython's
global display hook.  This keeps notebooks importable in ordinary Python and
ensures that rendering never starts a service, submits a run, or interprets an
artifact as executable HTML, JavaScript, or SVG.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .client import Artifact, Run


_MAX_PREVIEW_BYTES = 256 * 1024
_MAX_ROWS = 50
_MAX_COLUMNS = 12
_MAX_CELL_CHARACTERS = 2_000


@dataclass(frozen=True)
class NotebookView:
    """A frontend-neutral, escaped rich view.

    Jupyter recognizes ``_repr_mimebundle_`` without making IPython a runtime
    dependency. The HTML is constructed only from escaped text.
    """

    text: str
    html: str

    def _repr_mimebundle_(
        self, include: Any = None, exclude: Any = None
    ) -> dict[str, str]:
        del include, exclude
        return {"text/plain": self.text, "text/html": self.html}

    def _repr_html_(self) -> str:
        return self.html


def _text(value: Any) -> str:
    rendered = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
    return rendered[:_MAX_CELL_CHARACTERS] + ("…" if len(rendered) > _MAX_CELL_CHARACTERS else "")


def _html_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(_text(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _wrapped(title: str, text: str, body: str) -> NotebookView:
    escaped_title = html.escape(title)
    return NotebookView(text=text, html=f"<section><h4>{escaped_title}</h4>{body}</section>")


def _json_view(title: str, payload: Any) -> NotebookView:
    if isinstance(payload, list) and payload and all(isinstance(item, Mapping) for item in payload):
        columns = list(dict.fromkeys(key for item in payload for key in item))[:_MAX_COLUMNS]
        rows = [[item.get(column, "") for column in columns] for item in payload[:_MAX_ROWS]]
        text = f"{title}: {len(payload)} record(s)"
        return _wrapped(title, text, _html_table(columns, rows))
    if isinstance(payload, Mapping):
        rows = list(payload.items())[:_MAX_ROWS]
        return _wrapped(title, f"{title}: {len(payload)} field(s)", _html_table(["field", "value"], rows))
    rendered = _text(payload)
    return _wrapped(title, rendered, f"<pre>{html.escape(rendered)}</pre>")


def render_artifact(artifact: Artifact) -> NotebookView:
    """Return a safe, size-bounded preview of a checksum-verified artifact.

    SVG and arbitrary binary payloads are summarized rather than embedded.
    This prevents an artifact from gaining browser execution privileges merely
    because a notebook renders it.
    """

    content = artifact.read_bytes()
    title = f"Artifact {artifact.id} ({artifact.artifact_type})"
    if len(content) > _MAX_PREVIEW_BYTES:
        text = f"{title}: {len(content)} bytes; inline preview suppressed at {_MAX_PREVIEW_BYTES} bytes"
        return _wrapped(title, text, f"<p>{html.escape(text)}</p>")
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        text = f"{title}: {len(content)} binary bytes; download the verified artifact to inspect it"
        return _wrapped(title, text, f"<p>{html.escape(text)}</p>")
    stripped = decoded.lstrip().lower()
    if stripped.startswith("<svg"):
        text = f"{title}: SVG preview suppressed; download the verified artifact to inspect it"
        return _wrapped(title, text, f"<p>{html.escape(text)}</p>")
    try:
        return _json_view(title, json.loads(decoded))
    except json.JSONDecodeError:
        preview = decoded[:_MAX_PREVIEW_BYTES]
        text = f"{title}: {len(content)} text bytes"
        return _wrapped(title, text, f"<pre>{html.escape(preview)}</pre>")


def render_citations(citations: Sequence[Mapping[str, Any]]) -> NotebookView:
    """Render citation metadata as escaped text, never as active links."""

    rows = [
        [
            citation.get("title", ""),
            citation.get("url", citation.get("source_uri", "")),
            citation.get("source_revision", ""),
        ]
        for citation in citations[:_MAX_ROWS]
    ]
    return _wrapped(
        "Citations",
        f"Citations: {len(citations)} record(s)",
        _html_table(["title", "source", "revision"], rows),
    )


def render_run(run: Run) -> NotebookView:
    """Render a run's current public state without polling or side effects."""

    state = run.state
    rows = [(key, value) for key, value in sorted(run.metadata.items()) if key not in {"id", "state"}]
    text = f"Run {run.id}: {state}"
    body = f"<p>{html.escape(text)}</p>" + _html_table(["field", "value"], rows[:_MAX_ROWS])
    return _wrapped(f"Run {run.id}", text, body)
