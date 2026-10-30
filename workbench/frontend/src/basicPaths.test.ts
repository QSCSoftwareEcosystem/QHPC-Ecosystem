import { beforeAll, describe, expect, it, vi } from "vitest";


let basicPaths: Array<{
  id: string;
  workflowId: string;
  actionLabel: string;
  blocks: Array<{ title: string; kind: string; nodeIds?: string[] }>;
  hardwareNotice?: string;
}>;


beforeAll(async () => {
  vi.stubGlobal("window", {
    location: { href: "http://workbench.test/" },
  });
  ({ BASIC_PATHS: basicPaths } = await import("./ComposerApp"));
});


describe("basic Composer paths", () => {
  it("starts with an executable circuit-simulation path", () => {
    const simulation = basicPaths.find((path) => path.id === "simulate");

    expect(simulation).toMatchObject({
      workflowId: "nwqsim-bell-simulation",
      actionLabel: "Run simulation",
    });
    expect(simulation?.blocks.map((block) => block.title)).toEqual([
      "Circuit input",
      "Simulate",
      "Analyze results",
      "Results",
    ]);
    expect(simulation?.blocks.find((block) => block.title === "Simulate")?.nodeIds).toEqual([
      "simulate",
    ]);
  });

  it("offers a circuit transformation path with inspectable metrics", () => {
    const transform = basicPaths.find((path) => path.id === "transform");

    expect(transform).toMatchObject({
      workflowId: "ct-hw-qasm-analysis",
      actionLabel: "Transform circuit",
    });
    expect(transform?.blocks.map((block) => block.kind)).toEqual([
      "input",
      "transform",
      "analysis",
      "output",
    ]);
    expect(transform?.blocks.find((block) => block.title === "Transform circuit")?.nodeIds).toEqual([
      "transpile",
    ]);
  });

  it("keeps hardware execution explicit and preflight-ready", () => {
    const hardware = basicPaths.find((path) => path.id === "hardware");

    expect(hardware).toMatchObject({
      workflowId: "ftqc-iqm-bell-execution",
      actionLabel: "Submit hardware run",
    });
    expect(hardware?.blocks.map((block) => block.kind)).toEqual([
      "input",
      "transform",
      "execution",
      "output",
    ]);
    expect(hardware?.blocks.find((block) => block.title === "Run on hardware")?.nodeIds).toEqual([
      "execute",
    ]);
    expect(hardware?.hardwareNotice).toContain("QPU job");
  });
});
