import React, { useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

export function PatientSearchPanel({ onOutput }: any) {
  const { dispatch } = useAppContext();
  const [q, setQ] = useState("");
  const [birth, setBirth] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    setErr(null);
    const params = new URLSearchParams();
    if (q.includes("MRN-") || q.includes("mrn")) params.set("identifier", `urn:mrn|${q}`);
    else if (q) params.set("name", q);
    if (birth) params.set("birthdate", birth);
    const res = await apiFetch(`/fhir/Patient?${params.toString()}`);
    setRows((res.entry ?? []).map((e: any) => e.resource));
  }

  return (
    <div>
      <div className="row">
        <input
          placeholder="name or MRN"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ width: 240 }}
        />
        <input
          placeholder="birthdate YYYY-MM-DD"
          value={birth}
          onChange={(e) => setBirth(e.target.value)}
          style={{ width: 180 }}
        />
        <button onClick={() => run()}>Search</button>
      </div>
      {err && <div className="muted">{err}</div>}
      <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
        {rows.map((p) => (
          <div key={p.id} className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <div>
                {p.name?.[0]?.family}, {p.name?.[0]?.given?.[0]}
              </div>
              <div className="muted">
                {p.id} · {p.identifier?.[0]?.value}
              </div>
            </div>
            <button
              onClick={() => {
                dispatch({ type: "setPatient", patientId: p.id });
                onOutput?.({ selectedPatientId: p.id });
              }}
            >
              Select
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

