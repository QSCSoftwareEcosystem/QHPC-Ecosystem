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
