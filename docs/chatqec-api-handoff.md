# ChatQEC Workbench API Handoff

- Status: Implemented backend contract and Workbench client
- Last updated: 2026-07-28
- Workbench view: `?view=assistant`
- Service boundary: [ChatQEC Service Boundary](chatqec-service-boundary.md)

The Workbench must call the QHPC API, never the loopback ChatQEC service
directly. The QHPC API injects the authorized subject, workspace, policy,
correlation, active corpus revision, and downstream workload identity.

## Status

```http
GET /api/v1/assistant/chatqec/status
```

A configured healthy service returns `200`:

```json
{
  "status": "ok",
  "available": true,
  "service": "chatqec",
  "mode": "canonical-extractive-development",
  "source_revision": "4c017510511f835001bfe5901a9d59e86cc130cd",
  "corpus_revision": "sha256:...",
  "pages": 60,
  "tool_execution": false
}
```

An API started without ChatQEC returns `200` with
`{"status":"unconfigured","available":false}`. A configured but unreachable or
invalid service returns `502`.

## Ask

```http
POST /api/v1/assistant/chatqec/answers
Content-Type: application/json
X-CSRFToken: <Workbench CSRF token>

{
  "question": "How is the surface code decoded?",
  "conversation_id": "conversation-4d31b5ad",
  "history": [
    {"role": "user", "content": "What is the surface code?"},
    {"role": "assistant", "content": "Previous cited answer text"}
  ]
}
```

`history` is optional and limited to 20 messages. Questions and history entries
are limited to 8,000 characters. No other fields are accepted. In particular,
the browser cannot select an authorized subject, workspace, policy, provider,
model, corpus revision, service URL, or credential.

A successful response is the validated `answer-response` from
[`integrations/chatqec/service.yaml`](../integrations/chatqec/service.yaml). The
UI should consume:

- `answer`;
- `citations[]` with `title`, `source_uri`, `source_revision`, and optional
  `locator`;
- `confidence`;
- `provider` and `model`;
- `corpus_revision`;
- `usage`; and
- retrieval, rerank, generation, and total values under `latency_ms`.

Only `http` and `https` citation links should be made clickable. Render answer
text as untrusted content. A valid refusal has answer text, low confidence, and
an empty citation list.

## Failure Behavior

- `400`: unsupported or malformed browser payload.
- `503`: ChatQEC was not configured in the QHPC API process.
- `502`: configured ChatQEC transport, health, contract, or response failure.

The local implementation is deliberately extractive and model-free. Its
`provider` is `chatqec-local`, its `model` is
`canonical-extractive-v1`, and `tool_execution` is false. The interface must
not imply that a production model-backed service or DOE deployment approval
exists.

## Workbench Client

The **Assistant** view implements this contract in both the separately deployed
Django Workbench and the static development fallback. It keeps one
browser-local conversation, sends at most 20 prior user and assistant messages,
and creates a new conversation identifier on **Clear**. Status is loaded
independently and input remains disabled until the service reports available.

Answer content is HTML-escaped before the small supported bold-text transform.
Only absolute `http` and `https` citation URLs become links; other schemes
remain inert text. The source ledger reports each distinct citation and the
active service mode, tool-execution state, and corpus digest. The browser sends
only `question`, `conversation_id`, and `history`.
