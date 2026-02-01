import React, { createContext, useContext, useMemo, useReducer } from "react";

export type AppContextState = {
  patientId?: string;
  encounterId?: string;
  preAuthId?: string;
  jobId?: string;
  correlationId: string;
  userDisplay: string;
};

type Action =
  | { type: "setPatient"; patientId?: string }
  | { type: "setEncounter"; encounterId?: string }
  | { type: "setCorrelationId"; correlationId: string }
  | { type: "setPreAuth"; preAuthId?: string }
  | { type: "setJob"; jobId?: string };

function genCorrelationId(): string {
  return `ui-${crypto.randomUUID()}`;
}

function reducer(state: AppContextState, action: Action): AppContextState {
  switch (action.type) {
    case "setPatient":
      if (action.patientId === state.patientId) return state;
      // Patient change invalidates patient-scoped context.
      return {
        ...state,
        patientId: action.patientId,
        encounterId: undefined,
        preAuthId: undefined,
        jobId: undefined,
      };
    case "setEncounter":
      return { ...state, encounterId: action.encounterId };
    case "setCorrelationId":
      return { ...state, correlationId: action.correlationId };
    case "setPreAuth":
      return { ...state, preAuthId: action.preAuthId };
    case "setJob":
      return { ...state, jobId: action.jobId };
    default:
      return state;
  }
}

const Ctx = createContext<
  | {
      state: AppContextState;
      dispatch: React.Dispatch<Action>;
    }
  | undefined
>(undefined);

export function ContextProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    correlationId: genCorrelationId(),
    userDisplay: "Dr. Sample User",
  });
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppContext() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAppContext must be used within ContextProvider");
  return ctx;
}
