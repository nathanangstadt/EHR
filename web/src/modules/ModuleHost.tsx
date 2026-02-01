import React from "react";
import registry from "./registry.json";
import { PatientSearchPanel } from "./components/PatientSearchPanel";
import { PatientCreateForm } from "./components/PatientCreateForm";
import { PatientSummaryCard } from "./components/PatientSummaryCard";
import { TimelineList } from "./components/TimelineList";
import { ClinicalEventDetailDrawer } from "./components/ClinicalEventDetailDrawer";
import { PreAuthCreateWizard } from "./components/PreAuthCreateWizard";
import { PreAuthHistoryList } from "./components/PreAuthHistoryList";
import { PreAuthRequestCard } from "./components/PreAuthRequestCard";
import { PreAuthPackageSnapshotViewer } from "./components/PreAuthPackageSnapshotViewer";
import { DecisionPanel } from "./components/DecisionPanel";
import { SubmitButtonWithJobStatus } from "./components/SubmitButtonWithJobStatus";
import { JobList } from "./components/JobList";
import { JobDetailPanel } from "./components/JobDetailPanel";
import { FHIRRequestComposer } from "./components/FHIRRequestComposer";
import { MappingTraceViewer } from "./components/MappingTraceViewer";
import { RequestedDocumentUploader } from "./components/RequestedDocumentUploader";
import { PayerRuleSetEditor } from "./components/PayerRuleSetEditor";
import { PayerPreAuthQueue } from "./components/PayerPreAuthQueue";
import { AdminTools } from "./components/AdminTools";

export type ModuleContext = {
  patientId?: string;
  encounterId?: string;
  preAuthId?: string;
  jobId?: string;
  correlationId?: string;
  refresh?: number;
};

type Props = {
  moduleId: string;
  context: ModuleContext;
  inputs?: any;
  onOutput?: (o: any) => void;
};

const components: Record<string, React.FC<any>> = {
  PatientSearchPanel,
  PatientCreateForm,
  PatientSummaryCard,
  TimelineList,
  ClinicalEventDetailDrawer,
  PreAuthCreateWizard,
  PreAuthHistoryList,
  PreAuthRequestCard,
  PreAuthPackageSnapshotViewer,
  DecisionPanel,
  RequestedDocumentUploader,
  SubmitButtonWithJobStatus,
  JobList,
  JobDetailPanel,
  FHIRRequestComposer,
  MappingTraceViewer,
  PayerRuleSetEditor,
  PayerPreAuthQueue,
  AdminTools,
};

export function ModuleHost({ moduleId, context, inputs, onOutput }: Props) {
  const meta = (registry as any[]).find((m) => m.id === moduleId);
  const Cmp = components[moduleId];
  if (!meta || !Cmp) return <div className="card">Unknown module</div>;

  const req = meta.requiredContext ?? {};
  const missing = Object.entries(req)
    .filter(([, v]) => v)
    .map(([k]) => k)
    .filter((k) => !(context as any)[k]);

  if (missing.length) {
    return (
      <div className="card">
        <div>
          <strong>{meta.title}</strong>
        </div>
        <div className="muted">Missing context: {missing.join(", ")}</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>{meta.title}</strong>
      </div>
      <Cmp context={context} inputs={inputs} onOutput={onOutput} />
    </div>
  );
}
