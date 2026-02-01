export type AppEvent =
  | { type: "selectEventRef"; payload: { resourceType: string; id: string } }
  | { type: "setJobId"; payload: { jobId?: string } }
  | { type: "setPreAuthId"; payload: { preAuthId?: string } };

type Listener = (e: AppEvent) => void;
const listeners = new Set<Listener>();

export function emit(e: AppEvent) {
  for (const l of listeners) l(e);
}

export function subscribe(l: Listener) {
  listeners.add(l);
  return () => listeners.delete(l);
}

