import type { PublishedWorkflow } from "./types";


interface ParsedVersion {
  core: number[];
  prerelease: string[] | null;
}


function parseVersion(value: string): ParsedVersion | null {
  const match = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/.exec(value);
  if (!match) return null;
  return {
    core: [Number(match[1]), Number(match[2]), Number(match[3])],
    prerelease: match[4]?.split(".") ?? null,
  };
}


function comparePrerelease(left: string[] | null, right: string[] | null): number {
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  const length = Math.max(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const leftPart = left[index];
    const rightPart = right[index];
    if (leftPart === undefined) return -1;
    if (rightPart === undefined) return 1;
    const leftNumeric = /^\d+$/.test(leftPart);
    const rightNumeric = /^\d+$/.test(rightPart);
    if (leftNumeric && rightNumeric) {
      const difference = Number(leftPart) - Number(rightPart);
      if (difference) return difference;
      continue;
    }
    if (leftNumeric) return -1;
    if (rightNumeric) return 1;
    const difference = leftPart.localeCompare(rightPart);
    if (difference) return difference;
  }
  return 0;
}


export function compareWorkflowVersions(left: string, right: string): number {
  const leftVersion = parseVersion(left);
  const rightVersion = parseVersion(right);
  if (leftVersion === null || rightVersion === null) {
    return left.localeCompare(right);
  }
  for (let index = 0; index < leftVersion.core.length; index += 1) {
    const difference = leftVersion.core[index] - rightVersion.core[index];
    if (difference) return difference;
  }
  return comparePrerelease(leftVersion.prerelease, rightVersion.prerelease);
}


/** Present one runnable definition per workflow ID while preserving history in the API. */
export function latestWorkflowVersions(
  workflows: PublishedWorkflow[],
): PublishedWorkflow[] {
  const latest = new Map<string, PublishedWorkflow>();
  for (const workflow of workflows) {
    const current = latest.get(workflow.id);
    if (!current || compareWorkflowVersions(workflow.version, current.version) > 0) {
      latest.set(workflow.id, workflow);
    }
  }
  return [...latest.values()].sort((left, right) => left.id.localeCompare(right.id));
}
