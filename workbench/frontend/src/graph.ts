import type { Connection, Viewport } from "@xyflow/react";

import type {
  ArtifactPort,
  BoundaryNodeData,
  CanvasDocument,
  CapabilitySummary,
  ComposerEdge,
  ComposerNode,
  DraftLayout,
  OperationDefinition,
  OperationNodeData,
  ParameterValue,
  ValidationIssue,
  Workflow,
  WorkflowEdgeDefinition,
  WorkflowInputDefinition,
  WorkflowNodeDefinition,
  WorkflowOutputDefinition,
} from "./types";


const DEFAULT_VIEWPORT: Viewport = { x: 0, y: 0, zoom: 1 };
const OPERATION_X_GAP = 310;
const OPERATION_Y_GAP = 210;


function clone<T>(value: T): T {
  return structuredClone(value);
}


export function operationKey(
  capabilityId: string,
  version: string,
  operationId: string,
): string {
  return `${capabilityId}@${version}/${operationId}`;
}


export function capabilityOperationIndex(
  capabilities: CapabilitySummary[],
): Map<string, { capability: CapabilitySummary; operation: OperationDefinition }> {
  const result = new Map<
    string,
    { capability: CapabilitySummary; operation: OperationDefinition }
  >();
  for (const capability of capabilities) {
    for (const operation of capability.operations) {
      result.set(
        operationKey(capability.id, capability.version, operation.id),
        { capability, operation },
      );
    }
  }
  return result;
}


function fallbackPosition(index: number): { x: number; y: number } {
  return {
    x: 220 + (index % 3) * OPERATION_X_GAP,
    y: 90 + Math.floor(index / 3) * OPERATION_Y_GAP,
  };
}


function positionFor(
  id: string,
  kind: DraftLayout["nodes"][number]["kind"],
  layout: DraftLayout | undefined,
  fallback: { x: number; y: number },
): { x: number; y: number } {
  const item = layout?.nodes.find(
    (candidate) => candidate.id === id && candidate.kind === kind,
  );
  return item ? clone(item.position) : fallback;
}


function inferredPorts(
  nodeId: string,
  workflow: Workflow,
): {
  inputs: Record<string, ArtifactPort>;
  outputs: Record<string, ArtifactPort>;
} {
  const inputs: Record<string, ArtifactPort> = {};
  const outputs: Record<string, ArtifactPort> = {};
  for (const edge of workflow.spec.edges) {
    if (edge.to.node === nodeId) {
      inputs[edge.to.port] = { artifact_type: edge.to.artifact_type };
    }
    if (edge.from.node === nodeId) {
      outputs[edge.from.port] = { artifact_type: edge.from.artifact_type };
    }
  }
  for (const definition of Object.values(workflow.spec.inputs)) {
    if (definition.to.node === nodeId) {
      inputs[definition.to.port] = {
        artifact_type: definition.artifact_type,
        required: definition.required,
      };
    }
  }
  for (const definition of Object.values(workflow.spec.outputs)) {
    if (definition.from.node === nodeId) {
      outputs[definition.from.port] = {
        artifact_type: definition.artifact_type,
      };
    }
  }
  return { inputs, outputs };
}


function operationNode(
  definition: WorkflowNodeDefinition,
  sequence: number,
  workflow: Workflow,
  layout: DraftLayout | undefined,
  operations: ReturnType<typeof capabilityOperationIndex>,
): ComposerNode {
  const match = operations.get(
    operationKey(
      definition.operation.capability,
      definition.operation.version,
      definition.operation.operation,
    ),
  );
  const inferred = inferredPorts(definition.id, workflow);
  const data: OperationNodeData = {
    kind: "operation",
    title: match?.operation.title ?? definition.operation.operation,
    project: match?.capability.project ?? "unregistered",
    operation: clone(definition.operation),
    parameters: clone(definition.parameters),
    parameterDefinitions: clone(match?.operation.parameters ?? {}),
    inputs: clone(match?.operation.inputs ?? inferred.inputs),
    outputs: clone(match?.operation.outputs ?? inferred.outputs),
    sequence,
    originalNode: clone(definition),
  };
  return {
    id: definition.id,
    type: "operation",
    position: positionFor(
      definition.id,
      "operation",
      layout,
      fallbackPosition(sequence),
    ),
    data,
  };
}


function inputBoundaryNode(
  name: string,
  definition: WorkflowInputDefinition,
  sequence: number,
  layout: DraftLayout | undefined,
  targetPosition: { x: number; y: number } | undefined,
): ComposerNode {
  const id = `input:${name}`;
  const data: BoundaryNodeData = {
    kind: "workflow-input",
    name,
    artifactType: definition.artifact_type,
    required: definition.required,
    requiredWasSet: Object.hasOwn(definition, "required"),
    sequence,
  };
  return {
    id,
    type: "boundary",
    position: positionFor(id, "workflow-input", layout, {
      x: Math.max(10, (targetPosition?.x ?? 220) - 210),
      y: (targetPosition?.y ?? 90) + sequence * 72,
    }),
    data,
  };
}


function outputBoundaryNode(
  name: string,
  definition: WorkflowOutputDefinition,
  sequence: number,
  layout: DraftLayout | undefined,
  sourcePosition: { x: number; y: number } | undefined,
): ComposerNode {
  const id = `output:${name}`;
  const data: BoundaryNodeData = {
    kind: "workflow-output",
    name,
    artifactType: definition.artifact_type,
    sequence,
  };
  return {
    id,
    type: "boundary",
    position: positionFor(id, "workflow-output", layout, {
      x: (sourcePosition?.x ?? 220) + 280,
      y: (sourcePosition?.y ?? 90) + sequence * 72,
    }),
    data,
  };
}


export function workflowToCanvas(
  workflow: Workflow,
  layout: DraftLayout | undefined,
  capabilities: CapabilitySummary[],
): CanvasDocument {
  const operations = capabilityOperationIndex(capabilities);
  const nodes: ComposerNode[] = workflow.spec.nodes.map((definition, index) =>
    operationNode(definition, index, workflow, layout, operations),
  );
  const operationPositions = new Map(
    nodes.map((node) => [node.id, node.position]),
  );

  const inputEntries = Object.entries(workflow.spec.inputs);
  for (const [index, [name, definition]] of inputEntries.entries()) {
    nodes.push(
      inputBoundaryNode(
        name,
        definition,
        index,
        layout,
        operationPositions.get(definition.to.node),
      ),
    );
  }
  const outputEntries = Object.entries(workflow.spec.outputs);
  for (const [index, [name, definition]] of outputEntries.entries()) {
    nodes.push(
      outputBoundaryNode(
        name,
        definition,
        index,
        layout,
        operationPositions.get(definition.from.node),
      ),
    );
  }

  const edges: ComposerEdge[] = workflow.spec.edges.map((definition, index) => ({
    id: `edge:${index}:${definition.from.node}:${definition.from.port}:${definition.to.node}:${definition.to.port}`,
    source: definition.from.node,
    sourceHandle: `out:${definition.from.port}`,
    target: definition.to.node,
    targetHandle: `in:${definition.to.port}`,
    type: "smoothstep",
    data: {
      kind: "internal",
      artifactType: definition.from.artifact_type,
      sequence: index,
      originalEdge: clone(definition),
    },
  }));
  for (const [index, [name, definition]] of inputEntries.entries()) {
    edges.push({
      id: `workflow-input:${name}`,
      source: `input:${name}`,
      sourceHandle: `out:${name}`,
      target: definition.to.node,
      targetHandle: `in:${definition.to.port}`,
      type: "smoothstep",
      data: {
        kind: "workflow-input",
        artifactType: definition.artifact_type,
        sequence: index,
        boundaryName: name,
      },
    });
  }
  for (const [index, [name, definition]] of outputEntries.entries()) {
    edges.push({
      id: `workflow-output:${name}`,
      source: definition.from.node,
      sourceHandle: `out:${definition.from.port}`,
      target: `output:${name}`,
      targetHandle: `in:${name}`,
      type: "smoothstep",
      data: {
        kind: "workflow-output",
        artifactType: definition.artifact_type,
        sequence: index,
        boundaryName: name,
      },
    });
  }
  return {
    nodes,
    edges,
    viewport: clone(layout?.viewport ?? DEFAULT_VIEWPORT),
  };
}


function portFromHandle(handle: string | null | undefined, prefix: string): string {
  if (!handle?.startsWith(prefix)) {
    throw new Error(`connection handle must start with ${prefix}`);
  }
  return handle.slice(prefix.length);
}


function sortedBySequence<T extends { data?: { sequence?: number } }>(
  values: T[],
): T[] {
  return [...values].sort(
    (left, right) =>
      (left.data?.sequence ?? Number.MAX_SAFE_INTEGER) -
      (right.data?.sequence ?? Number.MAX_SAFE_INTEGER),
  );
}


export function canvasToWorkflow(
  metadata: Workflow["metadata"],
  nodes: ComposerNode[],
  edges: ComposerEdge[],
): Workflow {
  const operationNodes = sortedBySequence(
    nodes.filter(
      (node): node is Extract<ComposerNode, { type: "operation" }> =>
        node.type === "operation",
    ),
  );
  const workflowNodes = operationNodes.map((node) => ({
    ...clone(node.data.originalNode),
    id: node.id,
    operation: clone(node.data.operation),
    parameters: clone(node.data.parameters),
  }));

  const internalEdges = sortedBySequence(
    edges.filter((edge) => edge.data?.kind === "internal"),
  ).map((edge): WorkflowEdgeDefinition => {
    const fromPort = portFromHandle(edge.sourceHandle, "out:");
    const toPort = portFromHandle(edge.targetHandle, "in:");
    const original = edge.data?.originalEdge;
    return {
      from: {
        node: edge.source,
        port: fromPort,
        artifact_type:
          original?.from.artifact_type ?? edge.data?.artifactType ?? "",
      },
      to: {
        node: edge.target,
        port: toPort,
        artifact_type:
          original?.to.artifact_type ?? edge.data?.artifactType ?? "",
      },
    };
  });

  const inputs: Record<string, WorkflowInputDefinition> = {};
  for (const edge of sortedBySequence(
    edges.filter((candidate) => candidate.data?.kind === "workflow-input"),
  )) {
    const boundary = nodes.find(
      (node) =>
        node.id === edge.source && node.data.kind === "workflow-input",
    );
    if (!boundary || boundary.data.kind !== "workflow-input") continue;
    const definition: WorkflowInputDefinition = {
      artifact_type: boundary.data.artifactType,
      to: {
        node: edge.target,
        port: portFromHandle(edge.targetHandle, "in:"),
      },
    };
    if (boundary.data.requiredWasSet) {
      definition.required = boundary.data.required;
    }
    inputs[boundary.data.name] = definition;
  }

  const outputs: Record<string, WorkflowOutputDefinition> = {};
  for (const edge of sortedBySequence(
    edges.filter((candidate) => candidate.data?.kind === "workflow-output"),
  )) {
    const boundary = nodes.find(
      (node) =>
        node.id === edge.target && node.data.kind === "workflow-output",
    );
    if (!boundary || boundary.data.kind !== "workflow-output") continue;
    outputs[boundary.data.name] = {
      artifact_type: boundary.data.artifactType,
      from: {
        node: edge.source,
        port: portFromHandle(edge.sourceHandle, "out:"),
      },
    };
  }

  return {
    api_version: "qhpc/v1",
    kind: "Workflow",
    metadata: clone(metadata),
    spec: {
      nodes: workflowNodes,
      edges: internalEdges,
      inputs,
      outputs,
    },
  };
}


export function layoutFromCanvas(
  nodes: ComposerNode[],
  viewport: Viewport,
): DraftLayout {
  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      kind: node.data.kind,
      position: clone(node.position),
    })),
    viewport: clone(viewport),
  };
}


export function createEmptyWorkflow(): Workflow {
  return {
    api_version: "qhpc/v1",
    kind: "Workflow",
    metadata: {
      id: "untitled-workflow",
      name: "Untitled workflow",
      version: "0.1.0",
      owner: "workbench-user",
      visibility: "internal",
    },
    spec: {
      nodes: [],
      edges: [],
      inputs: {},
      outputs: {},
    },
  };
}


export function createOperationCanvasNode(
  capability: CapabilitySummary,
  operation: OperationDefinition,
  id: string,
  position: { x: number; y: number },
  sequence: number,
): ComposerNode {
  const parameters = Object.fromEntries(
    Object.entries(operation.parameters ?? {})
      .filter(([, definition]) => Object.hasOwn(definition, "default"))
      .map(([name, definition]) => [name, definition.default as ParameterValue]),
  );
  const originalNode: WorkflowNodeDefinition = {
    id,
    operation: {
      capability: capability.id,
      version: capability.version,
      operation: operation.id,
    },
    parameters,
  };
  return {
    id,
    type: "operation",
    position,
    data: {
      kind: "operation",
      title: operation.title,
      project: capability.project,
      operation: clone(originalNode.operation),
      parameters,
      parameterDefinitions: clone(operation.parameters ?? {}),
      inputs: clone(operation.inputs),
      outputs: clone(operation.outputs),
      sequence,
      originalNode,
    },
  };
}


function artifactTypeForHandle(
  node: ComposerNode,
  handle: string | null | undefined,
  direction: "source" | "target",
): string | undefined {
  if (node.data.kind === "operation") {
    const prefix = direction === "source" ? "out:" : "in:";
    if (!handle?.startsWith(prefix)) return undefined;
    const port = handle.slice(prefix.length);
    return direction === "source"
      ? node.data.outputs[port]?.artifact_type
      : node.data.inputs[port]?.artifact_type;
  }
  return node.data.artifactType;
}


function operationPathExists(
  start: string,
  target: string,
  edges: ComposerEdge[],
): boolean {
  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    if (edge.data?.kind !== "internal") continue;
    adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), edge.target]);
  }
  const pending = [start];
  const visited = new Set<string>();
  while (pending.length) {
    const node = pending.pop();
    if (!node || visited.has(node)) continue;
    if (node === target) return true;
    visited.add(node);
    pending.push(...(adjacency.get(node) ?? []));
  }
  return false;
}


export function validateConnection(
  connection: Connection,
  nodes: ComposerNode[],
  edges: ComposerEdge[],
): { valid: boolean; message?: string } {
  const source = nodes.find((node) => node.id === connection.source);
  const target = nodes.find((node) => node.id === connection.target);
  if (!source || !target) {
    return { valid: false, message: "Both connection endpoints are required." };
  }
  if (source.id === target.id) {
    return { valid: false, message: "An operation cannot connect to itself." };
  }
  if (
    source.data.kind === "workflow-output" ||
    target.data.kind === "workflow-input" ||
    (source.data.kind === "workflow-input" &&
      target.data.kind !== "operation") ||
    (target.data.kind === "workflow-output" &&
      source.data.kind !== "operation")
  ) {
    return { valid: false, message: "Connection direction is not valid." };
  }
  const sourceType = artifactTypeForHandle(
    source,
    connection.sourceHandle,
    "source",
  );
  const targetType = artifactTypeForHandle(
    target,
    connection.targetHandle,
    "target",
  );
  if (!sourceType || !targetType) {
    return { valid: false, message: "Select a named input and output port." };
  }
  if (sourceType !== targetType) {
    return {
      valid: false,
      message: `${sourceType} cannot connect to ${targetType}.`,
    };
  }
  if (
    edges.some(
      (edge) =>
        edge.target === connection.target &&
        edge.targetHandle === connection.targetHandle,
    )
  ) {
    return { valid: false, message: "That input already has a connection." };
  }
  if (
    source.data.kind === "operation" &&
    target.data.kind === "operation" &&
    operationPathExists(target.id, source.id, edges)
  ) {
    return { valid: false, message: "The connection would create a cycle." };
  }
  return { valid: true };
}


export function connectionEdge(
  connection: Connection,
  nodes: ComposerNode[],
  sequence: number,
): ComposerEdge {
  const source = nodes.find((node) => node.id === connection.source);
  const target = nodes.find((node) => node.id === connection.target);
  if (!source || !target) throw new Error("connection endpoints are unavailable");
  const artifactType = artifactTypeForHandle(
    source,
    connection.sourceHandle,
    "source",
  );
  if (!artifactType) throw new Error("connection source has no artifact type");
  let kind: NonNullable<ComposerEdge["data"]>["kind"] = "internal";
  let boundaryName: string | undefined;
  if (source.data.kind === "workflow-input") {
    kind = "workflow-input";
    boundaryName = source.data.name;
  } else if (target.data.kind === "workflow-output") {
    kind = "workflow-output";
    boundaryName = target.data.name;
  }
  return {
    id: `edge:${crypto.randomUUID()}`,
    source: source.id,
    sourceHandle: connection.sourceHandle,
    target: target.id,
    targetHandle: connection.targetHandle,
    type: "smoothstep",
    data: { kind, artifactType, sequence, boundaryName },
  };
}


export function validateCanvas(
  nodes: ComposerNode[],
  edges: ComposerEdge[],
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const operationNodes = nodes.filter(
    (
      node,
    ): node is Extract<ComposerNode, { type: "operation" }> =>
      node.type === "operation",
  );
  if (!operationNodes.length) {
    issues.push({
      code: "workflow.empty",
      message: "Add at least one operation.",
    });
  }
  const ids = new Set<string>();
  for (const node of operationNodes) {
    if (ids.has(node.id)) {
      issues.push({
        code: "node.duplicate",
        message: `Operation id ${node.id} is duplicated.`,
        nodeId: node.id,
      });
    }
    ids.add(node.id);
    for (const [port, definition] of Object.entries(node.data.inputs)) {
      if (definition.required === false) continue;
      const connected = edges.some(
        (edge) =>
          edge.target === node.id && edge.targetHandle === `in:${port}`,
      );
      if (!connected) {
        issues.push({
          code: "input.required",
          message: `${node.id}.${port} requires an input.`,
          nodeId: node.id,
        });
      }
    }
  }
  for (const node of nodes) {
    if (node.data.kind === "workflow-input") {
      if (!edges.some((edge) => edge.source === node.id)) {
        issues.push({
          code: "boundary.disconnected",
          message: `Workflow input ${node.data.name} is disconnected.`,
          nodeId: node.id,
        });
      }
    } else if (node.data.kind === "workflow-output") {
      if (!edges.some((edge) => edge.target === node.id)) {
        issues.push({
          code: "boundary.disconnected",
          message: `Workflow output ${node.data.name} is disconnected.`,
          nodeId: node.id,
        });
      }
    }
  }
  for (const edge of edges) {
    const result = validateConnection(
      {
        source: edge.source,
        sourceHandle: edge.sourceHandle ?? null,
        target: edge.target,
        targetHandle: edge.targetHandle ?? null,
      },
      nodes,
      edges.filter((candidate) => candidate.id !== edge.id),
    );
    if (!result.valid) {
      issues.push({
        code: "edge.invalid",
        message: result.message ?? "Connection is invalid.",
        edgeId: edge.id,
      });
    }
  }
  return issues;
}


export function uniqueNodeId(base: string, nodes: ComposerNode[]): string {
  const normalized =
    base
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, "-")
      .replace(/^[^a-z]+/, "")
      .replace(/-+$/g, "") || "operation";
  const existing = new Set(nodes.map((node) => node.id));
  if (!existing.has(normalized)) return normalized;
  let suffix = 2;
  while (existing.has(`${normalized}-${suffix}`)) suffix += 1;
  return `${normalized}-${suffix}`;
}


export function uniqueBoundaryName(
  base: string,
  kind: "workflow-input" | "workflow-output",
  nodes: ComposerNode[],
): string {
  const normalized =
    base
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, "_")
      .replace(/^[^a-z]+/, "")
      .replace(/_+$/g, "") || (kind === "workflow-input" ? "input" : "output");
  const existing = new Set(
    nodes
      .filter((node) => node.data.kind === kind)
      .map((node) =>
        node.data.kind === "workflow-input" ||
        node.data.kind === "workflow-output"
          ? node.data.name
          : "",
      ),
  );
  if (!existing.has(normalized)) return normalized;
  let suffix = 2;
  while (existing.has(`${normalized}_${suffix}`)) suffix += 1;
  return `${normalized}_${suffix}`;
}


export function createBoundaryForPort(
  operationNode: Extract<ComposerNode, { type: "operation" }>,
  port: string,
  kind: "workflow-input" | "workflow-output",
  nodes: ComposerNode[],
  edgeSequence: number,
): { node: ComposerNode; edge: ComposerEdge } {
  const definition =
    kind === "workflow-input"
      ? operationNode.data.inputs[port]
      : operationNode.data.outputs[port];
  if (!definition) throw new Error(`port is unavailable: ${port}`);
  const name = uniqueBoundaryName(port, kind, nodes);
  const id = `${kind === "workflow-input" ? "input" : "output"}:${name}`;
  const node: ComposerNode = {
    id,
    type: "boundary",
    position: {
      x:
        operationNode.position.x +
        (kind === "workflow-input" ? -210 : 280),
      y: operationNode.position.y,
    },
    data: {
      kind,
      name,
      artifactType: definition.artifact_type,
      required:
        kind === "workflow-input" ? definition.required ?? true : undefined,
      requiredWasSet: kind === "workflow-input",
      sequence: nodes.filter((item) => item.data.kind === kind).length,
    },
  };
  const source = kind === "workflow-input" ? node : operationNode;
  const target = kind === "workflow-input" ? operationNode : node;
  const edge: ComposerEdge = {
    id: `${kind}:${name}`,
    source: source.id,
    sourceHandle:
      kind === "workflow-input" ? `out:${name}` : `out:${port}`,
    target: target.id,
    targetHandle: kind === "workflow-input" ? `in:${port}` : `in:${name}`,
    type: "smoothstep",
    data: {
      kind,
      artifactType: definition.artifact_type,
      sequence: edgeSequence,
      boundaryName: name,
    },
  };
  return { node, edge };
}
