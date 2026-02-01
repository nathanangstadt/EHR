import React from "react";
import { ModuleHost } from "../../modules/ModuleHost";
import { useAppContext } from "../context";

export function JobsPage() {
  const { state, dispatch } = useAppContext();
  return (
    <div className="grid2">
      <ModuleHost moduleId="JobList" context={{}} onOutput={(o) => dispatch({ type: "setJob", jobId: o.selectedJobId })} />
      <ModuleHost moduleId="JobDetailPanel" context={{ jobId: state.jobId }} />
    </div>
  );
}

