# IQM hardware execution target

`iqm-hardware` is the controlled target for the credential-isolated IQM
worker.  It accepts only the published `quantum-backend` operation admitted by
that worker.  The worker owns its HTTPS endpoint, one device alias, and its
credential; workflows can neither select an endpoint nor provide a provider
token. Published hardware workflows request the logical alias `default`; the
worker resolves that name to its one operator-configured device alias and
rejects any workflow-supplied device name.

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

## Run-scoped settings

A published workflow remains immutable. An operation can explicitly mark a
bounded parameter as `run_tunable`; EQO then records the caller's selected
value in the persisted task operation for that particular run without changing
the workflow digest. The Basic hardware path currently exposes only the IQM
measurement-shot count (1 through 4096). Device selection, endpoint, wait
limit, runtime identity, and credential reference remain worker-owned.
