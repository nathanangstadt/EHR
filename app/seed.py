from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    SomBinary,
    SomCondition,
    SomDocument,
    SomEncounter,
    SomObservation,
    SomOrganization,
    SomPatient,
    SomPractitioner,
    SomPreAuthDecision,
    SomPreAuthPackageSnapshot,
    SomPreAuthRequest,
    SomPreAuthStatusHistory,
    SomServiceRequest,
    SomServiceRequestReason,
)
from app.db.session import session_scope
from app.services.preauth.service import PreAuthService
from app.services.provenance import ProvenanceService
from app.services.payer.rules import PayerRuleService
from app.services.terminology import TerminologyService


def seed(db: Session) -> dict[str, str]:
    existing = db.execute(select(SomPatient).limit(1)).scalar_one_or_none()
    if existing:
        return {"ok": "already-seeded"}

    prov = ProvenanceService(db).create(activity="seed", author="seed", correlation_id="seed")

    p1 = SomPatient(
        identifier_system="urn:mrn",
        identifier_value="MRN-1001",
        name_family="Doe",
        name_given="Jane",
        birth_date=dt.date(1980, 1, 1),
        created_provenance_id=prov.id,
        extensions={},
    )
    p2 = SomPatient(
        identifier_system="urn:mrn",
        identifier_value="MRN-1002",
        name_family="Roe",
        name_given="John",
        birth_date=dt.date(1975, 6, 15),
        created_provenance_id=prov.id,
        extensions={},
    )
    db.add_all([p1, p2])
    db.flush()

    prac = SomPractitioner(name="Dr. Alice Example", created_provenance_id=prov.id, extensions={})
    org = SomOrganization(name="Sample Ortho Clinic", created_provenance_id=prov.id, extensions={})
    db.add_all([prac, org])
    db.flush()

    e1 = SomEncounter(
        patient_id=p1.id,
        status="in-progress",
        start_time=dt.datetime(2026, 1, 5, 10, 0, tzinfo=dt.timezone.utc),
        end_time=None,
        created_provenance_id=prov.id,
        extensions={},
    )
    e2 = SomEncounter(
        patient_id=p1.id,
        status="finished",
        start_time=dt.datetime(2025, 12, 10, 9, 0, tzinfo=dt.timezone.utc),
        end_time=dt.datetime(2025, 12, 10, 10, 0, tzinfo=dt.timezone.utc),
        created_provenance_id=prov.id,
        extensions={},
    )
    e3 = SomEncounter(
        patient_id=p2.id,
        status="finished",
        start_time=dt.datetime(2025, 11, 1, 12, 0, tzinfo=dt.timezone.utc),
        end_time=dt.datetime(2025, 11, 1, 12, 30, tzinfo=dt.timezone.utc),
        created_provenance_id=prov.id,
        extensions={},
    )
    db.add_all([e1, e2, e3])
    db.flush()

    snomed = "http://snomed.info/sct"
    loinc = "http://loinc.org"
    cpt = "http://www.ama-assn.org/go/cpt"
    docsys = "urn:sample-app:doc-type"

    oa = TerminologyService(db).normalize_concept(system=snomed, code="396275006", display="Osteoarthritis", version=None, correlation_id="seed")
    acute = TerminologyService(db).normalize_concept(system=snomed, code="263204007", display="Acute knee injury", version=None, correlation_id="seed")
    htn = TerminologyService(db).normalize_concept(system=snomed, code="38341003", display="Hypertension", version=None, correlation_id="seed")
    mri_knee = TerminologyService(db).normalize_concept(system=cpt, code="73721", display="MRI knee wo contrast", version=None, correlation_id="seed")
    sys_bp = TerminologyService(db).normalize_concept(system=loinc, code="8480-6", display="Systolic blood pressure", version=None, correlation_id="seed")
    glu = TerminologyService(db).normalize_concept(system=loinc, code="2345-7", display="Glucose [Mass/volume] in Serum or Plasma", version=None, correlation_id="seed")
    xray_doc = TerminologyService(db).normalize_concept(system=docsys, code="knee-xray-report", display="Knee X-ray report", version=None, correlation_id="seed")

    c1 = SomCondition(
        patient_id=p1.id,
        code_concept_id=oa.id,
        clinical_status="active",
        onset_date=dt.date(2024, 1, 1),
        created_provenance_id=prov.id,
        extensions={},
    )
    c2 = SomCondition(
        patient_id=p1.id,
        code_concept_id=acute.id,
        clinical_status="active",
        onset_date=dt.date(2026, 1, 1),
        created_provenance_id=prov.id,
        extensions={},
    )
    c3 = SomCondition(
        patient_id=p2.id,
        code_concept_id=htn.id,
        clinical_status="active",
        onset_date=dt.date(2020, 1, 1),
        created_provenance_id=prov.id,
        extensions={},
    )
    db.add_all([c1, c2, c3])
    db.flush()

    sr1 = SomServiceRequest(
        patient_id=p1.id,
        encounter_id=e2.id,
        code_concept_id=mri_knee.id,
        status="active",
        intent="order",
        priority="routine",
        authored_on=dt.datetime(2025, 12, 10, 9, 20, tzinfo=dt.timezone.utc),
        created_provenance_id=prov.id,
        extensions={},
    )
    sr2 = SomServiceRequest(
        patient_id=p1.id,
        encounter_id=e1.id,
        code_concept_id=mri_knee.id,
        status="draft",
        intent="order",
        priority="urgent",
        authored_on=dt.datetime(2026, 1, 5, 10, 5, tzinfo=dt.timezone.utc),
        created_provenance_id=prov.id,
        extensions={},
    )
    sr3 = SomServiceRequest(
        patient_id=p2.id,
        code_concept_id=mri_knee.id,
        status="active",
        intent="order",
        priority="routine",
        authored_on=dt.datetime(2025, 11, 1, 12, 0, tzinfo=dt.timezone.utc),
        created_provenance_id=prov.id,
        extensions={},
    )
    db.add_all([sr1, sr2, sr3])
    db.flush()

    # Link service requests to diagnosis conditions (FHIR-like reasonReference).
    db.add_all(
        [
            SomServiceRequestReason(
                service_request_id=sr1.id,
                condition_id=c1.id,
                role="reason",
                rank=1,
                created_provenance_id=prov.id,
                extensions={},
            ),
            SomServiceRequestReason(
                service_request_id=sr2.id,
                condition_id=c2.id,
                role="reason",
                rank=1,
                created_provenance_id=prov.id,
                extensions={},
            ),
        ]
    )

    # Observations (10 total): encounter-scoped vitals + labs; include one corrected version via extensions marker
    obs = []
    # Encounter e2 (older): a couple vitals + labs (OA context)
    obs.append(
        SomObservation(
            patient_id=p1.id,
            encounter_id=e2.id,
            status="final",
            category="vital",
            code_concept_id=sys_bp.id,
            effective_time=dt.datetime(2025, 12, 10, 9, 5, tzinfo=dt.timezone.utc),
            value_type="quantity",
            value_quantity_value=128,
            value_quantity_unit="mmHg",
            value_concept_id=None,
            created_provenance_id=prov.id,
            extensions={"context": "oa"},
        )
    )
    obs.append(
        SomObservation(
            patient_id=p1.id,
            encounter_id=e2.id,
            status="final",
            category="lab",
            code_concept_id=glu.id,
            effective_time=dt.datetime(2025, 12, 10, 9, 10, tzinfo=dt.timezone.utc),
            value_type="quantity",
            value_quantity_value=96,
            value_quantity_unit="mg/dL",
            value_concept_id=None,
            created_provenance_id=prov.id,
            extensions={"context": "oa"},
        )
    )
    for i in range(4):
        obs.append(
            SomObservation(
                patient_id=p1.id,
                encounter_id=e1.id,
                status="final",
                category="vital",
                code_concept_id=sys_bp.id,
                effective_time=dt.datetime(2026, 1, 5, 10, 0 + i, tzinfo=dt.timezone.utc),
                value_type="quantity",
                value_quantity_value=120 + i,
                value_quantity_unit="mmHg",
                value_concept_id=None,
                created_provenance_id=prov.id,
                extensions={},
            )
        )
    for i in range(4):
        obs.append(
            SomObservation(
                patient_id=p1.id,
                encounter_id=e1.id,
                status="final",
                category="lab",
                code_concept_id=glu.id,
                effective_time=dt.datetime(2026, 1, 5, 9, 0 + i, tzinfo=dt.timezone.utc),
                value_type="quantity",
                value_quantity_value=90 + i,
                value_quantity_unit="mg/dL",
                value_concept_id=None,
                created_provenance_id=prov.id,
                extensions={"corrected": i == 3},
            )
        )
    db.add_all(obs)
    db.flush()

    # Example X-ray report document (not linked to preauth by default).
    xray_text = b"Knee X-ray report (seed)\nFindings: mild osteoarthritis.\nImpression: no acute fracture.\n"
    xray_sha = hashlib.sha256(xray_text).hexdigest()
    xbin = SomBinary(
        content_type="text/plain",
        data=xray_text,
        size_bytes=len(xray_text),
        sha256_hex=xray_sha,
        created_provenance_id=prov.id,
        extensions={},
    )
    db.add(xbin)
    db.flush()
    xdoc = SomDocument(
        patient_id=p1.id,
        encounter_id=e1.id,
        status="current",
        type_concept_id=xray_doc.id,
        date_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7),
        title="Knee X-ray report (seed, last 30 days)",
        description="Knee X-ray report",
        binary_id=xbin.id,
        created_provenance_id=prov.id,
        extensions={},
    )
    db.add(xdoc)
    db.flush()

    # PreAuth drafts + one submitted with snapshot/decision
    pa1 = SomPreAuthRequest(
        patient_id=p1.id,
        encounter_id=e1.id,
        practitioner_id=prac.id,
        organization_id=org.id,
        diagnosis_condition_id=c1.id,  # osteoarthritis
        service_request_id=sr1.id,  # MRI knee
        status="draft",
        priority="routine",
        payer="Acme Payer",
        policy_id="POL-1",
        notes="Seed draft",
        created_provenance_id=prov.id,
        extensions={"supportingObservationIds": [str(obs[0].id)]},
    )
    pa2 = SomPreAuthRequest(
        patient_id=p1.id,
        encounter_id=e1.id,
        practitioner_id=prac.id,
        organization_id=org.id,
        diagnosis_condition_id=c2.id,  # acute injury
        service_request_id=sr2.id,
        status="draft",
        priority="urgent",
        payer="Acme Payer",
        policy_id="POL-2",
        notes="Seed draft 2",
        created_provenance_id=prov.id,
        extensions={"supportingObservationIds": [str(obs[2].id), str(obs[3].id)]},
    )
    db.add_all([pa1, pa2])
    db.flush()

    db.add_all(
        [
            SomPreAuthStatusHistory(preauth_request_id=pa1.id, from_status=None, to_status="draft", changed_by="seed", correlation_id="seed", extensions={}),
            SomPreAuthStatusHistory(preauth_request_id=pa2.id, from_status=None, to_status="draft", changed_by="seed", correlation_id="seed", extensions={}),
        ]
    )

    # Seed a submitted + decision snapshot
    pa3 = SomPreAuthRequest(
        patient_id=p1.id,
        encounter_id=e1.id,
        practitioner_id=prac.id,
        organization_id=org.id,
        diagnosis_condition_id=c1.id,  # osteoarthritis -> pending-info
        service_request_id=sr1.id,
        status="submitted",
        priority="routine",
        payer="Acme Payer",
        policy_id="POL-3",
        notes="Seed submitted",
        created_provenance_id=prov.id,
        extensions={"supportingObservationIds": [str(obs[0].id)]},
    )
    db.add(pa3)
    db.flush()
    db.add(SomPreAuthStatusHistory(preauth_request_id=pa3.id, from_status=None, to_status="submitted", changed_by="seed", correlation_id="seed", extensions={}))

    PreAuthService(db)._create_snapshot(pa3, correlation_id="seed")
    dec_prov = ProvenanceService(db).create(activity="payer-determination", author="seed-payer", correlation_id="seed")
    decision = SomPreAuthDecision(
        preauth_request_id=pa3.id,
        decided_time=dt.datetime.now(dt.timezone.utc),
        outcome="pending-info",
        reason_codes=[{"code": "need-xray", "display": "X-ray report required"}],
        rationale="Need knee X-ray report before approving.",
        requested_additional_info=[{"type": "document", "display": "Knee X-ray report (last 30 days)"}],
        raw_payer_response={"outcome": "pending-info"},
        provenance_id=dec_prov.id,
        extensions={},
    )
    db.add(decision)
    pa3.status = "pending-info"
    db.add(SomPreAuthStatusHistory(preauth_request_id=pa3.id, from_status="submitted", to_status="pending-info", changed_by="seed-payer", correlation_id="seed", extensions={}))

    # Seed payer-managed rules for "Acme Payer"
    PayerRuleService(db).upsert_active(
        payer="Acme Payer",
        correlation_id="seed",
        notes="Seed ruleset",
        rules={
            "schemaVersion": "1",
            "policies": [
                {
                    "id": "mri-knee-oa",
                    "services": {
                        "codes": [
                            {"system": cpt, "code": "73721"},
                            {"system": cpt, "code": "73722"},
                            {"system": cpt, "code": "73723"},
                        ]
                    },
                    "diagnosis": {"codes": [{"system": snomed, "code": "396275006"}]},
                    "requiredDocuments": [
                        {"code": "knee-xray-report", "display": "Knee X-ray report (last 30 days)", "maxAgeDays": 30}
                    ],
                    "outcome": "approved",
                    "rationale": "Osteoarthritis criteria met with required documentation.",
                    "pendingInfoRationale": "Need recent knee X-ray report before approving advanced imaging.",
                },
                {
                    "id": "mri-knee-acute",
                    "services": {
                        "codes": [
                            {"system": cpt, "code": "73721"},
                            {"system": cpt, "code": "73722"},
                            {"system": cpt, "code": "73723"},
                        ]
                    },
                    "diagnosis": {"codes": [{"system": snomed, "code": "263204007"}]},
                    "requiredDocuments": [],
                    "outcome": "approved",
                    "rationale": "Acute injury criteria met for MRI knee.",
                },
            ],
        },
    )

    return {"ok": "seeded"}


def main() -> None:
    with session_scope() as db:
        seed(db)


if __name__ == "__main__":
    main()
