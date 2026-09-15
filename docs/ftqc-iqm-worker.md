# FTQC–IQM Quantum Worker

The FTQC preparation workflows are credential-free. The two execution workflows
add a separate `quantum-backend` task only after the local preparation report
and IQM-native circuit are available. They are claimed exclusively by
`qhpc-iqm-worker`; ordinary local and Slurm workers never admit that class.

## Install the provider in the isolated worker environment

IQM's Qiskit integration is optional, so it is not installed with the ordinary
EQO development dependencies:

```bash
python -m pip install '.[iqm]'
```

The optional dependency pins `iqm-client[qiskit]` to the tested major version.
The worker refuses to start if the client is unavailable. It does not contact a
device merely by starting.

## Start an internal-alpha worker

The endpoint and one permitted device alias belong to the operator's worker
configuration—not to a browser or workflow document. For the internal alpha,
there is no separate policy-reference field. Set the token only in the worker
process environment, then start it with non-secret configuration:

```bash
export IQM_BASE_URL='https://qccsw.ccs.ornl.gov'
qhpc-iqm-worker \
  --catalog ecosystem.yaml \
  --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --database .qhpc/live/workbench.sqlite \
  --artifact-root .qhpc/live/artifacts \
  --device-alias approved-device \
  --prompt-for-token
```

`IQM_BASE_URL` supplies the worker endpoint. `--endpoint` remains available as
an explicit non-secret override. Neither value is read from a workflow or
passed to the API, Workbench, or ordinary workers.

`--prompt-for-token` uses the invoking terminal's no-echo prompt and keeps the
value only in the IQM worker process. It is deliberately unavailable from the
browser and no token argument exists. Non-interactive deployment may instead
provide `IQM_TOKEN` in the IQM worker's process environment. For supervised
local startup, use `eqo dev up --start-iqm-worker --prompt-for-iqm-token` with
the device-alias option.

The process advertises a non-secret readiness record to the Workbench: the
runtime, device alias, internal-alpha scope, and whether the configured
credential reference is currently resolvable. It never advertises or stores the
token.

`eqo dev up --start-iqm-worker` can supervise the same worker after receiving
the endpoint and alias flags. It passes `IQM_TOKEN` only to the IQM child
process and removes it from the API, Workbench, local-worker, and
virtual-Slurm-worker environments.

## Run the safe simulation worker

For a complete local route/submit/collect demonstration before a site has
approved hardware access, start the distinct simulation worker:

```bash
eqo iqm-simulation-worker \
  --catalog ecosystem.yaml \
  --registry examples/registry.yaml \
  --deployment-profile deployments/initial.yaml \
  --database .qhpc/live/workbench.sqlite \
  --artifact-root .qhpc/live/artifacts
```

It requires neither the optional IQM client dependency nor `IQM_BASE_URL` or
`IQM_TOKEN`, makes no network request, and accepts no endpoint configuration.
It uses the same typed asynchronous boundary as the hardware worker, but all
layout, receipt, and counts artifacts identify `provider: simulated-iqm` and a
simulation-only calibration. The Workbench exposes it as **Safe demonstration
mode**, never as a satisfied hardware-admission gate.

For the supervised developer stack use
`eqo dev up --start-iqm-simulation-worker`. EQO Local exposes the same safe
path with `eqo local up --iqm-simulation --open`.

## What the execution workflow preserves

The worker uses the IQM Client/Qiskit provider to route against the current
backend calibration, then preserves a routed layout, redacted job receipt, raw
counts, and decoded logical-result artifact. It restricts each worker to one
device alias and one `secret://env/...` reference, bounds inputs, shots, wait
time, and provider response sizes, and adopts a persisted job handle after a
worker restart rather than submitting a duplicate job.

Starting the worker or completing a job does not promote a scientific claim.
Promotion still requires the developer-approved hardware evidence packet and
comparison rule described in the FTQC–IQM plan.
