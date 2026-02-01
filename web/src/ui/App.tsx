import React, { useMemo, useState } from "react";
import { ContextBar } from "./ContextBar";
import { ContextProvider } from "../ui/context";
import { PatientsPage } from "../ui/pages/PatientsPage";
import { WorkspacePage } from "../ui/pages/WorkspacePage";
import { PreAuthPage } from "../ui/pages/PreAuthPage";
import { JobsPage } from "../ui/pages/JobsPage";
import { PayerConsolePage } from "../ui/pages/PayerConsolePage";
import { ModelInspectorPage } from "../ui/pages/ModelInspectorPage";

type PageId = "patients" | "workspace" | "preauth" | "jobs" | "payer" | "inspector";

export function App() {
  const [page, setPage] = useState<PageId>("patients");
  const items = useMemo(
    () =>
      [
        { id: "patients", title: "Patients" },
        { id: "workspace", title: "Patient Workspace" },
        { id: "preauth", title: "Pre-Authorization" },
        { id: "jobs", title: "Jobs" },
        { id: "payer", title: "Payer Console" },
        { id: "inspector", title: "Model Inspector" },
      ] as const,
    [],
  );

  return (
    <ContextProvider>
      <div className="appShell">
        <ContextBar />
        <div className="main">
          <nav className="nav">
            {items.map((i) => (
              <button
                key={i.id}
                className={page === i.id ? "active" : ""}
                onClick={() => setPage(i.id)}
              >
                {i.title}
              </button>
            ))}
          </nav>
          <div className="page">
            {page === "patients" && <PatientsPage />}
            {page === "workspace" && <WorkspacePage />}
            {page === "preauth" && <PreAuthPage />}
            {page === "jobs" && <JobsPage />}
            {page === "payer" && <PayerConsolePage />}
            {page === "inspector" && <ModelInspectorPage />}
          </div>
        </div>
      </div>
    </ContextProvider>
  );
}
