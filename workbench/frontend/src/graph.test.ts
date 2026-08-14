import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import {
  canvasToWorkflow,
  validateCanvas,
  validateConnection,
  workflowToCanvas,
} from "./graph";
import type { Workflow } from "./types";


const exampleRoot = resolve(import.meta.dirname, "../../../examples/workflows");
const examples = [
  "ct-hw-qasm-analysis.yaml",
  "qec-memory-estimation.yaml",
  "openqevo-method-catalog.yaml",
  "openqevo-trotter-synthesis.yaml",
  "nwqec-counts.yaml",
  "showcase-evolution-readiness.yaml",
  "showcase-qec-distance-study.yaml",
];


describe("workflow canvas conversion", () => {
  it.each(examples)("round-trips %s without changing the workflow", (name) => {
    const workflow = parse(
      readFileSync(resolve(exampleRoot, name), "utf8"),
    ) as Workflow;
    const canvas = workflowToCanvas(workflow, undefined, []);

    expect(
      canvasToWorkflow(workflow.metadata, canvas.nodes, canvas.edges),
    ).toEqual(workflow);
  });

  it("keeps layout out of the canonical workflow", () => {
    const workflow = parse(
      readFileSync(resolve(exampleRoot, examples[0]), "utf8"),
    ) as Workflow;
    const canvas = workflowToCanvas(workflow, undefined, []);
    canvas.nodes[0].position = { x: 999, y: 777 };

    expect(
      canvasToWorkflow(workflow.metadata, canvas.nodes, canvas.edges),
    ).toEqual(workflow);
  });

  it("rejects cycles and second connections to a named input", () => {
    const workflow = parse(
      readFileSync(resolve(exampleRoot, examples[0]), "utf8"),
    ) as Workflow;
    const canvas = workflowToCanvas(workflow, undefined, []);

    const cycle = validateConnection(
      {
        source: "analyze",
        sourceHandle: "out:metrics",
        target: "transpile",
        targetHandle: "in:circuit",
      },
      canvas.nodes,
      canvas.edges,
    );
    expect(cycle.valid).toBe(false);

    const occupied = validateConnection(
      {
        source: "input:circuit",
        sourceHandle: "out:circuit",
        target: "transpile",
        targetHandle: "in:circuit",
      },
      canvas.nodes,
      canvas.edges,
    );
    expect(occupied).toEqual({
      valid: false,
      message: "That input already has a connection.",
    });
  });

  it("reports a disconnected workflow boundary", () => {
    const workflow = parse(
      readFileSync(resolve(exampleRoot, "nwqec-counts.yaml"), "utf8"),
    ) as Workflow;
    const canvas = workflowToCanvas(workflow, undefined, []);
    const edges = canvas.edges.filter(
      (edge) => edge.data?.kind !== "workflow-input",
    );

    expect(validateCanvas(canvas.nodes, edges)).toContainEqual({
      code: "boundary.disconnected",
      message: "Workflow input circuit is disconnected.",
      nodeId: "input:circuit",
    });
  });
});
