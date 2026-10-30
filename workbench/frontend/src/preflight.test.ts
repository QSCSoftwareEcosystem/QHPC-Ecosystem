import { describe, expect, it } from "vitest";

import { workflowPreflightDisplay } from "./preflight";
import type { WorkflowPreflight } from "./types";


function report(
  state: WorkflowPreflight["state"],
  canQueue: boolean,
): WorkflowPreflight {
  return {
    state,
    ready: state === "ready",
    can_queue: canQueue,
    summary: "Execution check summary.",
    reason: "Execution check reason.",
    workflow: { id: "example", version: "0.1.0", digest: "sha256:example" },
    target: "local-development",
    checks: [],
    requirements: [],
    checked_at: "2026-10-28T12:00:00Z",
  };
}


describe("workflow preflight display", () => {
  it("allows queueing for a degraded advisory report", () => {
    const display = workflowPreflightDisplay(report("degraded", true));

    expect(display.status).toBe("degraded");
    expect(display.canQueue).toBe(true);
    expect(display.report?.target).toBe("local-development");
  });

  it("blocks queueing when a required check is unavailable", () => {
    const display = workflowPreflightDisplay(report("unavailable", false));

    expect(display.status).toBe("unavailable");
    expect(display.canQueue).toBe(false);
  });
});
