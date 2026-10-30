import type { WorkflowPreflight } from "./types";


export type PreflightDisplayState =
  | "idle"
  | "checking"
  | "ready"
  | "degraded"
  | "unavailable"
  | "error";

export interface PreflightDisplay {
  status: PreflightDisplayState;
  message: string;
  canQueue: boolean;
  report?: WorkflowPreflight;
}


export function workflowPreflightDisplay(
  report: WorkflowPreflight,
): PreflightDisplay {
  return {
    status: report.state,
    message: report.summary,
    canQueue: report.can_queue,
    report,
  };
}
