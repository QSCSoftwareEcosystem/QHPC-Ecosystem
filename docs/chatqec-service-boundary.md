# ChatQEC Service Boundary

- Status: Accepted design baseline
- Local implementation: Functional bundled canonical-corpus service
- Accepted: 2026-07-24
- Working source: [QSCSoftwareThrust/ChatQEC](https://github.com/QSCSoftwareThrust/ChatQEC)
- Pinned revision: `a1ddc2e4916b1f4152fba4c94c9c7512eea0d977`
- Formal decision: [ADR 0008](adr/0008-chatqec-internal-service-boundary.md)
- Service contract: [`integrations/chatqec/service.yaml`](../integrations/chatqec/service.yaml)
- Client adapter: [`service_adapters.py`](../src/qhpc_ecosystem/service_adapters.py)
- Development service: [`chatqec_service.py`](../src/qhpc_ecosystem/chatqec_service.py)
- QHPC gateway: [`assistant.py`](../src/qhpc_ecosystem/assistant.py)
- Workbench API handoff: [ChatQEC Workbench API Handoff](chatqec-api-handoff.md)
- Local smoke evidence:
  [2026-07-28 ChatQEC service smoke](evidence/chatqec-local-service-smoke-2026-07-28.md)
- Local bundle evidence:
  [2026-09-03 bundled corpus verification](evidence/chatqec-bundled-corpus-2026-09-03.md)
- Source evidence:
  [initial component source audit](evidence/initial-component-source-audit-2026-07-22.md#chatqec)

## Short Explanation

ChatQEC is a separately deployed internal assistant service, not code embedded
inside the QHPC API or Workbench. Users authenticate to QHPC, QHPC authorizes
the request, and QHPC calls ChatQEC with a scoped service identity. ChatQEC can
return cited answers from an approved read-only corpus, but it cannot submit
workflows or execute scientific tools directly.

This boundary keeps user identity, authorization, workflow execution, and
durable provenance under QHPC control while allowing the ChatQEC project to
evolve and deploy independently.

The provider-neutral v1 HTTPS JSON/SSE contract, bounded request builder,
response validator, SSE parser, fixtures, and integration tests are now
implemented in QHPC. The adapter requires a deployment-supplied transport that
applies the approved workload identity; it does not select or carry a provider
credential.

QHPC also implements a conforming loopback-only development server over the
exact-revision canonical Markdown corpus owned by ChatQEC. It returns
deterministic extractive answers or an explicit refusal, validates the same
request and response contracts, attaches immutable source citations, accepts
only a server-supplied bearer workload identity, disables tool execution, and
retains no conversation state. `eqo local up` verifies and serves the licensed,
checksum-pinned corpus bundled in the installed EQO wheel, so its first start
requires no network access or source checkout. `eqo dev up` may still prepare a
Git checkout for integration development. Both supervise the Assistant process
independently from the QHPC API. This makes the local Workbench assistant
functional without claiming that a generative model, Qdrant deployment, or
production identity service has been approved.

## Topology

```text
Workbench / CLI / automation
            |
            | institutional user identity
            v
        QHPC API
        - authentication and authorization
        - quotas, audit, and correlation
        - workflow and artifact control
            |
            | scoped workload identity over encrypted transport
            v
    Internal ChatQEC service
        - isolated conversation context
        - retrieval and cited answer generation
        - no direct workflow execution
          /                     \
         v                       v
read-only Qdrant corpus   one approved model endpoint
```

The browser does not call ChatQEC, Qdrant, or a model provider directly.
Provider credentials never enter the browser or workflow definition.

For local development, the lower two dependencies in this topology are
replaced by a read-only lexical/extractive pass over ChatQEC's pinned canonical
pages. Plain HTTP is allowed only on the loopback hop between the local QHPC
API and local development service. A non-loopback service origin still
requires HTTPS.

## Initial Allowed Scope

- Authenticated text questions about QEC.
- Retrieval from one curated, immutable corpus snapshot.
- Cited text answers with confidence, model identity, corpus revision, token
  accounting, and stage latency.
- Optional streaming through a versioned internal JSON and SSE contract.
- Explicit publication of an answer and citations as a governed QHPC artifact
  when retention is needed.

## Initially Disabled

- Anonymous or hCaptcha-based production access.
- User-controlled source ingestion or corpus mutation.
- Image and figure uploads.
- Tavily or other open-web fallback.
- Automatic failover among Anthropic, Gemini, or Hugging Face providers.
- Direct MCP subprocess execution.
- Direct workflow publication, run submission, or HPC and quantum target
  access.

These capabilities may be added later only through a reviewed contract and the
required data-egress, threat, and deployment approvals.

## Identity And Data Rules

- QHPC uses the approved institutional identity provider and authorizes the
  `assistant:ask` action.
- QHPC calls ChatQEC with mTLS or an equivalent short-lived workload identity.
- Conversation state is isolated by subject, workspace, and conversation ID.
- Prompts, responses, and images are not retained by default.
- Production telemetry excludes full prompts, retrieved chunks, provider
  payloads, tool content, and secrets.
- Quotas and provider costs are attributed to an authenticated subject and
  workspace, not an IP address or Streamlit session.

## Corpus And Model Rules

The online ChatQEC service has read-only access to Qdrant. Corpus ingestion,
embedding, source review, and retraction are separate curator-authorized jobs.
Each corpus release records its source registry digest, embedding model,
ChatQEC revision, licenses and attribution, and retraction state.

Each deployment selects exactly one site-hosted or explicitly DOE-approved
model endpoint and one approved embedding path. Automatic cross-provider
fallback is disabled because it could change where request content is sent.
Network egress is deny-by-default and limited to the selected endpoint.

## Tool Integration Later

ChatQEC may eventually return a structured tool proposal. It still does not
execute the tool. QHPC resolves the proposed operation against its registry,
authorizes it as the user, obtains confirmation when required, and submits it
through the ordinary workflow control plane.

## Remaining Deployment Inputs

The architecture is accepted. Deployment still requires concrete selections
and institutional acceptance for:

- the model and embedding endpoints;
- the identity provider and workload-identity mechanism;
- the allowed information class and egress routes;
- secrets storage, Qdrant placement, and corpus release storage;
- retention periods, quotas, budget, and service-level objectives; and
- a production model-backed server implementation with authorization,
  isolation, cancellation, timeout, provider-failure, load, and security
  acceptance tests.

These inputs configure the accepted boundary; they do not change the boundary
itself unless a later ADR supersedes [ADR 0008](adr/0008-chatqec-internal-service-boundary.md).
