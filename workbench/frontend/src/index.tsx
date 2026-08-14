import "@xyflow/react/dist/style.css";
import "./composer.css";
import "./knowledge.css";

import { createRoot, type Root } from "react-dom/client";

import { ComposerApp } from "./ComposerApp";
import { KnowledgeExplorer } from "./KnowledgeExplorer";


let composerRoot: Root | null = null;
let composerElement: HTMLElement | null = null;
let knowledgeRoot: Root | null = null;
let knowledgeElement: HTMLElement | null = null;


window.QHPCComposer = {
  mount(element: HTMLElement): void {
    if (composerRoot && composerElement === element) return;
    composerRoot?.unmount();
    composerElement = element;
    composerRoot = createRoot(element);
    composerRoot.render(<ComposerApp />);
  },

  unmount(): void {
    composerRoot?.unmount();
    composerRoot = null;
    composerElement = null;
  },
};

window.QHPCKnowledge = {
  mount(
    element: HTMLElement,
    options?: { initialNodeId?: string | null },
  ): void {
    knowledgeRoot?.unmount();
    knowledgeElement = element;
    knowledgeRoot = createRoot(element);
    knowledgeRoot.render(
      <KnowledgeExplorer initialNodeId={options?.initialNodeId ?? null} />,
    );
  },

  unmount(): void {
    knowledgeRoot?.unmount();
    knowledgeRoot = null;
    knowledgeElement = null;
  },
};

window.dispatchEvent(new CustomEvent("qhpc-composer-ready"));
window.dispatchEvent(new CustomEvent("qhpc-knowledge-ready"));
