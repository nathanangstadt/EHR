import React, { useEffect, useMemo, useState } from "react";
import { ModuleHost } from "../../modules/ModuleHost";
import { useAppContext } from "../context";
import { apiFetch } from "../../api/client";

function RequestedDocSection({
  preAuthId,
  correlationId,
  jobId,
  onAttached,
}: {
  preAuthId?: string;
  correlationId: string;
  jobId?: string;
  onAttached?: (info: any) => void;
}) {
  const [preauth, setPreauth] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    async function load() {
      if (!preAuthId) return;
      setErr(null);
      try {
        const res = await apiFetch(`/preauth/${preAuthId}`);
        if (ok) setPreauth(res);
      } catch (e: any) {
        if (ok) setErr(e.message);
      }
    }
    load();
    return () => {
      ok = false;
    };
  }, [preAuthId]);

  useEffect(() => {
    let stop = false;
    async function poll() {
      if (!preAuthId || !jobId) return;
      while (!stop) {
        try {
          const job = await apiFetch(`/jobs/${jobId}`);
          if (job.status === "succeeded" || job.status === "failed") {
            const res = await apiFetch(`/preauth/${preAuthId}`);
            setPreauth(res);
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
  }, [preAuthId, jobId]);

  const needsDocument = useMemo(() => {
    const need = preauth?.latestDecision?.requestedAdditionalInfo ?? [];
    return (need as any[]).some((n) => {
      const type = (n.type ?? "").toString().toLowerCase();
      const code = (n.code ?? "").toString().toLowerCase();
      return type === "document" || code.includes("xray") || code.includes("x-ray");
    });
  }, [preauth]);

  if (!preAuthId) return null;
  if (err) return null;
  if (!preauth) return null;
  if (!needsDocument) return null;

  return (
    <ModuleHost
      moduleId="RequestedDocumentUploader"
      context={{ preAuthId, correlationId }}
      onOutput={(o) => onAttached?.(o)}
    />
  );
}

export function PreAuthPage() {
  const { state, dispatch } = useAppContext();
  const [refresh, setRefresh] = useState(0);
  return (
    <div className="grid2" style={{ alignItems: "start" }}>
      <div style={{ display: "grid", gap: 12 }}>
        <ModuleHost
          moduleId="PreAuthHistoryList"
          context={{ patientId: state.patientId }}
          onOutput={async (o) => {
            dispatch({ type: "setJob", jobId: undefined });
            dispatch({ type: "setPreAuth", preAuthId: o.selectedPreAuthId });
            setRefresh((v) => v + 1);
            try {
              const pr = await apiFetch(`/preauth/${o.selectedPreAuthId}`);
              dispatch({ type: "setEncounter", encounterId: pr.encounterId || undefined });
            } catch {
              // ignore
            }
          }}
        />
        <ModuleHost
          moduleId="PreAuthCreateWizard"
          context={{ patientId: state.patientId, encounterId: state.encounterId, correlationId: state.correlationId }}
          onOutput={(o) => {
            dispatch({ type: "setJob", jobId: undefined });
            dispatch({ type: "setPreAuth", preAuthId: o.createdPreAuthId });
            setRefresh((v) => v + 1);
          }}
        />
      </div>
      <div style={{ display: "grid", gap: 12 }}>
        <ModuleHost moduleId="PreAuthRequestCard" context={{ preAuthId: state.preAuthId, jobId: state.jobId, refresh }} />
        <ModuleHost
          moduleId="SubmitButtonWithJobStatus"
          context={{ preAuthId: state.preAuthId, correlationId: state.correlationId, jobId: state.jobId, refresh }}
        />
        <ModuleHost moduleId="PreAuthPackageSnapshotViewer" context={{ preAuthId: state.preAuthId, jobId: state.jobId, refresh }} />
        <ModuleHost moduleId="DecisionPanel" context={{ preAuthId: state.preAuthId, jobId: state.jobId, refresh }} />
        <RequestedDocSection
          preAuthId={state.preAuthId}
          correlationId={state.correlationId}
          jobId={state.jobId}
          onAttached={() => setRefresh((v) => v + 1)}
        />
      </div>
    </div>
  );
}
