import React from "react";
import { ModuleHost } from "../../modules/ModuleHost";

export function ModelInspectorPage() {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <ModuleHost moduleId="AdminTools" context={{}} />
      <ModuleHost moduleId="FHIRRequestComposer" context={{}} />
      <ModuleHost moduleId="MappingTraceViewer" context={{}} />
    </div>
  );
}
