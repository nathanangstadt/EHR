from fastapi.testclient import TestClient

from app.main import app


def test_patient_create_read_search_idempotent():
    client = TestClient(app)

    mrn = "MRN-TEST-1001"
    payload = {
        "resourceType": "Patient",
        "identifier": [{"system": "urn:mrn", "value": mrn}],
        "name": [{"family": "Tester", "given": ["Pat"]}],
        "birthDate": "1991-01-01",
    }

    r1 = client.post("/fhir/Patient", json=payload, headers={"X-Correlation-Id": "t-patient-1"})
    assert r1.status_code == 200
    p1 = r1.json()
    assert p1["id"]
    assert p1["meta"]["versionId"] == "1"

    r2 = client.post("/fhir/Patient", json=payload, headers={"X-Correlation-Id": "t-patient-1"})
    assert r2.status_code == 200
    p2 = r2.json()
    assert p2["id"] == p1["id"]

    r3 = client.get(f"/fhir/Patient/{p1['id']}")
    assert r3.status_code == 200
    got = r3.json()
    assert got["id"] == p1["id"]

    r4 = client.get(f"/fhir/Patient?identifier=urn:mrn|{mrn}")
    assert r4.status_code == 200
    bundle = r4.json()
    ids = [e["resource"]["id"] for e in bundle.get("entry", [])]
    assert p1["id"] in ids

