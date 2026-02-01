import React, { useEffect, useState } from "react";
import { ModuleHost } from "../../modules/ModuleHost";
import { useAppContext } from "../context";
import { subscribe } from "../eventBus";

export function WorkspacePage() {
  const { state, dispatch } = useAppContext();
  const [selectedEventRef, setSelectedEventRef] = useState<any>(null);

  useEffect(() => {
    return subscribe((e) => {
      if (e.type === "selectEventRef") setSelectedEventRef(e.payload);
      if (e.type === "setEncounterId") dispatch({ type: "setEncounter", encounterId: e.payload.encounterId });
      if (e.type === "setJobId") dispatch({ type: "setJob", jobId: e.payload.jobId });
      if (e.type === "setPreAuthId") dispatch({ type: "setPreAuth", preAuthId: e.payload.preAuthId });
    });
  }, []);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 12 }}>
      <div className="card">
        <strong>Activity</strong>
        <div className="muted" style={{ marginTop: 6 }}>
          Phase 1 placeholder. Phase 2 agent orchestration can drive this.
        </div>
      </div>
      <div style={{ display: "grid", gap: 12 }}>
        <ModuleHost moduleId="PatientSummaryCard" context={{ patientId: state.patientId }} />
        <div className="grid2">
          <ModuleHost
            moduleId="TimelineList"
            context={{ patientId: state.patientId, encounterId: state.encounterId }}
            onOutput={(o) => setSelectedEventRef(o.selectedEventRef)}
          />
          <ModuleHost
            moduleId="ClinicalEventDetailDrawer"
            context={{
              patientId: state.patientId,
              encounterId: state.encounterId,
              correlationId: state.correlationId,
            }}
            inputs={{ selectedEventRef }}
          />
        </div>
        {state.jobId && <ModuleHost moduleId="JobDetailPanel" context={{ jobId: state.jobId }} />}
      </div>
    </div>
  );
}
