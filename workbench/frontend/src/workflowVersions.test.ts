import { describe, expect, it } from "vitest";

import { compareWorkflowVersions, latestWorkflowVersions } from "./workflowVersions";
import type { PublishedWorkflow } from "./types";


function workflow(id: string, version: string): PublishedWorkflow {
  return {
    id,
    version,
    digest: "sha256:" + "0".repeat(64),
    registry_digest: "sha256:" + "1".repeat(64),
    created_at: "2026-09-10T00:00:00Z",
    created_by: "test",
    definition: {
      api_version: "qhpc/v1",
      kind: "Workflow",
      metadata: { id, version, name: id, owner: "test", visibility: "internal" },
      spec: { nodes: [], edges: [], inputs: {}, outputs: {} },
    },
  };
}


describe("workflow version selection", () => {
  it("orders semantic versions including prereleases", () => {
    expect(compareWorkflowVersions("0.2.0", "0.1.0")).toBeGreaterThan(0);
    expect(compareWorkflowVersions("1.0.0", "1.0.0-rc.1")).toBeGreaterThan(0);
    expect(compareWorkflowVersions("1.0.0-rc.10", "1.0.0-rc.2")).toBeGreaterThan(0);
  });

  it("keeps only the newest runnable workflow per immutable workflow ID", () => {
    expect(
      latestWorkflowVersions([
        workflow("ftqc-iqm-bell-preparation", "0.1.0"),
        workflow("qec-memory-estimation", "0.1.0"),
        workflow("ftqc-iqm-bell-preparation", "0.2.0"),
      ]).map((item) => `${item.id}@${item.version}`),
    ).toEqual([
      "ftqc-iqm-bell-preparation@0.2.0",
      "qec-memory-estimation@0.1.0",
    ]);
  });
});
