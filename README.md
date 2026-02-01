# Sample EHR + Payer Workflow Platform (SOM + FHIR R4 Facade)

This repo is a runnable sample that demonstrates:
- A hybrid **Semantic Object Model (SOM)** persistence layer (normalized core + `extensions` JSONB)
- A minimal, coherent **FHIR R4** REST facade under `/fhir`
- Async workflows with **Celery + Redis**, with job state persisted in **Postgres**
- A Phase 1 UI (Vite + React) that makes SOM/FHIR/provenance/audit/versioning/snapshots observable
- Phase 2-ready scaffolding: module registry + ModuleHost + context/event bus

## Quickstart

1) Create `.env` (first time only):

```bash
cp -n .env.example .env
```

2) Start everything:

```bash
docker compose up --build
```

UI: `http://localhost:${WEB_PORT:-5173}`  
API: `http://localhost:${API_PORT:-8000}`

The API container auto-runs migrations and seeds sample data when `AUTO_MIGRATE=1` and `AUTO_SEED=1` (default in `.env.example`).

## Payer-managed rules (Policy config)

The simulated payer decision logic is driven by a payer-managed rule set stored in Postgres (`som_payer_rule_set`).

- API: `GET /payer/rules?payer=Acme%20Payer` and `PUT /payer/rules?payer=Acme%20Payer`
- UI: **Payer Console → Payer Rule Set Editor**

Rule schema (current, minimal `schemaVersion=1`):
- `policies[]` with:
  - `services.cpt[]` (CPT codes)
  - `diagnosis.anyContains[]` (simple keyword matching on diagnosis display text)
  - `requiredDocuments[]` (`code`, `display`, `maxAgeDays`)
  - `outcome` (`approved|denied`)
  - `pendingInfoRationale` (used when required docs are missing)

## Key concepts (SOM hybrid persistence)

All SOM tables include:
- Stable query fields as relational columns
- `extensions JSONB NOT NULL DEFAULT '{}'` for evolving attributes

Schema evolution strategy:
- Unknown/mapping-specific fields go into `extensions`
- Promote stable fields to columns later (add migration + backfill) without breaking the mapping contract

## Provenance + Audit

Every create/update:
- creates a `SomProvenance` row (auto-created if omitted) with `sourceSystem="sample-app"` by default
- emits a `SomAuditEvent` row recording operation, correlation id, and optional payloads

Use `X-Correlation-Id` to make requests idempotent (repeat requests with the same correlation id return the prior result).

## Snapshot strategy (Pre-Authorization)

When a draft pre-auth is submitted:
- the API creates an immutable `SomPreAuthPackageSnapshot` containing a canonical JSON snapshot of referenced SOM objects
- checksum is computed over the canonical snapshot JSON
- a Celery job submits the package to a simulated payer and persists a `SomPreAuthDecision`

## API examples (FHIR facade)

Search patients:

```bash
curl "http://localhost:8000/fhir/Patient?name=doe&_count=10"
```

Create a patient:

```bash
curl -X POST "http://localhost:8000/fhir/Patient" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-1" \
  -d '{
    "resourceType":"Patient",
    "identifier":[{"system":"urn:mrn","value":"MRN-1001"}],
    "name":[{"family":"Doe","given":["Jane"]}],
    "birthDate":"1980-01-01"
  }'
```

Create an Observation (quantity):

```bash
curl -X POST "http://localhost:8000/fhir/Observation" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-obs-1" \
  -d '{
    "resourceType":"Observation",
    "status":"final",
    "category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/observation-category","code":"vital-signs"}]}],
    "code":{"coding":[{"system":"http://loinc.org","code":"8480-6","display":"Systolic blood pressure"}]},
    "subject":{"reference":"Patient/REPLACE_WITH_PATIENT_ID"},
    "effectiveDateTime":"2026-01-01T10:00:00Z",
    "valueQuantity":{"value":120,"unit":"mmHg"}
  }'
```

## API examples (Pre-Auth + Jobs)

Create a bulk import job (simulates batch inserts):

```bash
curl -X POST "http://localhost:8000/jobs" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-import-1" \
  -d '{
    "type":"bulk_import_observations",
    "parameters":{"patientId":"REPLACE_WITH_PATIENT_ID","count":25}
  }'
```

Create draft preauth:

```bash
curl -X POST "http://localhost:8000/preauth" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-preauth-1" \
  -d '{
    "patientId":"REPLACE",
    "practitionerId":"REPLACE",
    "diagnosisConditionId":"REPLACE",
    "serviceRequestId":"REPLACE",
    "priority":"routine",
    "payer":"Acme Payer",
    "supportingObservationIds":[]
  }'
```

Submit preauth (draft-only; creates snapshot + enqueues job):

```bash
curl -X POST "http://localhost:8000/preauth/REPLACE/submit" \
  -H "X-Correlation-Id: demo-preauth-submit-1"
```

Poll job:

```bash
curl "http://localhost:8000/jobs/JOB_ID"
```

## Resolving `pending-info` (upload the requested document)

If a pre-auth comes back as `pending-info` requesting a “Knee X-ray report (last 30 days)”, you can create a document using FHIR `Binary` + `DocumentReference`, attach it to the preauth, and re-submit.

1) Create `Binary` (text/plain):

```bash
DATA_B64="$(printf "Knee X-ray report\\nFindings: ...\\nImpression: ...\\n" | base64)"
curl -X POST "http://localhost:8000/fhir/Binary" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-xray-bin-1" \
  -d "{\"resourceType\":\"Binary\",\"contentType\":\"text/plain\",\"data\":\"${DATA_B64}\"}"
```

2) Create `DocumentReference` pointing at that `Binary/{id}`:

```bash
curl -X POST "http://localhost:8000/fhir/DocumentReference" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-xray-docref-1" \
  -d '{
    "resourceType":"DocumentReference",
    "status":"current",
    "subject":{"reference":"Patient/REPLACE_WITH_PATIENT_ID"},
    "type":{"coding":[{"system":"urn:sample-app:doc-type","code":"knee-xray-report","display":"Knee X-ray report"}]},
    "date":"2026-01-15T12:00:00Z",
    "description":"Knee X-ray report (last 30 days)",
    "content":[{"attachment":{"url":"Binary/REPLACE_WITH_BINARY_ID","contentType":"text/plain"}}]
  }'
```

3) Attach the document to the preauth:

```bash
curl -X POST "http://localhost:8000/preauth/REPLACE_WITH_PREAUTH_ID/documents" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-Id: demo-xray-attach-1" \
  -d '{"documentId":"REPLACE_WITH_DOCUMENT_REFERENCE_ID","role":"supporting"}'
```

4) Re-submit (`pending-info` only):

```bash
curl -X POST "http://localhost:8000/preauth/REPLACE_WITH_PREAUTH_ID/resubmit" \
  -H "X-Correlation-Id: demo-preauth-resubmit-1"
```

## Phase 1 UI modules + Phase 2 readiness

Modules are declared in `web/src/modules/registry.json` and rendered through `web/src/modules/ModuleHost.tsx`.

The app includes:
- a context store (active patient/encounter/correlationId)
- a tiny event bus so module outputs can update context or open other modules

This makes “agent composition” a deterministic orchestration problem in Phase 2: choose module ids + inputs and render via ModuleHost.

## Dev loop

- Backend hot reload: `uvicorn --reload` inside container
- Frontend hot reload: Vite dev server inside container
- Source is bind-mounted; DB/Redis use named volumes

## Tests (in containers)

```bash
docker compose run --rm api pytest -q
```

## Payer simulator rules

Worker rule set for **MRI Knee**:
- If diagnosis indicates **osteoarthritis** and service is **MRI knee** → `pending-info` (needs X-ray report)
- If diagnosis indicates **acute injury** and service is **MRI knee** → `approved`
- Otherwise → `denied`
