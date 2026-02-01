import React from "react";
import { ModuleHost } from "../../modules/ModuleHost";

export function PayerConsolePage() {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <ModuleHost moduleId="PayerRuleSetEditor" context={{}} />
      <ModuleHost moduleId="PayerPreAuthQueue" context={{}} />
    </div>
  );
}

