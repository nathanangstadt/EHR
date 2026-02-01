import React, { useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

export function FHIRRequestComposer() {
  const { state } = useAppContext();
  const [method, setMethod] = useState<"GET" | "POST" | "PUT">("GET");
  const [path, setPath] = useState("/fhir/Patient?_count=5");
  const [body, setBody] = useState('{\n  "resourceType": "Patient"\n}\n');
  const [out, setOut] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function send() {
    setErr(null);
    try {
      const res = await apiFetch(path, {
        method,
        correlationId: state.correlationId,
        body: method === "GET" ? undefined : body,
      });
      setOut(res);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <div className="row">
        <select value={method} onChange={(e) => setMethod(e.target.value as any)}>
          <option>GET</option>
          <option>POST</option>
          <option>PUT</option>
        </select>
        <input value={path} onChange={(e) => setPath(e.target.value)} style={{ width: 420 }} />
        <button onClick={() => send()}>Send</button>
      </div>
      {method !== "GET" && (
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={10}
          style={{ width: "100%", marginTop: 8, fontFamily: "ui-monospace, SFMono-Regular" }}
        />
      )}
      {err && <div className="muted">{err}</div>}
      {out && <pre className="code">{JSON.stringify(out, null, 2)}</pre>}
    </div>
  );
}

