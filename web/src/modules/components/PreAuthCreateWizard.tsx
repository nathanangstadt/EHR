import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

type Step = "service" | "diagnosis" | "supporting" | "create";

export function PreAuthCreateWizard({ context, onOutput }: any) {
  const { state, dispatch } = useAppContext();
  const [step, setStep] = useState<Step>("service");
  const [conditions, setConditions] = useState<any[]>([]);
  const [serviceRequests, setServiceRequests] = useState<any[]>([]);
  const [observations, setObservations] = useState<any[]>([]);
  const [practitionerId, setPractitionerId] = useState<string>("");
  const [diagnosisId, setDiagnosisId] = useState<string>("");
  const [serviceRequestId, setServiceRequestId] = useState<string>("");
  const [supporting, setSupporting] = useState<Set<string>>(new Set());
  const [created, setCreated] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    setStep("service");
    setConditions([]);
    setServiceRequests([]);
    setObservations([]);
    setDiagnosisId("");
    setServiceRequestId("");
    setSupporting(new Set());
    setCreated(null);

    async function load() {
      if (!context.patientId) return;
      setErr(null);
      try {
        const pid = context.patientId;
        const [cond, sr, obs, prac] = await Promise.all([
          apiFetch(`/fhir/Condition?patient=${pid}&_count=50`),
          apiFetch(`/fhir/ServiceRequest?patient=${pid}&_count=50`),
          apiFetch(`/fhir/Observation?patient=${pid}&_count=50&_sort=-date`),
          apiFetch(`/fhir/Practitioner?_count=10`),
        ]);
        if (!ok) return;
        setConditions((cond.entry ?? []).map((e: any) => e.resource));
        setServiceRequests((sr.entry ?? []).map((e: any) => e.resource));
        setObservations((obs.entry ?? []).map((e: any) => e.resource));
        const first = (prac.entry ?? []).map((e: any) => e.resource)[0];
        if (first?.id) setPractitionerId(first.id);
      } catch (e: any) {
        if (ok) setErr(e.message);
      }
    }
    load();
    return () => {
      ok = false;
    };
  }, [context.patientId]);

  async function create() {
    setErr(null);
    try {
      const res = await apiFetch("/preauth", {
        method: "POST",
        correlationId: state.correlationId,
        body: JSON.stringify({
          patientId: context.patientId,
          encounterId: context.encounterId,
          practitionerId,
          diagnosisConditionId: diagnosisId,
          serviceRequestId,
          priority: "routine",
          payer: "Acme Payer",
          supportingObservationIds: Array.from(supporting),
        }),
      });
      setCreated(res);
      dispatch({ type: "setPreAuth", preAuthId: res.id });
      onOutput?.({ createdPreAuthId: res.id });
      setStep("create");
    } catch (e: any) {
      setErr(e.message);
    }
  }

  if (!context.patientId) return <div className="muted">Select an active patient.</div>;

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">Step</span>
        <select value={step} onChange={(e) => setStep(e.target.value as Step)}>
          <option value="service">Pick ServiceRequest</option>
          <option value="diagnosis">Pick Diagnosis</option>
          <option value="supporting">Pick Supporting Observations</option>
          <option value="create">Create Draft</option>
        </select>
      </div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">PractitionerId</span>
        <input value={practitionerId} onChange={(e) => setPractitionerId(e.target.value)} style={{ width: 320 }} />
      </div>
      {err && <div className="muted">{err}</div>}
      {step === "service" && (
        <div style={{ display: "grid", gap: 8 }}>
          {serviceRequests.map((sr) => (
            <button
              key={sr.id}
              onClick={() => {
                setServiceRequestId(sr.id);
                const rr = (sr.reasonReference ?? [])[0]?.reference as string | undefined;
                if (rr && typeof rr === "string" && rr.startsWith("Condition/")) {
                  const cid = rr.split("/")[1];
                  if (cid) setDiagnosisId(cid);
                }
                const enc = sr.encounter?.reference as string | undefined;
                if (enc && typeof enc === "string" && enc.startsWith("Encounter/")) {
                  const eid = enc.split("/")[1];
                  if (eid) dispatch({ type: "setEncounter", encounterId: eid });
                }
                setStep("diagnosis");
              }}
              style={{ textAlign: "left", padding: 10, borderRadius: 10 }}
            >
              <div>
                {sr.code?.coding?.[0]?.display ?? sr.code?.coding?.[0]?.code}{" "}
                <span className="muted">({sr.status})</span>
              </div>
              {sr.reasonReference?.length ? (
                <div className="muted">
                  reason: {(sr.reasonReference ?? [])
                    .map((r: any) => r.reference)
                    .filter(Boolean)
                    .join(", ")}
                </div>
              ) : null}
              <div className="muted">{sr.id}</div>
            </button>
          ))}
        </div>
      )}
      {step === "diagnosis" && (
        <div>
          <div className="muted" style={{ marginBottom: 8 }}>
            Pick the primary diagnosis/indication for this request.
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {conditions.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setDiagnosisId(c.id);
                  setStep("supporting");
                }}
                style={{ textAlign: "left", padding: 10, borderRadius: 10 }}
              >
                <div>
                  {c.code?.coding?.[0]?.display ?? c.code?.coding?.[0]?.code}{" "}
                  <span className="muted">({c.clinicalStatus?.coding?.[0]?.code})</span>
                </div>
                <div className="muted">{c.id}</div>
              </button>
            ))}
          </div>
        </div>
      )}
      {step === "supporting" && (
        <div>
          <div className="muted" style={{ marginBottom: 8 }}>
            Select observations to include in the pre-auth package snapshot.
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {observations
              .filter((o) => {
                // If an encounter is set (from context bar or ServiceRequest.encounter), default to that slice.
                if (!context.encounterId) return true;
                const encRef = o.encounter?.reference as string | undefined;
                return encRef === `Encounter/${context.encounterId}`;
              })
              .map((o) => {
              const checked = supporting.has(o.id);
              return (
                <label key={o.id} className="row" style={{ justifyContent: "space-between" }}>
                  <span>
                    {o.code?.coding?.[0]?.display ?? o.code?.coding?.[0]?.code} · {o.effectiveDateTime}
                  </span>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      const next = new Set(supporting);
                      if (e.target.checked) next.add(o.id);
                      else next.delete(o.id);
                      setSupporting(next);
                    }}
                  />
                </label>
              );
            })}
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button onClick={() => setStep("create")}>Continue</button>
          </div>
        </div>
      )}
      {step === "create" && (
        <div>
          <div className="row" style={{ marginBottom: 8 }}>
            <span className="muted">Diagnosis</span>
            <span>{diagnosisId || "(select)"}</span>
          </div>
          <div className="row" style={{ marginBottom: 8 }}>
            <span className="muted">ServiceRequest</span>
            <span>{serviceRequestId || "(select)"}</span>
          </div>
          <div className="row">
            <button disabled={!diagnosisId || !serviceRequestId || !practitionerId} onClick={() => create()}>
              Create Draft PreAuth
            </button>
          </div>
          {created && <pre className="code">{JSON.stringify(created, null, 2)}</pre>}
        </div>
      )}
    </div>
  );
}
