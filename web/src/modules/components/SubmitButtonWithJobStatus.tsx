import React, { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";
import { useAppContext } from "../../ui/context";
import { emit } from "../../ui/eventBus";

export function SubmitButtonWithJobStatus({ context, onOutput }: any) {
  const { state, dispatch } = useAppContext();
  const [job, setJob] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [preauthStatus, setPreauthStatus] = useState<string | null>(null);
  const [hasDecision, setHasDecision] = useState<boolean>(false);
  const [mode, setMode] = useState<"submit" | "resubmit">("submit");

  async function submit() {
    setErr(null);
    try {
      const cur = await apiFetch(`/preauth/${context.preAuthId}`);
      setPreauthStatus(cur.status);
      setHasDecision(!!cur.latestDecision);
      const nextMode = cur.status === "pending-info" ? "resubmit" : "submit";
      setMode(nextMode);
      const endpoint = nextMode === "resubmit" ? "resubmit" : "submit";
      const res = await apiFetch(`/preauth/${context.preAuthId}/${endpoint}`, {
        method: "POST",
        correlationId: state.correlationId,
      });
      dispatch({ type: "setJob", jobId: res.jobId });
      emit({ type: "setJobId", payload: { jobId: res.jobId } });
      onOutput?.({ jobId: res.jobId });
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function enqueueReview() {
    setErr(null);
    try {
      const res = await apiFetch(`/preauth/${context.preAuthId}/enqueue-review`, {
        method: "POST",
        correlationId: state.correlationId,
      });
      dispatch({ type: "setJob", jobId: res.jobId });
      emit({ type: "setJobId", payload: { jobId: res.jobId } });
      onOutput?.({ jobId: res.jobId });
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    let stop = false;
    async function refreshPreauth() {
      if (!context.preAuthId) return;
      try {
        const cur = await apiFetch(`/preauth/${context.preAuthId}`);
        setPreauthStatus(cur.status);
        setHasDecision(!!cur.latestDecision);
        setMode(cur.status === "pending-info" ? "resubmit" : "submit");
      } catch (e: any) {
        setErr(e.message);
      }
    }
    async function poll(jobId: string) {
      while (!stop) {
        try {
          const r = await apiFetch(`/jobs/${jobId}`);
          setJob(r);
          if (r.status === "succeeded" || r.status === "failed") {
            await refreshPreauth();
            return;
          }
        } catch (e: any) {
          setErr(e.message);
          return;
        }
        await new Promise((r) => setTimeout(r, 750));
      }
    }
    refreshPreauth();
    if (context.jobId) poll(context.jobId);
    return () => {
      stop = true;
    };
  }, [context.preAuthId, context.jobId, context.refresh]);

  const canSubmit = preauthStatus === "draft" || preauthStatus === "pending-info";
  const canEnqueueReview =
    !!preauthStatus && !hasDecision && ["submitted", "resubmitted", "in-review"].includes(preauthStatus);

  return (
    <div>
      <div className="row">
        <button onClick={() => submit()} disabled={!canSubmit}>
          {mode === "resubmit" ? "Resubmit PreAuth" : "Submit PreAuth"}
        </button>
        {!canSubmit && canEnqueueReview && (
          <button onClick={() => enqueueReview()}>Retry Payer Job</button>
        )}
        {preauthStatus && <span className="muted">Current status: {preauthStatus}</span>}
        <span className="muted">Uses correlation id from ContextBar.</span>
      </div>
      {err && <div className="muted">{err}</div>}
      {job && (
        <div style={{ marginTop: 8 }}>
          <div className="row">
            <strong>Status:</strong> <span>{job.status}</span>
            <strong>Progress:</strong> <span>{job.progress}%</span>
          </div>
          <div className="muted">{job.message}</div>
        </div>
      )}
    </div>
  );
}
