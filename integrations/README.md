# Integration Scaffolds

This directory tracks pre-runtime integration work for every component in the
initial deployment profile. A scaffold records source and GitLab mirror
information, the assigned developer environment, the intended interface,
contract and adapter readiness, fixtures, tests, and blockers.

Scaffolds are not executable capability descriptors. They deliberately contain
no runtime digest or invocation command. Runtime-free `OperationInterface`
documents pin the audited source and define behavior, typed artifact ports, and
parameters while adapters and integration tests stabilize. Runtime-free
`ServiceInterface` documents define separately deployed HTTPS boundaries,
identity requirements, policy invariants, JSON Schemas, and endpoints without
selecting deployment credentials or providers. Production containerization
follows that work; an executable component graduates to a registry capability
only after the immutable runtime is accepted and its digest can be recorded.

Validate and inspect the set with:

```bash
qhpc-ecosystem integration validate deployments/initial.yaml
qhpc-ecosystem integration list deployments/initial.yaml
qhpc-ecosystem integration info deployments/initial.yaml nwqec
qhpc-ecosystem contract validate operation-interface integrations/nwqec/interface.yaml
qhpc-ecosystem contract validate service-interface integrations/chatqec/service.yaml
```

Source-backed verification entry points for the current pre-runtime adapters
are `tools/verify_nwqec.py` and
`tools/verify_ftprimitivebench_lightstim.py`. They require the corresponding
pinned project dependencies and do not substitute for production target tests.
TN-Sim command construction and count parsing are covered by the pinned source
audit and representative fixtures; its external iTensor binary remains a
production-runtime build and source-backed acceptance gate.

The initial pre-container integration scope is closed for all ten selected
components. OpenQSE and QAppsWiki publish pinned non-executable resources.
ChatQEC has a provider-neutral service contract and controlled client adapter;
its server implementation and institutionally approved deployment services
remain production gates.
