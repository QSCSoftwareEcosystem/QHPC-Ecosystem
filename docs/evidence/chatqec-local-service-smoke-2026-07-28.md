# ChatQEC Local Service Smoke Evidence

- Date: 2026-07-28
- Scope: Local development service, QHPC API boundary, and Workbench client
- Result: Passed
- Production acceptance: Not claimed

## Source

- Repository: `https://github.com/QSCSoftwareThrust/ChatQEC`
- Revision: `4c017510511f835001bfe5901a9d59e86cc130cd`
- Prepared checkout:
  `.qhpc/services/chatqec-4c017510511f`
- License file: Present
- Canonical pages loaded: 60
- Deterministic corpus revision:
  `sha256:95e43b52660f4789457ef54b0b5c3ffc557b0610e24fc4780ed709c800928330`

The source manager verified origin, exact `HEAD`, a clean tracked worktree,
license presence, and canonical corpus presence. It also recovered an
interrupted generated checkout containing only `.git`; a regression test
covers that state while ordinary tracked changes remain fail-closed.

## Service Boundary

The loopback service started independently from the QHPC API and reported:

```json
{
  "status": "ok",
  "service": "chatqec",
  "mode": "canonical-extractive-development",
  "pages": 60,
  "tool_execution": false
}
```

An authenticated contract request asking how the surface code is decoded
returned:

- a canonical extractive answer including the decoding section;
- citation ID `canonical:surface-code`;
- the exact ChatQEC source revision in the citation URI;
- content revision
  `sha256:1d382ae0ea363c31e2424ab27a8c23eaecb6f3af029c4fe623eb6a21361d100a`;
- provider `chatqec-local`;
- model label `canonical-extractive-v1`; and
- retrieval and total latency accounting.

An unauthenticated direct answer request returned `401`. JSON and SSE response
paths are covered by the same response validator.

## QHPC Gateway

The QHPC API was started against the independent loopback service. Its
`GET /api/v1/assistant/chatqec/status` endpoint reported the 60-page active
corpus. A browser-shaped request to
`POST /api/v1/assistant/chatqec/answers`, containing only question,
conversation ID, and history, returned the cited answer without a downstream
credential in the request. A request attempting to supply
`authorized_subject` returned `400`.

The generated workload token is absent from process commands. The development
supervisor removes any parent-shell `QHPC_CHATQEC_IDENTITY_TOKEN` before
starting children, then supplies its generated token only to the QHPC API and
ChatQEC service.

## Workbench Client

The Django Workbench called the QHPC gateway through its fixed-origin proxy,
loaded the 60-page service status, submitted a surface-code question, and
rendered the returned canonical answer and exact-revision citation. Desktop
1440 by 1000 and mobile 390 by 844 browser checks found no console errors or
horizontal overflow.

A repeatable Playwright test covers both viewports. It verifies that the
browser request contains exactly `question`, `conversation_id`, and `history`;
answer HTML is escaped; an HTTPS citation is linked; and a `javascript:`
citation remains inert text. The mobile view scrolls the new answer below the
existing sticky navigation.

## Automated Verification

The complete Python suite passed with loopback socket tests enabled:

```text
161 passed in 30.77s
```

This includes source preparation, exact-revision recovery, cited answer and
refusal behavior, workload authentication, JSON and SSE validation, service
origin restrictions, API payload allowlisting, and supervisor token isolation.
Contracts, all ten integration scaffolds, and the rebuilt 13-capability
registry also validated.

The dedicated ChatQEC Playwright specification passed in both desktop and
mobile projects (`2 passed`). The frontend TypeScript check and all seven
composer unit tests also passed.

## Exclusions

This evidence does not approve or exercise a generative model, embedding
endpoint, Qdrant service, open-web fallback, image ingestion, scientific tool
execution, non-loopback service transport, institutional identity, production
secrets, production retention, load, or DOE security acceptance. Those remain
production gates under ADR 0008.
