import React, { useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

export function MappingTraceViewer() {
  const { state } = useAppContext();
  const [correlationId, setCorrelationId] = useState(state.correlationId);
  const [resourceType, setResourceType] = useState("Patient");
  const [resourceId, setResourceId] = useState("");
  const [out, setOut] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    setErr(null);
    try {
      const qp = new URLSearchParams();
      if (correlationId) qp.set("correlationId", correlationId);
      if (resourceType && resourceId) {
        qp.set("resourceType", resourceType);
        qp.set("resourceId", resourceId);
      }
      const res = await apiFetch(`/internal/mapping-trace?${qp.toString()}`);
      setOut(res);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <div className="row">
        <span className="muted">CorrelationId</span>
        <input value={correlationId} onChange={(e) => setCorrelationId(e.target.value)} style={{ width: 320 }} />
        <button onClick={() => run()}>Trace</button>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <span className="muted">or Resource</span>
        <select value={resourceType} onChange={(e) => setResourceType(e.target.value)} style={{ width: 160 }}>
          {["Patient", "Observation", "Condition", "ServiceRequest", "PreAuth"].map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <input
          value={resourceId}
          onChange={(e) => setResourceId(e.target.value)}
          placeholder="UUID"
          style={{ width: 320 }}
        />
        <button onClick={() => run()}>Trace</button>
      </div>
      {err && <div className="muted">{err}</div>}
      {out && <pre className="code">{JSON.stringify(out, null, 2)}</pre>}
    </div>
  );
}

