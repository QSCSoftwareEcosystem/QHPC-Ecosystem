import { Handle, Position, type NodeProps } from "@xyflow/react";
import { ArrowDownToLine, ArrowUpFromLine, Box } from "lucide-react";

import type {
  BoundaryNodeData,
  OperationNodeData,
} from "./types";


function shortArtifactType(value: string): string {
  return value.replace(/^qhpc\./, "");
}


export function OperationCanvasNode({
  data,
  selected,
}: NodeProps & { data: OperationNodeData }): React.JSX.Element {
  return (
    <article className={`composer-operation-node${selected ? " is-selected" : ""}`}>
      <header>
        <span className="composer-node-icon" aria-hidden="true">
          <Box size={14} strokeWidth={1.8} />
        </span>
        <span>
          <strong>{data.title}</strong>
          <small>
            {data.operation.capability} / {data.operation.operation}
          </small>
        </span>
      </header>
      <div className="composer-port-columns">
        <div className="composer-port-list composer-port-list-input">
          {Object.entries(data.inputs).map(([name, definition]) => (
            <div className="composer-port" key={name}>
              <Handle
                id={`in:${name}`}
                type="target"
                position={Position.Left}
                title={`${name}: ${definition.artifact_type}`}
              />
              <span>{name}</span>
              <small>{shortArtifactType(definition.artifact_type)}</small>
            </div>
          ))}
        </div>
        <div className="composer-port-list composer-port-list-output">
          {Object.entries(data.outputs).map(([name, definition]) => (
            <div className="composer-port" key={name}>
              <span>{name}</span>
              <small>{shortArtifactType(definition.artifact_type)}</small>
              <Handle
                id={`out:${name}`}
                type="source"
                position={Position.Right}
                title={`${name}: ${definition.artifact_type}`}
              />
            </div>
          ))}
        </div>
      </div>
      <footer>
        <span>v{data.operation.version}</span>
        <span>{Object.keys(data.parameters).length} params</span>
      </footer>
    </article>
  );
}


export function BoundaryCanvasNode({
  data,
  selected,
}: NodeProps & { data: BoundaryNodeData }): React.JSX.Element {
  const input = data.kind === "workflow-input";
  return (
    <article
      className={`composer-boundary-node ${input ? "is-input" : "is-output"}${selected ? " is-selected" : ""}`}
    >
      {input && (
        <Handle
          id={`out:${data.name}`}
          type="source"
          position={Position.Right}
          title={data.artifactType}
        />
      )}
      <span aria-hidden="true">
        {input ? (
          <ArrowUpFromLine size={14} strokeWidth={1.8} />
        ) : (
          <ArrowDownToLine size={14} strokeWidth={1.8} />
        )}
      </span>
      <span>
        <strong>{data.name}</strong>
        <small>{shortArtifactType(data.artifactType)}</small>
      </span>
      {!input && (
        <Handle
          id={`in:${data.name}`}
          type="target"
          position={Position.Left}
          title={data.artifactType}
        />
      )}
    </article>
  );
}
