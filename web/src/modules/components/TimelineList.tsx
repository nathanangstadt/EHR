import React, { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api/client";
import { emit } from "../../ui/eventBus";

type EventRef = { resourceType: string; id: string };
type Scope = "patient" | "encounter";

function refId(reference?: string): string | undefined {
  if (!reference) return undefined;
  const parts = reference.split("/");
  return parts[parts.length - 1] || undefined;
}

function encounterIdForResource(resourceType: string, r: any): string | undefined {
  if (resourceType === "Encounter") return r?.id;
  const direct = refId(r?.encounter?.reference);
  if (direct) return direct;
  // FHIR DocumentReference: context.encounter is typically an array of references.
  const docEnc = r?.context?.encounter;
  if (Array.isArray(docEnc) && docEnc.length) return refId(docEnc[0]?.reference);
  return undefined;
}

export function TimelineList({ context, onOutput }: any) {
  const [items, setItems] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [loading, setLoading] = useState(false);
  const [scope, setScope] = useState<Scope>(context.encounterId ? "encounter" : "patient");

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

  useEffect(() => {
    if (!context.encounterId && scope === "encounter") setScope("patient");
  }, [context.encounterId, scope]);

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
    const all = [...items].sort((a, b) => getTime(b) - getTime(a));
    if (scope !== "encounter" || !context.encounterId) return all;

    const encId = context.encounterId;
    return all.filter((it) => {
      const id = encounterIdForResource(it.resourceType, it.resource);
      return id === encId;
    });
  }, [items, scope, context.encounterId]);

  if (!context.patientId) return <div className="muted">Select a patient.</div>;
  if (err) return <div className="muted">{err}</div>;

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row">
          <span className="muted">{loading ? "Loading..." : `${sorted.length} items`}</span>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as Scope)}
            disabled={!context.encounterId}
            title={context.encounterId ? "Scope timeline to patient or active encounter" : "Set an active encounter to enable encounter scoping"}
          >
            <option value="patient">All encounters</option>
            <option value="encounter">Active encounter only</option>
          </select>
        </div>
        <div className="row">
          {context.encounterId && scope === "encounter" && (
            <button onClick={() => emit({ type: "setEncounterId", payload: { encounterId: undefined } })} disabled={loading}>
              Clear Encounter
            </button>
          )}
          <button onClick={() => setRefreshTick((n) => n + 1)} disabled={loading}>
            Refresh
          </button>
        </div>
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
              if (it.resourceType === "Encounter") {
                emit({ type: "setEncounterId", payload: { encounterId: r.id } });
              }
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
