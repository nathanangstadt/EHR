import React, { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api/client";
import { emit } from "../../ui/eventBus";

type EventRef = { resourceType: string; id: string };

export function TimelineList({ context, onOutput }: any) {
  const [items, setItems] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let ok = true;
    async function run() {
      if (!context.patientId) return;
      setLoading(true);
      setErr(null);
      try {
        const pid = context.patientId;
        const [enc, doc, obs, cond, sr] = await Promise.all([
          apiFetch(`/fhir/Encounter?patient=${pid}&_count=50`),
          apiFetch(`/fhir/DocumentReference?patient=${pid}&_count=50`),
          apiFetch(`/fhir/Observation?patient=${pid}&_sort=-date&_count=50`),
          apiFetch(`/fhir/Condition?patient=${pid}&_count=50`),
          apiFetch(`/fhir/ServiceRequest?patient=${pid}&_count=50`),
        ]);
        const merged: any[] = [];
        for (const e of enc.entry ?? []) merged.push({ resourceType: "Encounter", resource: e.resource });
        for (const e of doc.entry ?? []) merged.push({ resourceType: "DocumentReference", resource: e.resource });
        for (const e of obs.entry ?? []) merged.push({ resourceType: "Observation", resource: e.resource });
        for (const e of cond.entry ?? []) merged.push({ resourceType: "Condition", resource: e.resource });
        for (const e of sr.entry ?? []) merged.push({ resourceType: "ServiceRequest", resource: e.resource });
        if (ok) setItems(merged);
      } catch (e: any) {
        if (ok) setErr(e.message);
      } finally {
        if (ok) setLoading(false);
      }
    }
    run();
    return () => {
      ok = false;
    };
  }, [context.patientId, context.encounterId, refreshTick]);

  const sorted = useMemo(() => {
    function getTime(it: any): number {
      const r = it.resource;
      const dt =
        r.period?.start ??
        r.period?.end ??
        r.effectiveDateTime ??
        r.authoredOn ??
        r.onsetDate ??
        r.onsetDateTime ??
        r.meta?.lastUpdated;
      return dt ? Date.parse(dt) : 0;
    }
    return [...items].sort((a, b) => getTime(b) - getTime(a));
  }, [items]);

  if (!context.patientId) return <div className="muted">Select a patient.</div>;
  if (err) return <div className="muted">{err}</div>;

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="muted">{loading ? "Loading..." : `${sorted.length} items`}</div>
        <button onClick={() => setRefreshTick((n) => n + 1)} disabled={loading}>
          Refresh
        </button>
      </div>
      {sorted.map((it) => {
        const r = it.resource;
        const label =
          it.resourceType === "Encounter"
            ? `Encounter (${r.status ?? "unknown"})`
            : it.resourceType === "DocumentReference"
              ? `Document: ${r.description ?? r.type?.coding?.[0]?.display ?? r.type?.coding?.[0]?.code ?? "DocumentReference"}`
            : it.resourceType === "Observation"
              ? `${r.code?.coding?.[0]?.display ?? r.code?.coding?.[0]?.code} = ${
                  r.valueQuantity?.value ?? r.valueCodeableConcept?.coding?.[0]?.code ?? ""
                }`
              : it.resourceType === "Condition"
                ? `${r.code?.coding?.[0]?.display ?? r.code?.coding?.[0]?.code}`
                : `${r.code?.coding?.[0]?.display ?? r.code?.coding?.[0]?.code}`;
        const when =
          r.period?.start ??
          r.period?.end ??
          r.date ??
          r.effectiveDateTime ??
          r.authoredOn ??
          r.onsetDate ??
          r.meta?.lastUpdated ??
          "(no date)";
        return (
          <button
            key={`${it.resourceType}/${r.id}`}
            onClick={() => {
              const ref: EventRef = { resourceType: it.resourceType, id: r.id };
              emit({ type: "selectEventRef", payload: ref });
              onOutput?.({ selectedEventRef: ref });
            }}
            style={{ textAlign: "left", padding: 10, borderRadius: 10 }}
          >
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>{it.resourceType}</strong>
              <span className="muted">{when}</span>
            </div>
            <div>{label}</div>
            <div className="muted">{r.id}</div>
          </button>
        );
      })}
    </div>
  );
}
