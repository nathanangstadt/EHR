from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.mapping.fhir_dispatch import fhir_create
from app.services.preauth.service import PreAuthService


_TEMPLATES = {
    "knee-oa-mri": {
        "title": "Knee OA + MRI Knee (likely pending-info)",
        "diagnosis": {"system": "http://snomed.info/sct", "code": "396275006", "display": "Osteoarthritis"},
        "service": {"system": "http://www.ama-assn.org/go/cpt", "code": "73721", "display": "MRI knee wo contrast"},
        "priority": "routine",
    },
    "knee-acute-mri": {
        "title": "Acute knee injury + MRI Knee (likely approved)",
        "diagnosis": {"system": "http://snomed.info/sct", "code": "263204007", "display": "Acute knee injury"},
        "service": {"system": "http://www.ama-assn.org/go/cpt", "code": "73721", "display": "MRI knee wo contrast"},
        "priority": "urgent",
    },
}


class ScenarioService:
    def __init__(self, db: Session):
        self.db = db

    def list_templates(self) -> dict[str, Any]:
        return {"templates": [{"id": k, **v} for k, v in _TEMPLATES.items()]}

    def create_from_template(self, body: dict[str, Any], *, correlation_id: str | None) -> dict[str, Any]:
        if settings.app_env != "dev":
            raise ValueError("Scenario creation is only allowed when APP_ENV=dev")

        template_id = body.get("templateId")
        if template_id not in _TEMPLATES:
            raise ValueError("Unknown templateId")
        tmpl = _TEMPLATES[template_id]

        patient_in = body.get("patient") or {}
        family = patient_in.get("family") or "Test"
        given = patient_in.get("given") or "Patient"
        birth_date = patient_in.get("birthDate") or "1980-01-01"
        mrn = patient_in.get("mrn") or f"MRN-{dt.datetime.now(dt.timezone.utc).strftime('%H%M%S')}"

        now = dt.datetime.now(dt.timezone.utc)

        # 1) Create Patient
        patient = fhir_create(
            self.db,
            "Patient",
            {
                "resourceType": "Patient",
                "identifier": [{"system": "urn:mrn", "value": mrn}],
                "name": [{"family": family, "given": [given]}],
                "birthDate": birth_date,
            },
            correlation_id=correlation_id,
        )

        # 2) Create a Practitioner (so preauth can be created without hunting for one)
        practitioner = fhir_create(
            self.db,
            "Practitioner",
            {"resourceType": "Practitioner", "name": [{"text": "Dr. Scenario User"}]},
            correlation_id=correlation_id,
        )

        # 3) Create Encounter
        encounter = fhir_create(
            self.db,
            "Encounter",
            {
                "resourceType": "Encounter",
                "status": "in-progress",
                "subject": {"reference": f"Patient/{patient['id']}"},
                "period": {"start": (now - dt.timedelta(hours=2)).isoformat()},
            },
            correlation_id=correlation_id,
        )

        # 4) Create Condition (diagnosis / indication)
        diagnosis = tmpl["diagnosis"]
        condition = fhir_create(
            self.db,
            "Condition",
            {
                "resourceType": "Condition",
                "subject": {"reference": f"Patient/{patient['id']}"},
                "code": {"coding": [diagnosis]},
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "onsetDateTime": (now - dt.timedelta(days=10)).date().isoformat(),
            },
            correlation_id=correlation_id,
        )

        # 5) Create ServiceRequest linked to Condition + Encounter
        service = tmpl["service"]
        service_request = fhir_create(
            self.db,
            "ServiceRequest",
            {
                "resourceType": "ServiceRequest",
                "status": "active",
                "intent": "order",
                "priority": tmpl["priority"],
                "subject": {"reference": f"Patient/{patient['id']}"},
                "encounter": {"reference": f"Encounter/{encounter['id']}"},
                "reasonReference": [{"reference": f"Condition/{condition['id']}"}],
                "code": {"coding": [service]},
                "authoredOn": now.isoformat(),
            },
            correlation_id=correlation_id,
        )

        # 6) Create a few supporting observations
        obs1 = fhir_create(
            self.db,
            "Observation",
            {
                "resourceType": "Observation",
                "status": "final",
                "category": [{"coding": [{"code": "vital-signs"}]}],
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]},
                "subject": {"reference": f"Patient/{patient['id']}"},
                "encounter": {"reference": f"Encounter/{encounter['id']}"},
                "effectiveDateTime": (now - dt.timedelta(minutes=30)).isoformat(),
                "valueQuantity": {"value": 128, "unit": "mmHg"},
            },
            correlation_id=correlation_id,
        )
        obs2 = fhir_create(
            self.db,
            "Observation",
            {
                "resourceType": "Observation",
                "status": "final",
                "category": [{"coding": [{"code": "laboratory"}]}],
                "code": {"coding": [{"system": "http://loinc.org", "code": "2345-7", "display": "Glucose [Mass/volume] in Serum or Plasma"}]},
                "subject": {"reference": f"Patient/{patient['id']}"},
                "encounter": {"reference": f"Encounter/{encounter['id']}"},
                "effectiveDateTime": (now - dt.timedelta(minutes=60)).isoformat(),
                "valueQuantity": {"value": 96, "unit": "mg/dL"},
            },
            correlation_id=correlation_id,
        )

        preauth_id = None
        if body.get("createPreAuthDraft"):
            payer = body.get("payer") or "Acme Payer"
            pr = PreAuthService(self.db).create_draft(
                {
                    "patientId": patient["id"],
                    "encounterId": encounter["id"],
                    "practitionerId": practitioner["id"],
                    "diagnosisConditionId": condition["id"],
                    "serviceRequestId": service_request["id"],
                    "priority": "routine",
                    "payer": payer,
                    "supportingObservationIds": [obs1["id"], obs2["id"]],
                },
                correlation_id=correlation_id,
            )
            preauth_id = pr.get("id")

        return {
            "templateId": template_id,
            "patientId": patient["id"],
            "practitionerId": practitioner["id"],
            "encounterId": encounter["id"],
            "conditionId": condition["id"],
            "serviceRequestId": service_request["id"],
            "observationIds": [obs1["id"], obs2["id"]],
            "preAuthId": preauth_id,
        }

