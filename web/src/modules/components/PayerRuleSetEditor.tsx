import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

export function PayerRuleSetEditor() {
  const { state } = useAppContext();
  const [payer, setPayer] = useState("Acme Payer");
  const [jsonText, setJsonText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    setStatus(null);
    try {
      const res = await apiFetch(`/payer/rules?payer=${encodeURIComponent(payer)}`);
      setJsonText(JSON.stringify(res.rules, null, 2));
      setStatus(`Loaded active ruleset ${res.id}`);
    } catch (e: any) {
      setErr(e.message);
      setJsonText(JSON.stringify({ schemaVersion: "1", policies: [] }, null, 2));
    }
  }

  async function saveActive() {
    setErr(null);
    setStatus(null);
    try {
      const rules = JSON.parse(jsonText);
      const res = await apiFetch(`/payer/rules?payer=${encodeURIComponent(payer)}`, {
        method: "PUT",
        correlationId: state.correlationId,
        body: JSON.stringify({ rules }),
      });
      setStatus(`Saved active ruleset ${res.id}`);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">Payer</span>
        <input value={payer} onChange={(e) => setPayer(e.target.value)} style={{ width: 240 }} />
        <button onClick={() => load()}>Load</button>
        <button onClick={() => saveActive()}>Save as Active</button>
      </div>
      {status && <div className="muted">{status}</div>}
      {err && <div className="muted">{err}</div>}
      <textarea
        value={jsonText}
        onChange={(e) => setJsonText(e.target.value)}
        rows={18}
        style={{ width: "100%", fontFamily: "ui-monospace, SFMono-Regular" }}
      />
    </div>
  );
}

