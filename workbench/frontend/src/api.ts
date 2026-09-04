import type {
  ArtifactRecord,
  CapabilitySummary,
  DraftLayout,
  DraftValidation,
  KnowledgeGraphSlice,
  KnowledgeNodeRecord,
  KnowledgePath,
  KnowledgeSearchResults,
  KnowledgeSummary,
  PublishedDraft,
  PublishedWorkflow,
  RunRecord,
  RuntimeReadiness,
  Workflow,
  WorkflowDraft,
} from "./types";


const API_ROOT = "/api/v1";


function csrfToken(): string {
  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith("csrftoken="))
    ?.slice("csrftoken=".length) ?? "";
}


export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (init.method && !["GET", "HEAD", "OPTIONS"].includes(init.method)) {
    headers.set("X-CSRFToken", csrfToken());
  }
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const message =
      typeof body === "object" &&
      body !== null &&
      "error" in body &&
      typeof body.error === "string"
        ? body.error
        : `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return body as T;
}


export const composerApi = {
  capabilities(): Promise<CapabilitySummary[]> {
    return request("/capabilities");
  },

  workflows(): Promise<PublishedWorkflow[]> {
    return request("/workflows");
  },

  drafts(): Promise<WorkflowDraft[]> {
    return request("/workflow-drafts?owner=workbench-user");
  },

  draft(id: string): Promise<WorkflowDraft> {
    return request(`/workflow-drafts/${encodeURIComponent(id)}`);
  },

  createDraft(workflow: Workflow, layout: DraftLayout): Promise<WorkflowDraft> {
    return request("/workflow-drafts", {
      method: "POST",
      body: JSON.stringify({
        workflow,
        layout,
        created_by: "workbench-user",
      }),
    });
  },

  updateDraft(
    id: string,
    revision: number,
    workflow: Workflow,
    layout: DraftLayout,
  ): Promise<WorkflowDraft> {
    return request(`/workflow-drafts/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({
        workflow,
        layout,
        expected_revision: revision,
      }),
    });
  },

  deleteDraft(id: string, revision: number): Promise<{ deleted: string }> {
    return request(`/workflow-drafts/${encodeURIComponent(id)}`, {
      method: "DELETE",
      body: JSON.stringify({ expected_revision: revision }),
    });
  },

  validateDraft(id: string, revision: number): Promise<DraftValidation> {
    return request(
      `/workflow-drafts/${encodeURIComponent(id)}/validate`,
      {
        method: "POST",
        body: JSON.stringify({ expected_revision: revision }),
      },
    );
  },

  publishDraft(id: string, revision: number): Promise<PublishedDraft> {
    return request(`/workflow-drafts/${encodeURIComponent(id)}/publish`, {
      method: "POST",
      body: JSON.stringify({
        expected_revision: revision,
        created_by: "workbench-user",
      }),
    });
  },

  runs(): Promise<RunRecord[]> {
    return request("/runs");
  },

  artifacts(): Promise<ArtifactRecord[]> {
    return request("/artifacts");
  },

  createArtifact(
    artifactType: string,
    name: string,
    content: string,
  ): Promise<ArtifactRecord> {
    return request("/artifacts", {
      method: "POST",
      body: JSON.stringify({
        artifact_type: artifactType,
        name,
        content,
        created_by: "workbench-user",
      }),
    });
  },

  submitRun(
    workflowId: string,
    version: string,
    inputs: Record<string, string>,
    executionTarget: string,
  ): Promise<RunRecord> {
    return request("/runs", {
      method: "POST",
      body: JSON.stringify({
        workflow_id: workflowId,
        version,
        inputs,
        execution_target: executionTarget,
        created_by: "workbench-user",
      }),
    });
  },

  readiness(
    executionTarget: string,
    executionClass: string,
    runtimeDigests: string[],
  ): Promise<RuntimeReadiness> {
    const params = new URLSearchParams({
      execution_target: executionTarget,
      execution_class: executionClass,
    });
    runtimeDigests.forEach((digest) => params.append("runtime_digest", digest));
    return request(`/readiness?${params}`);
  },
};


export const knowledgeApi = {
  summary(): Promise<KnowledgeSummary> {
    return request("/knowledge");
  },

  search(
    query: string,
    filters: {
      type?: string;
      domain?: string;
      community?: number;
      limit?: number;
    } = {},
  ): Promise<KnowledgeSearchResults> {
    const params = new URLSearchParams({ query });
    if (filters.type) params.set("type", filters.type);
    if (filters.domain) params.set("domain", filters.domain);
    if (filters.community !== undefined) {
      params.set("community", String(filters.community));
    }
    params.set("limit", String(filters.limit ?? 60));
    return request(`/knowledge/nodes?${params}`);
  },

  node(id: string): Promise<KnowledgeNodeRecord> {
    return request(`/knowledge/nodes/${encodeURIComponent(id)}`);
  },

  neighborhood(id: string, depth = 1): Promise<KnowledgeGraphSlice> {
    return request(
      `/knowledge/neighborhood/${encodeURIComponent(id)}?depth=${depth}`,
    );
  },

  community(index: number): Promise<KnowledgeGraphSlice> {
    return request(`/knowledge/communities/${index}`);
  },

  path(source: string, target: string): Promise<KnowledgePath> {
    const params = new URLSearchParams({ source, target });
    return request(`/knowledge/path?${params}`);
  },
};
