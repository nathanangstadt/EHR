import React, { useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

export function PatientCreateForm({ context, onOutput }: any) {
  const { state, dispatch } = useAppContext();
  const [family, setFamily] = useState("Smith");
  const [given, setGiven] = useState("Sam");
  const [mrn, setMrn] = useState(`MRN-${Math.floor(1000 + Math.random() * 8999)}`);
  const [birthDate, setBirthDate] = useState("1990-01-01");
  const [out, setOut] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    setErr(null);
    try {
      const res = await apiFetch("/fhir/Patient", {
        method: "POST",
        correlationId: state.correlationId,
        body: JSON.stringify({
          resourceType: "Patient",
          identifier: [{ system: "urn:mrn", value: mrn }],
          name: [{ family, given: [given] }],
          birthDate,
        }),
      });
      setOut(res);
      dispatch({ type: "setPatient", patientId: res.id });
      onOutput?.({ createdPatientId: res.id });
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <div className="grid2">
        <div className="row">
          <span className="muted">Family</span>
          <input value={family} onChange={(e) => setFamily(e.target.value)} />
        </div>
        <div className="row">
          <span className="muted">Given</span>
          <input value={given} onChange={(e) => setGiven(e.target.value)} />
        </div>
        <div className="row">
          <span className="muted">MRN</span>
          <input value={mrn} onChange={(e) => setMrn(e.target.value)} />
        </div>
        <div className="row">
          <span className="muted">Birthdate</span>
          <input value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
        </div>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <button onClick={() => create()}>Create</button>
        <span className="muted">Uses `X-Correlation-Id` from ContextBar</span>
      </div>
      {err && <div className="muted">{err}</div>}
      {out && <pre className="code">{JSON.stringify(out, null, 2)}</pre>}
    </div>
  );
}

