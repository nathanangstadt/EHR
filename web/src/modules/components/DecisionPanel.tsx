import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

export function DecisionPanel({ context }: any) {
  const [dec, setDec] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    async function run() {
      if (!context.preAuthId) return;
      setErr(null);
      try {
        const res = await apiFetch(`/preauth/${context.preAuthId}/latest-decision`);
        if (ok) setDec(res);
      } catch (e: any) {
        if (!ok) return;
        if (String(e.message || "").startsWith("404 ")) {
          setDec(null);
          setErr(null);
          return;
        }
        setErr(e.message);
      }
    }
    run();
    return () => {
      ok = false;
    };
  }, [context.preAuthId, context.refresh]);

  useEffect(() => {
    let stop = false;
    async function poll() {
      if (!context.preAuthId || !context.jobId) return;
      while (!stop) {
        try {
          const job = await apiFetch(`/jobs/${context.jobId}`);
          setJobStatus(job.status);
          if (job.status === "succeeded" || job.status === "failed") {
            // Refresh decision after completion.
            try {
              const res = await apiFetch(`/preauth/${context.preAuthId}/latest-decision`);
              setErr(null);
              setDec(res);
            } catch (e: any) {
              if (String(e.message || "").startsWith("404 ")) {
                setDec(null);
                setErr(null);
                return;
              }
            }
            return;
          }
        } catch (e: any) {
          setErr(e.message);
          return;
        }
        await new Promise((r) => setTimeout(r, 750));
      }
    }
    poll();
    return () => {
      stop = true;
    };
  }, [context.preAuthId, context.jobId, context.refresh]);

  if (!context.preAuthId) return <div className="muted">Select a PreAuth.</div>;
  if (err) return <div className="muted">{err}</div>;
  if (!dec)
    return (
      <div className="muted">
        No decision yet{jobStatus ? ` (job: ${jobStatus})` : ""}. Submit the request and wait for completion.
      </div>
    );
  return <pre className="code">{JSON.stringify(dec, null, 2)}</pre>;
}
