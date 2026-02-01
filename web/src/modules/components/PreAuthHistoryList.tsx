import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

export function PreAuthHistoryList({ context, onOutput }: any) {
  const [status, setStatus] = useState<string>("");
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    if (!context.patientId) return;
    setErr(null);
    const qp = new URLSearchParams();
    qp.set("patient", context.patientId);
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
  }, [context.patientId, status]);

  if (!context.patientId) return <div className="muted">Select an active patient to view pre-auth history.</div>;

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">Status</span>
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 180 }}>
          <option value="">(any)</option>
          {["draft", "submitted", "resubmitted", "in-review", "pending-info", "approved", "denied", "canceled"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button onClick={() => refresh()}>Refresh</button>
        <span className="muted">{rows.length} items</span>
        <button onClick={() => setCollapsed(!collapsed)}>{collapsed ? "Show" : "Collapse"}</button>
      </div>
      {err && <div className="muted">{err}</div>}
      {!collapsed && !rows.length && <div className="muted">No pre-auth requests found for this patient.</div>}
      {!collapsed && (
        <div style={{ maxHeight: 280, overflowY: "auto", paddingRight: 4 }}>
          <div style={{ display: "grid", gap: 8 }}>
            {rows.map((p) => (
              <div key={p.id} className="card" style={{ marginTop: 0 }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong>{p.status}</strong>
                  <span className="muted">{p.updatedTime}</span>
                </div>
                <div className="muted">payer: {p.payer ?? "(none)"}</div>
                {p.latestDecision ? (
                  <div className="row">
                    <span className="muted">decision:</span>
                    <span>{p.latestDecision.outcome}</span>
                  </div>
                ) : (
                  <div className="muted">decision: (none yet)</div>
                )}
                <div className="muted">preAuthId: {p.id}</div>
                <div className="row" style={{ marginTop: 6 }}>
                  <button onClick={() => onOutput?.({ selectedPreAuthId: p.id })}>Load</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
