# Studies and execution profiles

An EQO study is a durable, many-to-many group of related workflow runs. Use a
study for a repeatability check, a comparison across compilers or simulators,
or a small experiment series. It does not alter a run, its artifacts, or its
published workflow: those remain immutable provenance records.

## What an execution profile means

EQO derives a study's execution profiles from the runs actually attached to
it. A profile groups runs with the same:

- workflow ID, version, and immutable workflow digest; and
- execution target.

Each profile reports its run count and the distribution of run states. This is
an evidence summary, not a claim that target calibration, queue conditions, or
scientific results were identical. Compare the individual run receipts and
artifacts when those details matter.

## CLI

Create an empty study, submit a new run directly into it, or attach an existing
run:

```bash
eqo run-record study create "Trotter comparison" \
  --description "Compare bounded local synthesis paths"

eqo run-record submit WORKFLOW_ID VERSION --study STUDY_ID
eqo run-record study add-run STUDY_ID RUN_ID
eqo run-record study info STUDY_ID
eqo run-record study list
```

`study info` returns the member runs and their derived execution profiles as
structured JSON, so it is appropriate for a notebook or a small report.

## API and Python

The REST surface is:

- `POST /api/v1/studies` — create a study with `name`, optional `description`,
  and optional `created_by`;
- `GET /api/v1/studies` and `GET /api/v1/studies/{study_id}` — list or inspect;
- `POST /api/v1/studies/{study_id}/runs` — add `run_id`; and
- `POST /api/v1/runs` with optional `study_id` — submit directly into a study.

The Python client uses the same API:

```python
from eqo import EQOClient

client = EQOClient.connect("http://127.0.0.1:8181")
study = client.studies.create("Bell validation")
run = client.workflows.submit(
    "example-generate-and-simulate", "0.1.0", study_id=study.id
)
profile_summary = study.refresh().metadata["execution_profiles"]
```

Studies and membership are exported as logical, portable EQO Local state. A
portable state version 1 bundle can still be imported; it simply has no study
records. Version 2 state preserves studies and their memberships alongside
their run and artifact provenance.
