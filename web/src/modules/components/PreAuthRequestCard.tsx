import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

export function PreAuthRequestCard({ context }: any) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    async function run() {
      if (!context.preAuthId) return;
      setErr(null);
      try {
        const res = await apiFetch(`/preauth/${context.preAuthId}`);
        if (ok) setData(res);
      } catch (e: any) {
        if (ok) setErr(e.message);
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
          if (job.status === "succeeded" || job.status === "failed") {
            const res = await apiFetch(`/preauth/${context.preAuthId}`);
            setData(res);
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
  }, [context.preAuthId, context.jobId]);

  if (!context.preAuthId) return <div className="muted">Create or select a PreAuth.</div>;
  if (err) return <div className="muted">{err}</div>;
  if (!data) return <div className="muted">Loading...</div>;
  return <pre className="code">{JSON.stringify(data, null, 2)}</pre>;
}
