import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";

export function JobList({ onOutput }: any) {
  const { dispatch } = useAppContext();
  const [jobs, setJobs] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    setErr(null);
    try {
      const res = await apiFetch("/jobs");
      setJobs(res.jobs ?? []);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div>
      <div className="row">
        <button onClick={() => refresh()}>Refresh</button>
      </div>
      {err && <div className="muted">{err}</div>}
      <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
        {jobs.map((j) => (
          <button
            key={j.id}
            onClick={() => {
              dispatch({ type: "setJob", jobId: j.id });
              onOutput?.({ selectedJobId: j.id });
            }}
            style={{ textAlign: "left", padding: 10, borderRadius: 10 }}
          >
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>{j.type}</strong>
              <span className="muted">{j.status}</span>
            </div>
            <div className="muted">
              {j.id} · {j.progress}%
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

