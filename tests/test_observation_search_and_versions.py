import datetime as dt

from fastapi.testclient import TestClient

from app.main import app


def _iso(ts: dt.datetime) -> str:
    return ts.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def test_observation_latest_search_and_entered_in_error_filter():
    client = TestClient(app)

    patient = client.post(
        "/fhir/Patient",
        json={
            "resourceType": "Patient",
            "identifier": [{"system": "urn:mrn", "value": "MRN-OBS-1"}],
            "name": [{"family": "Obs", "given": ["Case"]}],
        },
        headers={"X-Correlation-Id": "t-obs-patient"},
    ).json()

    code = {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic BP"}]}

    t1 = dt.datetime(2026, 1, 1, 10, 0, tzinfo=dt.timezone.utc)
    o1 = client.post(
        "/fhir/Observation",
        json={
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"code": "vital-signs"}]}],
            "code": code,
            "subject": {"reference": f"Patient/{patient['id']}"},
            "effectiveDateTime": _iso(t1),
            "valueQuantity": {"value": 120, "unit": "mmHg"},
        },
        headers={"X-Correlation-Id": "t-obs-1"},
    )
    assert o1.status_code == 200

    t2 = dt.datetime(2026, 1, 1, 11, 0, tzinfo=dt.timezone.utc)
    o2 = client.post(
        "/fhir/Observation",
        json={
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"code": "vital-signs"}]}],
            "code": code,
            "subject": {"reference": f"Patient/{patient['id']}"},
            "effectiveDateTime": _iso(t2),
            "valueQuantity": {"value": 125, "unit": "mmHg"},
        },
        headers={"X-Correlation-Id": "t-obs-2"},
    )
    assert o2.status_code == 200
    o2_id = o2.json()["id"]

    entered = client.post(
        "/fhir/Observation",
        json={
            "resourceType": "Observation",
            "status": "entered-in-error",
            "category": [{"coding": [{"code": "vital-signs"}]}],
            "code": code,
            "subject": {"reference": f"Patient/{patient['id']}"},
            "effectiveDateTime": _iso(dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.timezone.utc)),
            "valueQuantity": {"value": 999, "unit": "mmHg"},
        },
        headers={"X-Correlation-Id": "t-obs-eie"},
    )
    assert entered.status_code == 200
    entered_id = entered.json()["id"]

    latest = client.get(
        f"/fhir/Observation?patient={patient['id']}&code=http://loinc.org|8480-6&_sort=-date&_count=1"
    )
    assert latest.status_code == 200
    ids = [e["resource"]["id"] for e in latest.json().get("entry", [])]
    assert ids == [o2_id]

    # entered-in-error excluded by default
    all_default = client.get(f"/fhir/Observation?patient={patient['id']}&code=http://loinc.org|8480-6&_count=50")
    default_ids = [e["resource"]["id"] for e in all_default.json().get("entry", [])]
    assert entered_id not in default_ids

    # explicitly requested
    eie = client.get(
        f"/fhir/Observation?patient={patient['id']}&code=http://loinc.org|8480-6&status=entered-in-error&_count=50"
    )
    eie_ids = [e["resource"]["id"] for e in eie.json().get("entry", [])]
    assert entered_id in eie_ids


def test_observation_history_lite():
    client = TestClient(app)
    patient = client.post(
        "/fhir/Patient",
        json={"resourceType": "Patient", "name": [{"family": "Hist", "given": ["O"]}]},
        headers={"X-Correlation-Id": "t-hist-p"},
    ).json()
    created = client.post(
        "/fhir/Observation",
        json={
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"code": "laboratory"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": "2345-7", "display": "Glucose"}]},
            "subject": {"reference": f"Patient/{patient['id']}"},
            "effectiveDateTime": "2026-01-01T10:00:00Z",
            "valueQuantity": {"value": 90, "unit": "mg/dL"},
        },
        headers={"X-Correlation-Id": "t-hist-o1"},
    ).json()
    oid = created["id"]
    updated = client.put(
        f"/fhir/Observation/{oid}",
        json={
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"code": "laboratory"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": "2345-7", "display": "Glucose"}]},
            "subject": {"reference": f"Patient/{patient['id']}"},
            "effectiveDateTime": "2026-01-01T10:00:00Z",
            "valueQuantity": {"value": 92, "unit": "mg/dL"},
        },
        headers={"X-Correlation-Id": "t-hist-o2"},
    )
    assert updated.status_code == 200
    assert updated.json()["meta"]["versionId"] == "2"

    hist = client.get(f"/fhir/Observation/{oid}/_history")
    assert hist.status_code == 200
    assert hist.json()["type"] == "history"
    assert hist.json()["total"] >= 2

