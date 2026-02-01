import React, { useState } from "react";
import { ModuleHost } from "../../modules/ModuleHost";
import { useAppContext } from "../context";

export function PatientsPage() {
  const { state } = useAppContext();
  const [selectedPatientId, setSelectedPatientId] = useState<string | undefined>(state.patientId);

  return (
    <div className="grid2">
      <ModuleHost
        moduleId="PatientSearchPanel"
        context={{ correlationId: state.correlationId }}
        onOutput={(o) => setSelectedPatientId(o.selectedPatientId)}
      />
      <ModuleHost moduleId="PatientCreateForm" context={{ correlationId: state.correlationId }} />
    </div>
  );
}

