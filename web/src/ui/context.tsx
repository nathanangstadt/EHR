import React, { createContext, useContext, useEffect, useMemo, useReducer } from "react";

export type AppContextState = {
  patientId?: string;
  encounterId?: string;
  preAuthId?: string;
  jobId?: string;
  correlationId: string;
  userDisplay: string;
};

const STORAGE_KEY = "ehr.ui.context.v1";

type Action =
  | { type: "setPatient"; patientId?: string }
  | { type: "setEncounter"; encounterId?: string }
  | { type: "setCorrelationId"; correlationId: string }
  | { type: "setPreAuth"; preAuthId?: string }
  | { type: "setJob"; jobId?: string };

function genCorrelationId(): string {
  return `ui-${crypto.randomUUID()}`;
}

function loadStateFromStorage(): Partial<AppContextState> | undefined {
  try {
    if (typeof window === "undefined") return undefined;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return undefined;

    const s: Partial<AppContextState> = {};
    if (typeof parsed.patientId === "string" && parsed.patientId) s.patientId = parsed.patientId;
    if (typeof parsed.encounterId === "string" && parsed.encounterId) s.encounterId = parsed.encounterId;
    if (typeof parsed.preAuthId === "string" && parsed.preAuthId) s.preAuthId = parsed.preAuthId;
    if (typeof parsed.jobId === "string" && parsed.jobId) s.jobId = parsed.jobId;
    if (typeof parsed.correlationId === "string" && parsed.correlationId) s.correlationId = parsed.correlationId;
    if (typeof parsed.userDisplay === "string" && parsed.userDisplay) s.userDisplay = parsed.userDisplay;
    return s;
  } catch {
    return undefined;
  }
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
  const [state, dispatch] = useReducer(reducer, undefined, () => {
    const stored = loadStateFromStorage();
    return {
      correlationId: stored?.correlationId ?? genCorrelationId(),
      userDisplay: stored?.userDisplay ?? "Dr. Sample User",
      patientId: stored?.patientId,
      encounterId: stored?.encounterId,
      preAuthId: stored?.preAuthId,
      jobId: stored?.jobId,
    };
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          patientId: state.patientId,
          encounterId: state.encounterId,
          preAuthId: state.preAuthId,
          jobId: state.jobId,
          correlationId: state.correlationId,
          userDisplay: state.userDisplay,
        }),
      );
    } catch {
      // ignore storage errors (private mode, quota, etc.)
    }
  }, [state]);

  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppContext() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAppContext must be used within ContextProvider");
  return ctx;
}
