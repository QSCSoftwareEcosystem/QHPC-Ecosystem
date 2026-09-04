import type { Edge, Node, Viewport } from "@xyflow/react";


export type ParameterValue = string | number | boolean | null;

export interface ArtifactPort {
  artifact_type: string;
  description?: string;
  required?: boolean;
  multiple?: boolean;
}

export interface ParameterDefinition {
  type: "string" | "integer" | "number" | "boolean";
  title?: string;
  description?: string;
  required?: boolean;
  default?: ParameterValue;
  enum?: ParameterValue[];
  minimum?: number;
  maximum?: number;
}

export interface OperationDefinition {
  id: string;
  title: string;
  description?: string;
  inputs: Record<string, ArtifactPort>;
  outputs: Record<string, ArtifactPort>;
  parameters?: Record<string, ParameterDefinition>;
  runtime: {
    type: string;
    reference: string;
    digest: string;
  };
  execution_targets: string[];
}

export interface CapabilitySummary {
  id: string;
  name: string;
  capability_name?: string;
  version: string;
  project: string;
  description: string;
  guidance?: {
    use_when: string[];
    quick_start: string[];
    example_workflows?: string[];
    limitations?: string[];
  };
  operations: OperationDefinition[];
  validation: {
    status: string;
    evidence: string[];
  };
}

export interface WorkflowOperationReference {
  capability: string;
  version: string;
  operation: string;
}

export interface WorkflowNodeDefinition {
  id: string;
  operation: WorkflowOperationReference;
  parameters: Record<string, ParameterValue>;
  execution_target?: string;
  execution_class?:
    | "interactive-local"
    | "interactive-hpc-pilot"
    | "batch-hpc"
    | "quantum-backend";
}

export interface WorkflowEndpoint {
  node: string;
  port: string;
  artifact_type: string;
}

export interface WorkflowEdgeDefinition {
  from: WorkflowEndpoint;
  to: WorkflowEndpoint;
}

export interface WorkflowInputDefinition {
  artifact_type: string;
  required?: boolean;
  to: {
    node: string;
    port: string;
  };
}

export interface WorkflowOutputDefinition {
  artifact_type: string;
  from: {
    node: string;
    port: string;
  };
}

export interface Workflow {
  api_version: "qhpc/v1";
  kind: "Workflow";
  metadata: {
    id: string;
    name: string;
    version: string;
    owner: string;
    visibility: "private" | "project" | "internal" | "public";
    description?: string;
  };
  spec: {
    nodes: WorkflowNodeDefinition[];
    edges: WorkflowEdgeDefinition[];
    inputs: Record<string, WorkflowInputDefinition>;
    outputs: Record<string, WorkflowOutputDefinition>;
  };
}

export interface PublishedWorkflow {
  id: string;
  version: string;
  digest: string;
  registry_digest: string;
  created_at: string;
  created_by: string;
  definition: Workflow;
}

export type CanvasNodeKind =
  | "operation"
  | "workflow-input"
  | "workflow-output";

export interface DraftLayout {
  nodes: Array<{
    id: string;
    kind: CanvasNodeKind;
    position: {
      x: number;
      y: number;
    };
  }>;
  viewport: Viewport;
}

export interface WorkflowDraft {
  api_version: "qhpc/v1";
  kind: "WorkflowDraft";
  metadata: {
    id: string;
    name: string;
    owner: string;
    revision: number;
    created_at: string;
    updated_at: string;
  };
  spec: {
    workflow: Workflow;
    layout: DraftLayout;
  };
}

export interface OperationNodeData extends Record<string, unknown> {
  kind: "operation";
  title: string;
  project: string;
  operation: WorkflowOperationReference;
  parameters: Record<string, ParameterValue>;
  parameterDefinitions: Record<string, ParameterDefinition>;
  inputs: Record<string, ArtifactPort>;
  outputs: Record<string, ArtifactPort>;
  sequence: number;
  originalNode: WorkflowNodeDefinition;
}

export interface BoundaryNodeData extends Record<string, unknown> {
  kind: "workflow-input" | "workflow-output";
  name: string;
  artifactType: string;
  required?: boolean;
  requiredWasSet?: boolean;
  sequence: number;
}

export type ComposerNode =
  | Node<OperationNodeData, "operation">
  | Node<BoundaryNodeData, "boundary">;

export interface ComposerEdgeData extends Record<string, unknown> {
  kind: "internal" | "workflow-input" | "workflow-output";
  artifactType: string;
  sequence: number;
  boundaryName?: string;
  originalEdge?: WorkflowEdgeDefinition;
}

export type ComposerEdge = Edge<ComposerEdgeData>;

export interface CanvasDocument {
  nodes: ComposerNode[];
  edges: ComposerEdge[];
  viewport: Viewport;
}

export interface ValidationIssue {
  code: string;
  message: string;
  nodeId?: string;
  edgeId?: string;
}

export interface DraftValidation {
  draft_id: string;
  revision: number;
  valid: boolean;
  digest?: string;
  node_ids?: string[];
  issues: Array<{
    path: string;
    message: string;
  }>;
  message?: string;
}

export interface PublishedDraft {
  draft_id: string;
  revision: number;
  workflow: PublishedWorkflow;
}

export interface RunRecord {
  id: string;
  workflow_id: string;
  workflow_version: string;
  state: string;
  outputs: Record<string, string>;
}

export interface RuntimeReadiness {
  ready: boolean;
  reason: string;
  stale_after_seconds: number;
  requirements: Array<{
    node_id: string;
    execution_target: string;
    execution_class: string;
    runtime_digest: string;
    ready: boolean;
    compatible_workers: string[];
  }>;
  workers: Array<Record<string, unknown>>;
}

export interface ArtifactRecord {
  id: string;
  artifact_type: string;
  name?: string;
  checksum: string;
  size_bytes: number;
  provenance: string;
  uri: string;
}

export interface KnowledgeCommunity {
  index: number;
  label: string;
  size: number;
  god_node?: string | null;
  domains: string[];
  internal_edges: number;
  external_edges: number;
  cohesion: number;
}

export interface KnowledgeCommunityEdge {
  source: number;
  target: number;
  count: number;
  confidence: Record<string, number>;
}

export interface KnowledgeSummary {
  available: boolean;
  reason?: string;
  schema_version?: string;
  generated?: string;
  source_revision?: string;
  stats?: {
    content_nodes: number;
    all_nodes: number;
    edges: number;
    communities: number;
    by_type: Record<string, number>;
    by_provenance: Record<string, number>;
  };
  communities?: KnowledgeCommunity[];
  community_edges?: KnowledgeCommunityEdge[];
}

export interface KnowledgeNodeSummary {
  id: string;
  title: string;
  type: string;
  domains: string[];
  status?: string | null;
  provenance_status?: string | null;
  community?: number | null;
  community_label?: string | null;
  freshness?: string | null;
  freshness_rollup?: string | null;
  synthetic: boolean;
  degree: number;
}

export interface KnowledgeEdge {
  source: string;
  target: string;
  relation: string;
  confidence: "EXTRACTED" | "INFERRED" | "AMBIGUOUS";
  origin?: string | null;
}

export interface KnowledgeGraphSlice {
  nodes: KnowledgeNodeSummary[];
  edges: KnowledgeEdge[];
  truncated?: boolean;
  center?: string;
  depth?: number;
  community?: KnowledgeCommunity;
}

export interface KnowledgeNodeEdge extends KnowledgeEdge {
  node: KnowledgeNodeSummary;
}

export interface KnowledgeCitation {
  source: string;
  title: string;
  type: string;
  origin?: string | null;
  confidence: string;
}

export interface KnowledgeNodeRecord extends KnowledgeNodeSummary {
  rel_path?: string | null;
  version_built?: string | null;
  version_scope?: string | null;
  version_source?: unknown;
  outgoing: KnowledgeNodeEdge[];
  incoming: KnowledgeNodeEdge[];
  citations: KnowledgeCitation[];
}

export interface KnowledgeSearchResults {
  query: string;
  total: number;
  limit: number;
  items: KnowledgeNodeSummary[];
}

export interface KnowledgePath extends KnowledgeGraphSlice {
  found: boolean;
  source: string;
  target: string;
  path: string[];
  length?: number;
}

declare global {
  interface Window {
    QHPCComposer?: {
      mount: (element: HTMLElement) => void;
      unmount: () => void;
    };
    QHPCKnowledge?: {
      mount: (
        element: HTMLElement,
        options?: { initialNodeId?: string | null },
      ) => void;
      unmount: () => void;
    };
  }
}
