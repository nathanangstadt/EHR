import React, { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

function toBase64Utf8(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

function todayIsoDate(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function RequestedDocumentUploader({ context, onOutput }: any) {
  const { state } = useAppContext();
  const [preauth, setPreauth] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("Knee X-ray report");
  const [date, setDate] = useState(todayIsoDate());
  const [content, setContent] = useState("Knee X-ray report (POC text)\nFindings: ...\nImpression: ...\n");
  const [created, setCreated] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let ok = true;
    async function load() {
      if (!context.preAuthId) return;
      setErr(null);
      try {
        const res = await apiFetch(`/preauth/${context.preAuthId}`);
        if (ok) setPreauth(res);
      } catch (e: any) {
        if (ok) setErr(e.message);
      }
    }
    load();
    return () => {
      ok = false;
    };
  }, [context.preAuthId]);

  const requestNeeded = useMemo(() => {
    const need = preauth?.latestDecision?.requestedAdditionalInfo ?? [];
    return (need as any[]).some((n) => {
      const code = (n.code ?? "").toString().toLowerCase();
      const display = (n.display ?? "").toString().toLowerCase();
      const type = (n.type ?? "").toString().toLowerCase();
      return type === "document" || code === "knee-xray-report" || display.includes("x-ray") || display.includes("xray");
    });
  }, [preauth]);

  async function createAndAttach() {
    if (!preauth?.patientId) {
      setErr("Missing patientId (load a preauth first).");
      return;
    }
    setBusy(true);
    setErr(null);
    setCreated(null);
    try {
      const binary = await apiFetch("/fhir/Binary", {
        method: "POST",
        correlationId: state.correlationId,
        body: JSON.stringify({
          resourceType: "Binary",
          contentType: "text/plain",
          data: toBase64Utf8(content),
        }),
      });

      const doc = await apiFetch("/fhir/DocumentReference", {
        method: "POST",
        correlationId: state.correlationId,
        body: JSON.stringify({
          resourceType: "DocumentReference",
          status: "current",
          subject: { reference: `Patient/${preauth.patientId}` },
          ...(preauth.encounterId
            ? { context: { encounter: [{ reference: `Encounter/${preauth.encounterId}` }] } }
            : {}),
          type: {
            coding: [
              {
                system: "urn:sample-app:doc-type",
                code: "knee-xray-report",
                display: "Knee X-ray report",
              },
            ],
          },
          date: `${date}T12:00:00Z`,
          description: title,
          content: [
            {
              attachment: {
                url: `Binary/${binary.id}`,
                contentType: "text/plain",
              },
            },
          ],
        }),
      });

      const link = await apiFetch(`/preauth/${context.preAuthId}/documents`, {
        method: "POST",
        correlationId: state.correlationId,
        body: JSON.stringify({ documentId: doc.id, role: "supporting" }),
      });

      setCreated({ binary, documentReference: doc, link });
      const refreshed = await apiFetch(`/preauth/${context.preAuthId}`);
      setPreauth(refreshed);
      onOutput?.({ attachedDocumentId: doc.id, linkId: link.id });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!context.preAuthId) return <div className="muted">Select a PreAuth.</div>;
  if (err) return <div className="muted">{err}</div>;
  if (!preauth) return <div className="muted">Loading...</div>;

  return (
    <div>
      <div className="muted" style={{ marginBottom: 8 }}>
        {"Payer requested a document. Create a DocumentReference + Binary and attach it to this PreAuth."}
      </div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">Title</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} style={{ width: 320 }} />
      </div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted">Date</span>
        <input value={date} onChange={(e) => setDate(e.target.value)} style={{ width: 160 }} />
        <span className="muted">(must be within last 30 days)</span>
      </div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={8}
        style={{ width: "100%", fontFamily: "ui-monospace, SFMono-Regular" }}
      />
      <div className="row" style={{ marginTop: 8 }}>
        <button disabled={busy} onClick={() => createAndAttach()}>
          {busy ? "Working..." : "Create + Attach X-ray Report"}
        </button>
        <span className="muted">Then click Submit PreAuth again.</span>
      </div>
      {created && <pre className="code">{JSON.stringify(created, null, 2)}</pre>}
    </div>
  );
}
