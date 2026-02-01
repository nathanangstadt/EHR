import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

export function AdminTools() {
  const { state, dispatch } = useAppContext();
  const [templates, setTemplates] = useState<any[]>([]);
  const [templateId, setTemplateId] = useState<string>("knee-oa-mri");
  const [family, setFamily] = useState("Scenario");
  const [given, setGiven] = useState("Patient");
  const [birthDate, setBirthDate] = useState("1980-01-01");
  const [mrn, setMrn] = useState("");
  const [createPreAuthDraft, setCreatePreAuthDraft] = useState(true);

  const [resetOut, setResetOut] = useState<any>(null);
  const [scenarioOut, setScenarioOut] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let ok = true;
    async function load() {
      try {
        const res = await apiFetch("/internal/scenarios/templates");
        if (!ok) return;
        setTemplates(res.templates ?? []);
      } catch {
        // ignore; feature is dev-only
      }
    }
    load();
    return () => {
      ok = false;
    };
  }, []);

  async function reset() {
    if (!confirm("Reset ALL data and restore the initial seed dataset?")) return;
    setBusy(true);
    setErr(null);
    setResetOut(null);
    setScenarioOut(null);
    try {
      const res = await apiFetch("/internal/admin/reset", {
        method: "POST",
        correlationId: state.correlationId,
        body: JSON.stringify({ seed: true }),
      });
      setResetOut(res);
      dispatch({ type: "setPatient", patientId: undefined });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function createScenario() {
    setBusy(true);
    setErr(null);
    setScenarioOut(null);
    try {
      const res = await apiFetch("/internal/scenarios", {
        method: "POST",
        correlationId: state.correlationId,
        body: JSON.stringify({
          templateId,
          patient: { family, given, birthDate, mrn: mrn || undefined },
          createPreAuthDraft,
        }),
      });
      setScenarioOut(res);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div>
        <div className="muted" style={{ marginBottom: 8 }}>
          Dev-only utilities: reset seed data and generate realistic scenarios.
        </div>
        <button disabled={busy} onClick={() => reset()}>
          {busy ? "Working..." : "Reset Seed Data"}
        </button>
        {resetOut && <pre className="code" style={{ marginTop: 8 }}>{JSON.stringify(resetOut, null, 2)}</pre>}
      </div>

      <div>
        <div className="row" style={{ marginBottom: 8 }}>
          <span className="muted">Template</span>
          <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} style={{ width: 320 }}>
            {(templates.length ? templates : [{ id: "knee-oa-mri", title: "knee-oa-mri" }]).map((t: any) => (
              <option key={t.id} value={t.id}>
                {t.title ?? t.id}
              </option>
            ))}
          </select>
        </div>
        <div className="row" style={{ marginBottom: 8 }}>
          <span className="muted">Name</span>
          <input value={given} onChange={(e) => setGiven(e.target.value)} placeholder="Given" style={{ width: 160 }} />
          <input value={family} onChange={(e) => setFamily(e.target.value)} placeholder="Family" style={{ width: 160 }} />
        </div>
        <div className="row" style={{ marginBottom: 8 }}>
          <span className="muted">Birthdate</span>
          <input value={birthDate} onChange={(e) => setBirthDate(e.target.value)} style={{ width: 160 }} />
          <span className="muted">MRN</span>
          <input value={mrn} onChange={(e) => setMrn(e.target.value)} placeholder="(optional)" style={{ width: 200 }} />
        </div>
        <div className="row" style={{ marginBottom: 8 }}>
          <label className="row">
            <input type="checkbox" checked={createPreAuthDraft} onChange={(e) => setCreatePreAuthDraft(e.target.checked)} />
            <span className="muted">Create PreAuth draft</span>
          </label>
        </div>
        <div className="row">
          <button disabled={busy} onClick={() => createScenario()}>
            {busy ? "Working..." : "Create Scenario"}
          </button>
          {scenarioOut?.patientId && (
            <button
              onClick={() => {
                dispatch({ type: "setPatient", patientId: scenarioOut.patientId });
                if (scenarioOut.encounterId) dispatch({ type: "setEncounter", encounterId: scenarioOut.encounterId });
                if (scenarioOut.preAuthId) dispatch({ type: "setPreAuth", preAuthId: scenarioOut.preAuthId });
              }}
            >
              Load in Context
            </button>
          )}
        </div>
        {err && <div className="muted">{err}</div>}
        {scenarioOut && <pre className="code" style={{ marginTop: 8 }}>{JSON.stringify(scenarioOut, null, 2)}</pre>}
      </div>
    </div>
  );
}

