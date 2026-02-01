from fastapi.testclient import TestClient

from app.main import app


def test_condition_service_request_normalization_and_provenance():
    client = TestClient(app)
    patient = client.post(
        "/fhir/Patient",
        json={"resourceType": "Patient", "name": [{"family": "Norm", "given": ["A"]}]},
        headers={"X-Correlation-Id": "t-norm-p"},
    ).json()

    cond = client.post(
        "/fhir/Condition",
        json={
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "396275006", "display": "Osteoarthritis"}]},
            "clinicalStatus": {"coding": [{"code": "active"}]},
        },
        headers={"X-Correlation-Id": "t-norm-c"},
    ).json()

    sr = client.post(
        "/fhir/ServiceRequest",
        json={
            "resourceType": "ServiceRequest",
            "status": "active",
            "intent": "order",
            "priority": "routine",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "code": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": "73721", "display": "MRI knee wo contrast"}]},
            "reasonReference": [{"reference": f"Condition/{cond['id']}"}],
            "encounter": {"reference": "Encounter/00000000-0000-0000-0000-000000000000"},
            "authoredOn": "2026-01-01T10:00:00Z",
        },
        headers={"X-Correlation-Id": "t-norm-sr"},
    )
    assert sr.status_code == 400
    # encounter reference validation requires a real Encounter id; create one and retry.
    enc = client.post(
        "/fhir/Encounter",
        json={
            "resourceType": "Encounter",
            "status": "in-progress",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "period": {"start": "2026-01-01T09:00:00Z"},
        },
        headers={"X-Correlation-Id": "t-norm-enc"},
    ).json()
    sr = client.post(
        "/fhir/ServiceRequest",
        json={
            "resourceType": "ServiceRequest",
            "status": "active",
            "intent": "order",
            "priority": "routine",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "encounter": {"reference": f"Encounter/{enc['id']}"},
            "code": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": "73721", "display": "MRI knee wo contrast"}]},
            "reasonReference": [{"reference": f"Condition/{cond['id']}"}],
            "authoredOn": "2026-01-01T10:00:00Z",
        },
        headers={"X-Correlation-Id": "t-norm-sr2"},
    ).json()

    som_cond = client.get(f"/internal/som/Condition/{cond['id']}").json()
    assert som_cond["codeConcept"]["system"] == "http://snomed.info/sct"
    assert som_cond["codeConcept"]["code"] == "396275006"
    assert som_cond["row"]["created_provenance_id"]

    som_sr = client.get(f"/internal/som/ServiceRequest/{sr['id']}").json()
    assert som_sr["codeConcept"]["system"] == "http://www.ama-assn.org/go/cpt"
    assert som_sr["codeConcept"]["code"] == "73721"
    assert som_sr["row"]["created_provenance_id"]
    assert cond["id"] in (som_sr.get("reasonConditionIds") or [])

    # FHIR read should include reasonReference
    sr_read = client.get(f"/fhir/ServiceRequest/{sr['id']}").json()
    refs = [r.get("reference") for r in (sr_read.get("reasonReference") or [])]
    assert f"Condition/{cond['id']}" in refs
    assert sr_read.get("encounter", {}).get("reference") == f"Encounter/{enc['id']}"


def test_preauth_submit_creates_snapshot_job_and_decision():
    client = TestClient(app)

    patient = client.post(
        "/fhir/Patient",
        json={"resourceType": "Patient", "name": [{"family": "Pre", "given": ["Auth"]}]},
        headers={"X-Correlation-Id": "t-pa-p"},
    ).json()
    prac = client.post(
        "/fhir/Practitioner",
        json={"resourceType": "Practitioner", "name": [{"text": "Dr. Test"}]},
        headers={"X-Correlation-Id": "t-pa-pr"},
    ).json()
    cond = client.post(
        "/fhir/Condition",
        json={
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "396275006", "display": "Osteoarthritis"}]},
            "clinicalStatus": {"coding": [{"code": "active"}]},
        },
        headers={"X-Correlation-Id": "t-pa-c"},
    ).json()
    sr = client.post(
        "/fhir/ServiceRequest",
        json={
            "resourceType": "ServiceRequest",
            "status": "active",
            "intent": "order",
            "priority": "routine",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "code": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": "73721", "display": "MRI knee wo contrast"}]},
            "authoredOn": "2026-01-01T10:00:00Z",
        },
        headers={"X-Correlation-Id": "t-pa-sr"},
    ).json()

    draft = client.post(
        "/preauth",
        json={
            "patientId": patient["id"],
            "practitionerId": prac["id"],
            "diagnosisConditionId": cond["id"],
            "serviceRequestId": sr["id"],
            "priority": "routine",
            "payer": "Acme Payer",
            "supportingObservationIds": [],
        },
        headers={"X-Correlation-Id": "t-pa-create"},
    ).json()
    assert draft["status"] == "draft"

    submit = client.post(f"/preauth/{draft['id']}/submit", headers={"X-Correlation-Id": "t-pa-submit"}).json()
    assert submit["jobId"]
    assert submit["snapshotId"]

    job = client.get(f"/jobs/{submit['jobId']}").json()
    assert job["status"] == "succeeded"
    assert job["outputs"]["outcome"] in {"approved", "denied", "pending-info"}

    refreshed = client.get(f"/preauth/{draft['id']}").json()
    assert refreshed["latestSnapshot"] is not None
    assert refreshed["latestDecision"] is not None
    # Osteoarthritis + MRI knee => pending-info
    assert refreshed["latestDecision"]["outcome"] == "pending-info"


def test_pending_info_resolved_by_xray_document():
    client = TestClient(app)

    patient = client.post(
        "/fhir/Patient",
        json={"resourceType": "Patient", "name": [{"family": "Xray", "given": ["Needed"]}]},
        headers={"X-Correlation-Id": "t-xray-p"},
    ).json()
    prac = client.post(
        "/fhir/Practitioner",
        json={"resourceType": "Practitioner", "name": [{"text": "Dr. Xray"}]},
        headers={"X-Correlation-Id": "t-xray-pr"},
    ).json()
    cond = client.post(
        "/fhir/Condition",
        json={
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "396275006", "display": "Osteoarthritis"}]},
            "clinicalStatus": {"coding": [{"code": "active"}]},
        },
        headers={"X-Correlation-Id": "t-xray-c"},
    ).json()
    sr = client.post(
        "/fhir/ServiceRequest",
        json={
            "resourceType": "ServiceRequest",
            "status": "active",
            "intent": "order",
            "priority": "routine",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "code": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": "73721", "display": "MRI knee wo contrast"}]},
            "authoredOn": "2026-01-01T10:00:00Z",
        },
        headers={"X-Correlation-Id": "t-xray-sr"},
    ).json()

    draft = client.post(
        "/preauth",
        json={
            "patientId": patient["id"],
            "practitionerId": prac["id"],
            "diagnosisConditionId": cond["id"],
            "serviceRequestId": sr["id"],
            "priority": "routine",
            "payer": "Acme Payer",
            "supportingObservationIds": [],
        },
        headers={"X-Correlation-Id": "t-xray-create"},
    ).json()

    submit1 = client.post(f"/preauth/{draft['id']}/submit", headers={"X-Correlation-Id": "t-xray-submit1"}).json()
    job1 = client.get(f"/jobs/{submit1['jobId']}").json()
    assert job1["status"] == "succeeded"
    refreshed1 = client.get(f"/preauth/{draft['id']}").json()
    assert refreshed1["latestDecision"]["outcome"] == "pending-info"

    # Create Binary + DocumentReference for knee x-ray report and attach it.
    import base64

    b = client.post(
        "/fhir/Binary",
        json={
            "resourceType": "Binary",
            "contentType": "text/plain",
            "data": base64.b64encode(b"Knee X-ray report\n").decode("ascii"),
        },
        headers={"X-Correlation-Id": "t-xray-bin"},
    ).json()
    doc = client.post(
        "/fhir/DocumentReference",
        json={
            "resourceType": "DocumentReference",
            "status": "current",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "type": {"coding": [{"system": "urn:sample-app:doc-type", "code": "knee-xray-report", "display": "Knee X-ray report"}]},
            "date": "2026-01-20T12:00:00Z",
            "description": "Knee X-ray report (last 30 days)",
            "content": [{"attachment": {"url": f"Binary/{b['id']}", "contentType": "text/plain"}}],
        },
        headers={"X-Correlation-Id": "t-xray-doc"},
    ).json()
    link = client.post(
        f"/preauth/{draft['id']}/documents",
        json={"documentId": doc["id"], "role": "supporting"},
        headers={"X-Correlation-Id": "t-xray-attach"},
    )
    assert link.status_code == 200

    submit2 = client.post(f"/preauth/{draft['id']}/resubmit", headers={"X-Correlation-Id": "t-xray-submit2"}).json()
    job2 = client.get(f"/jobs/{submit2['jobId']}").json()
    assert job2["status"] == "succeeded"
    refreshed2 = client.get(f"/preauth/{draft['id']}").json()
    assert refreshed2["latestDecision"]["outcome"] == "approved"


def test_payer_ruleset_can_override_outcome():
    client = TestClient(app)

    # Install an active payer rule set that denies osteoarthritis MRI knee regardless of docs.
    put = client.put(
        "/payer/rules?payer=Acme%20Payer",
        json={
            "rules": {
                "schemaVersion": "1",
                "policies": [
                    {
                        "id": "deny-oa-mri-knee",
                        "services": {"cpt": ["73721", "73722", "73723"]},
                        "diagnosis": {"anyContains": ["osteoarthritis"]},
                        "requiredDocuments": [],
                        "outcome": "denied",
                        "reasonCodes": [{"code": "policy-denial", "display": "Policy denies OA MRI knee"}],
                        "rationale": "Requires conservative therapy trial before MRI.",
                    }
                ],
            }
        },
        headers={"X-Correlation-Id": "t-payer-rules-1"},
    )
    assert put.status_code == 200

    patient = client.post(
        "/fhir/Patient",
        json={"resourceType": "Patient", "name": [{"family": "Rule", "given": ["Override"]}]},
        headers={"X-Correlation-Id": "t-pr-p"},
    ).json()
    prac = client.post(
        "/fhir/Practitioner",
        json={"resourceType": "Practitioner", "name": [{"text": "Dr. Rule"}]},
        headers={"X-Correlation-Id": "t-pr-pr"},
    ).json()
    cond = client.post(
        "/fhir/Condition",
        json={
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "396275006", "display": "Osteoarthritis"}]},
            "clinicalStatus": {"coding": [{"code": "active"}]},
        },
        headers={"X-Correlation-Id": "t-pr-c"},
    ).json()
    sr = client.post(
        "/fhir/ServiceRequest",
        json={
            "resourceType": "ServiceRequest",
            "status": "active",
            "intent": "order",
            "priority": "routine",
            "subject": {"reference": f"Patient/{patient['id']}"},
            "code": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": "73721", "display": "MRI knee wo contrast"}]},
            "authoredOn": "2026-01-01T10:00:00Z",
        },
        headers={"X-Correlation-Id": "t-pr-sr"},
    ).json()

    draft = client.post(
        "/preauth",
        json={
            "patientId": patient["id"],
            "practitionerId": prac["id"],
            "diagnosisConditionId": cond["id"],
            "serviceRequestId": sr["id"],
            "priority": "routine",
            "payer": "Acme Payer",
            "supportingObservationIds": [],
        },
        headers={"X-Correlation-Id": "t-pr-create"},
    ).json()

    submit = client.post(f"/preauth/{draft['id']}/submit", headers={"X-Correlation-Id": "t-pr-submit"}).json()
    job = client.get(f"/jobs/{submit['jobId']}").json()
    assert job["status"] == "succeeded"
    refreshed = client.get(f"/preauth/{draft['id']}").json()
    assert refreshed["latestDecision"]["outcome"] == "denied"
