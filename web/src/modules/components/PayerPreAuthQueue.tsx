import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

export function PayerPreAuthQueue() {
  const { dispatch } = useAppContext();
  const [payer, setPayer] = useState("Acme Payer");
  const [status, setStatus] = useState<string>("pending-info");
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    setErr(null);
    const qp = new URLSearchParams();
    if (payer) qp.set("payer", payer);
    if (status) qp.set("status", status);
    try {
      const res = await apiFetch(`/preauth?${qp.toString()}`);
      setRows(res.preauth ?? []);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">Payer</span>
        <input value={payer} onChange={(e) => setPayer(e.target.value)} style={{ width: 220 }} />
        <span className="muted">Status</span>
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 160 }}>
          <option value="">(any)</option>
          {["draft", "submitted", "resubmitted", "in-review", "pending-info", "approved", "denied", "canceled"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button onClick={() => refresh()}>Refresh</button>
      </div>
      {err && <div className="muted">{err}</div>}
      <div style={{ display: "grid", gap: 8 }}>
        {rows.map((p) => (
          <div key={p.id} className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>{p.status}</strong>
              <span className="muted">{p.updatedTime}</span>
            </div>
            <div className="muted">preAuthId: {p.id}</div>
            <div className="muted">patientId: {p.patientId}</div>
            {p.latestDecision && (
              <div className="row">
                <span className="muted">decision:</span>
                <span>{p.latestDecision.outcome}</span>
              </div>
            )}
            <div className="row" style={{ marginTop: 6 }}>
              <button
                onClick={() => {
                  dispatch({ type: "setPatient", patientId: p.patientId });
                  dispatch({ type: "setPreAuth", preAuthId: p.id });
                }}
              >
                Load in App Context
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
