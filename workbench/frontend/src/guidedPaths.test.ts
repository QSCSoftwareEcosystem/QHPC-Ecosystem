import { beforeAll, describe, expect, it, vi } from "vitest";


let scientificPaths: Array<{
  workflowId: string;
  code: string;
  shortName: string;
  section: string;
  kind: string;
  toolChain: string[];
  inputLabel?: string;
  inputPlaceholder?: string;
  featuredRecipe?: { detail: string };
  examples?: Array<{ name: string; label: string; content: string }>;
  hardwareNotice?: { title: string; detail: string };
}>;


beforeAll(async () => {
  vi.stubGlobal("window", {
    location: { href: "http://workbench.test/" },
  });
  ({ SCIENTIFIC_PATHS: scientificPaths } = await import("./ComposerApp"));
});


describe("guided Composer paths", () => {
  it("leads with four goal-oriented scientific recipes", () => {
    const recipes = scientificPaths.filter((path) => path.featuredRecipe);

    expect(recipes).toHaveLength(4);
    expect(recipes.map((path) => path.workflowId)).toEqual(expect.arrayContaining([
      "openqevo-trotter-synthesis",
      "ct-hw-qasm-analysis",
      "qec-memory-estimation",
      "ftqc-iqm-bell-execution",
    ]));
    expect(recipes.every((path) => path.featuredRecipe?.detail)).toBe(true);
  });

  it("offers a Bell-circuit IQM hardware execution example", () => {
    const bellExecution = scientificPaths.find(
      (path) => path.workflowId === "ftqc-iqm-bell-execution",
    );

    expect(bellExecution).toMatchObject({
      code: "F4",
      shortName: "Route and execute a two-qubit Bell circuit",
      section: "gated",
      kind: "Hardware execution",
      toolChain: ["FTQC", "IQM route", "secured worker"],
      inputLabel: "Measured two-device-qubit OpenQASM 3 circuit",
      inputPlaceholder: "OPENQASM 3.0;",
    });
    expect(bellExecution?.examples?.[0]).toMatchObject({
      name: "ftqc-bell.qasm",
      label: "Load Bell input",
    });
    expect(bellExecution?.examples?.[0].content).toContain("OPENQASM 3.0;");
    expect(bellExecution?.examples?.[0].content).toContain("cx q[0], q[1];");
    expect(bellExecution?.hardwareNotice?.detail).toContain("512 shots");
  });
});
