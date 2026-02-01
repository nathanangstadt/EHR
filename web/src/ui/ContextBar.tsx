import React from "react";
import { useAppContext } from "./context";

export function ContextBar() {
  const { state, dispatch } = useAppContext();
  return (
    <div className="contextBar">
      <div className="row">
        <span className="muted">Active Patient</span>
        <input
          value={state.patientId ?? ""}
          placeholder="Patient UUID"
          onChange={(e) =>
            dispatch({ type: "setPatient", patientId: e.target.value || undefined })
          }
          style={{ width: 280 }}
        />
      </div>
      <div className="row">
        <span className="muted">Active Encounter</span>
        <input
          value={state.encounterId ?? ""}
          placeholder="Encounter UUID (optional)"
          onChange={(e) =>
            dispatch({
              type: "setEncounter",
              encounterId: e.target.value || undefined,
            })
          }
          style={{ width: 280 }}
        />
      </div>
      <div className="row">
        <span className="muted">Correlation ID</span>
        <input
          value={state.correlationId}
          onChange={(e) =>
            dispatch({ type: "setCorrelationId", correlationId: e.target.value })
          }
          style={{ width: 320 }}
        />
      </div>
      <div className="row">
        <span className="muted">User</span>
        <span>{state.userDisplay}</span>
      </div>
    </div>
  );
}

