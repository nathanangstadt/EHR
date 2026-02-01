import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

type EventRef = { resourceType: string; id: string } | null;
type Tab = "fhir" | "som" | "trace" | "versions";

export function ClinicalEventDetailDrawer({ inputs }: any) {
  const selected: EventRef = inputs?.selectedEventRef ?? null;
  const [tab, setTab] = useState<Tab>("fhir");
  const [fhir, setFhir] = useState<any>(null);
  const [som, setSom] = useState<any>(null);
  const [trace, setTrace] = useState<any>(null);
  const [versions, setVersions] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setTab("fhir");
    setFhir(null);
    setSom(null);
    setTrace(null);
    setVersions(null);
    setErr(null);
  }, [selected?.resourceType, selected?.id]);

  useEffect(() => {
    let ok = true;
    async function run() {
      if (!selected) return;
      setErr(null);
      try {
        if (tab === "fhir") {
          const r = await apiFetch(`/fhir/${selected.resourceType}/${selected.id}`);
          if (ok) setFhir(r);
        }
        if (tab === "som") {
          const r = await apiFetch(`/internal/som/${selected.resourceType}/${selected.id}`);
          if (ok) setSom(r);
        }
        if (tab === "trace") {
          const r = await apiFetch(
            `/internal/mapping-trace?resourceType=${encodeURIComponent(selected.resourceType)}&resourceId=${encodeURIComponent(
              selected.id,
            )}`,
          );
          if (ok) setTrace(r);
        }
        if (tab === "versions" && selected.resourceType === "Observation") {
          const r = await apiFetch(`/internal/observation/${selected.id}/versions`);
          if (ok) setVersions(r);
        }
      } catch (e: any) {
        if (ok) setErr(e.message);
      }
    }
    run();
    return () => {
      ok = false;
    };
  }, [tab, selected?.resourceType, selected?.id]);

  if (!selected) return <div className="muted">Select an event in the timeline.</div>;

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <strong>
          {selected.resourceType}/{selected.id}
        </strong>
      </div>
      <div className="row" style={{ marginBottom: 8 }}>
        {(["fhir", "som", "trace"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}>
            {t.toUpperCase()}
          </button>
        ))}
        {selected.resourceType === "Observation" && (
          <button onClick={() => setTab("versions")}>VERSIONS</button>
        )}
      </div>
      {err && <div className="muted">{err}</div>}
      {tab === "fhir" && fhir && <pre className="code">{JSON.stringify(fhir, null, 2)}</pre>}
      {tab === "som" && som && <pre className="code">{JSON.stringify(som, null, 2)}</pre>}
      {tab === "trace" && trace && <pre className="code">{JSON.stringify(trace, null, 2)}</pre>}
      {tab === "versions" && versions && <pre className="code">{JSON.stringify(versions, null, 2)}</pre>}
      {!err && tab === "versions" && selected.resourceType !== "Observation" && (
        <div className="muted">Version history is implemented only for Observation.</div>
      )}
    </div>
  );
}

