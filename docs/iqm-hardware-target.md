# IQM hardware execution target

`iqm-hardware` is the controlled target for the credential-isolated IQM
worker.  It accepts only the published `quantum-backend` operation admitted by
that worker.  The worker owns its HTTPS endpoint, one device alias, and its
credential; workflows can neither select an endpoint nor provide a provider
token.

The target permits the worker's approved provider egress only.  It is not a
reservation, capacity guarantee, or a claim that a submitted circuit will be
accepted by an external QPU.  EQO preflight checks the worker's non-secret
admission metadata immediately before queueing; the isolated worker performs
the final operation, runtime, target, and credential-reference checks.

In the optional per-user credential mode, the fixed endpoint and device alias
remain operator controlled. A run's reverse-proxy-authenticated principal is
used only inside the IQM worker to select that principal's encrypted vault
entry. The token is never placed in the workflow, run, artifact, or API
response.

`iqm-simulation` is deliberately a separate, credential-free worker target.
It produces simulation evidence only and is never selected by the published
hardware workflow.
