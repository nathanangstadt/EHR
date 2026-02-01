import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

export function JobDetailPanel({ context }: any) {
  const [job, setJob] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    async function run() {
      if (!context.jobId) return;
      setErr(null);
      try {
        const r = await apiFetch(`/jobs/${context.jobId}`);
        if (ok) setJob(r);
      } catch (e: any) {
        if (ok) setErr(e.message);
      }
    }
    run();
    const t = setInterval(run, 1000);
    return () => {
      ok = false;
      clearInterval(t);
    };
  }, [context.jobId]);

  if (!context.jobId) return <div className="muted">Select a job.</div>;
  if (err) return <div className="muted">{err}</div>;
  if (!job) return <div className="muted">Loading...</div>;
  return <pre className="code">{JSON.stringify(job, null, 2)}</pre>;
}

