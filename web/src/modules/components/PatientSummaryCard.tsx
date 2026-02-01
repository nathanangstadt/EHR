import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

export function PatientSummaryCard({ context }: any) {
  const [p, setP] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    async function run() {
      if (!context.patientId) return;
      setErr(null);
      try {
        const res = await apiFetch(`/fhir/Patient/${context.patientId}`);
        if (ok) setP(res);
      } catch (e: any) {
        if (ok) setErr(e.message);
      }
    }
    run();
    return () => {
      ok = false;
    };
  }, [context.patientId]);

  if (!context.patientId) return <div className="muted">Select a patient.</div>;
  if (err) return <div className="muted">{err}</div>;
  if (!p) return <div className="muted">Loading...</div>;
  return (
    <div>
      <div>
        {p.name?.[0]?.family}, {p.name?.[0]?.given?.[0]}
      </div>
      <div className="muted">
        MRN: {p.identifier?.[0]?.value ?? "(none)"} · Birthdate: {p.birthDate ?? "(none)"}
      </div>
      <div className="muted">
        version {p.meta?.versionId} · lastUpdated {p.meta?.lastUpdated}
      </div>
    </div>
  );
}

