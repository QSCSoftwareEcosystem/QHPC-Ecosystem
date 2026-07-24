# ADR 0008: ChatQEC As An Internal Assistant Service

- Status: Accepted
- Proposed: 2026-07-22
- Accepted: 2026-07-24
- Source revision: `4c017510511f835001bfe5901a9d59e86cc130cd`
- Explanation: [ChatQEC Service Boundary](../chatqec-service-boundary.md)

## Context

ChatQEC 0.1.0 is a QEC research assistant with a Python API, CLI, and
Streamlit application. Its query path classifies and rewrites a question,
retrieves from a Qdrant corpus, reranks evidence, and synthesizes a cited
answer. Optional paths accept images, search the web through Tavily, or invoke
Stim and decoding tools through a sibling MCP server.

The current source is an application, not an authenticated internal service.
It has no HTTP service API. The Streamlit application constructs a cached
process-wide `ChatQEC` object whose in-memory conversation history is therefore
not an acceptable multi-user isolation boundary. Its default model selection
can fail over among external providers, Qdrant is host-published without an
application authentication boundary in the development Compose file, and
verbose traces contain full questions, retrieved text, prompts, and tool data.

QHPC must not import ChatQEC into its API process or expose the development
Streamlit application as the production integration boundary.

## Decision

### Service Topology

The Workbench, CLI, and automation clients authenticate to the QHPC API. The
QHPC API calls a separately deployed ChatQEC service using an approved workload
identity and encrypted internal transport. ChatQEC is not directly reachable
from a user network, and it does not receive or validate browser credentials.

The initial service supports only cited text questions against a curated,
read-only corpus. The following paths remain disabled initially:

- anonymous and hCaptcha-based production access;
- user-directed source ingestion or corpus mutation;
- image attachments and figure upload;
- Tavily or other open-web fallback;
- direct MCP subprocess execution; and
- direct workflow publication, run submission, or target access.

### Identity And Authorization

QHPC performs user authentication with the approved institutional identity
provider and authorizes the `assistant:ask` action. The downstream call uses a
ChatQEC-specific workload identity, preferably mTLS or an equivalent
short-lived service credential. It carries a correlation ID, authorized
subject identifier, workspace identifier, and policy class for accounting and
audit. Long-lived shared API keys and forwarded browser bearer tokens are not
the preferred boundary.

Quotas are keyed by authenticated subject and workspace rather than an IP or
Streamlit session ID. The ChatQEC service applies defensive request and cost
limits even when QHPC has already authorized the request.

### Model And Egress Policy

Each deployment selects one explicitly approved model endpoint and one
explicitly approved embedding path. Production disables ChatQEC's automatic
provider failover because it can change the recipient and location of request
content without a new authorization decision. Provider, model, endpoint policy
ID, and model response identifiers are included in provenance.

Provider and web credentials are supplied by the approved secrets service and
are never sent to the browser, stored in workflow definitions, or loaded from a
production `.env` file. Network egress is deny-by-default and allowlisted for
the selected deployment policy.

### Conversation And Data Policy

Conversation state is isolated by QHPC subject, workspace, and conversation ID.
The ChatQEC process does not use shared global conversation memory. The request
either carries an authorized bounded history or references state in an
approved store with a defined TTL.

Prompts, responses, and uploaded content are not retained by default. QHPC
keeps the minimum audit record: request and correlation IDs, subject and
workspace identifiers, timestamps, policy decision, model and corpus
revisions, citation IDs, token and cost accounting, status, and stage latency.
A user may explicitly publish an answer and its citations as a governed QHPC
artifact when scientific provenance requires retention.

Full-payload tracing is disabled in production. Operational logs redact prompt,
retrieved chunk, provider payload, secret, and tool content. Any diagnostic
payload capture requires a separately authorized mode, protected storage, and
short retention.

### Corpus And Storage

The online service has read-only access to one versioned Qdrant corpus
snapshot. Qdrant is private to the service network and is not host-published to
users. Corpus ingestion, embeddings, source retraction, and watchlist refresh
run as a separate curator-authorized administrative job with distinct
credentials.

Every corpus release records its source registry digest, embedding model and
dimension, build revision, license and attribution review, and retraction
state. User queries cannot add URLs, repositories, PDFs, or videos to the
production corpus.

### API Contract

The first contract is a versioned internal JSON request with an optional SSE
response stream. It must include a request ID, conversation ID, question,
bounded history or history reference, workspace policy class, and corpus
revision. The response includes answer text, structured citations, confidence,
provider and model identity, corpus revision, token accounting, and latency
stages.

The model may return a structured tool proposal in a later contract, but it
cannot execute a QHPC operation. QHPC validates the proposed operation against
the registry, authorizes it as the user, requests confirmation when policy
requires it, and submits it through the ordinary workflow control plane.

## Required Source Work

Before this decision can become an executable service contract:

- add a dedicated internal HTTP/SSE adapter rather than using Streamlit as the
  service API;
- create one isolated conversation context per authorized conversation;
- return citations and final metadata from the streaming call so the current
  Streamlit pattern does not execute the question a second time;
- connect rate and cost enforcement to authenticated identity and measured
  provider usage;
- add redacted production telemetry and disable full-payload user tracing;
- separate read-only query startup from corpus administration; and
- add contract, authorization, isolation, cancellation, timeout, and provider
  failure tests.

## Implementation Status

QHPC now carries the provider-neutral v1 service contract, bounded request and
response adapter, SSE parser, representative fixtures, and client-side
contract tests. The adapter deliberately requires a deployment-configured
transport so it cannot select a workload credential or model provider.

The ChatQEC server changes listed above are not implemented by this repository.
They remain required before the service runtime can be built or accepted. The
machine-readable contract closes the ecosystem's pre-container interface
boundary; it does not approve a provider, corpus, identity mechanism, or
production deployment.

## Accepted Baseline

The following restrictive choices are the accepted QHPC design baseline. The
responsible institutional authority must approve the concrete deployment
services and any broader choice.

| Decision | Recommended initial choice |
| --- | --- |
| Model endpoint | One site-hosted or explicitly DOE-approved endpoint; no automatic cross-provider failover |
| Allowed content | Public or otherwise explicitly approved non-sensitive QEC questions and corpus material only |
| User identity | Institutional OIDC at QHPC; scoped workload identity from QHPC to ChatQEC |
| Retention | No prompt, response, or image retention by default; explicit governed artifact publication only |
| Corpus governance | Curator allowlist, license review, immutable snapshot digest, and retraction process |
| Images and web search | Disabled until separate content-egress approval and threat review |
| Scientific tools | Disabled initially; later exposed only as QHPC-authorized operation proposals |
| Quotas | Per subject and workspace with provider-token accounting and a deployment-wide budget |
| Availability | Internal best-effort service initially, with timeout, cancellation, and fail-closed behavior |

## Consequences

- ChatQEC remains independently owned and deployable while QHPC owns identity,
  authorization, workflow execution, and durable scientific provenance.
- Model and data egress become explicit deployment policy rather than an
  application fallback behavior.
- Corpus mutation cannot affect a running service without a reviewed snapshot
  release.
- The narrow first boundary delays images, web fallback, and live tools, but it
  avoids exposing the highest-risk paths before their controls exist.
- Accepting this architecture does not certify a concrete model endpoint,
  allowed data class, retention period, or institutional identity mechanism;
  those remain deployment inputs and acceptance gates.
