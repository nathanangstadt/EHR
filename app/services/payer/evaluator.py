from __future__ import annotations

import datetime as dt
from typing import Any


def _contains(text: str, needle: str) -> bool:
    return needle.lower() in (text or "").lower()


def evaluate_rules(
    *,
    rules: dict[str, Any],
    now: dt.datetime,
    service_system: str | None,
    service_code: str | None,
    service_text: str | None,
    service_priority: str | None,
    diagnosis_system: str | None,
    diagnosis_code: str | None,
    diagnosis_text: str | None,
    preauth_priority: str | None,
    supporting_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Minimal payer rules engine (POC):
    - rule match: service CPT in list AND diagnosis keyword match
    - requirements: requiredDocuments list, each has code and maxAgeDays
    - outcomes: if missing docs -> pending-info with requestedAdditionalInfo, else approve/deny per rule
    """
    schema = str(rules.get("schemaVersion") or "1")
    if schema != "1":
        raise ValueError(f"Unsupported payer rules schemaVersion {schema}")

    policies = rules.get("policies") or []
    for policy in policies:
        services = policy.get("services") or {}
        codes = services.get("codes") or []
        cpt_list = services.get("cpt") or []
        matched_service = True
        if codes:
            matched_service = False
            for c in codes:
                if not isinstance(c, dict):
                    continue
                if (c.get("system") or "") == (service_system or "") and (c.get("code") or "") == (service_code or ""):
                    matched_service = True
                    break
        elif cpt_list:
            matched_service = False
            # Back-compat: match CPT list against service_code when system looks like CPT.
            if service_code and service_code in cpt_list:
                matched_service = True
            elif service_text:
                st = (service_text or "").lower()
                if any(str(c).lower() in st for c in cpt_list):
                    matched_service = True
        if not matched_service:
            continue

        priority_in = services.get("priorityIn") or policy.get("priorityIn")
        if priority_in:
            if preauth_priority and preauth_priority not in priority_in:
                continue
            if not preauth_priority and service_priority and service_priority not in priority_in:
                continue

        diagnosis = policy.get("diagnosis") or {}
        diag_codes = diagnosis.get("codes") or []
        if diag_codes:
            ok = False
            for c in diag_codes:
                if not isinstance(c, dict):
                    continue
                if (c.get("system") or "") == (diagnosis_system or "") and (c.get("code") or "") == (diagnosis_code or ""):
                    ok = True
                    break
            if not ok:
                continue
        diag_any = diagnosis.get("anyContains") or []
        if diag_any and not any(_contains(diagnosis_text or "", k) for k in diag_any):
            continue

        required_docs = policy.get("requiredDocuments") or []
        missing: list[dict[str, Any]] = []
        for rd in required_docs:
            code = str(rd.get("code") or "")
            max_age = int(rd.get("maxAgeDays") or 3650)
            found = False
            for d in supporting_documents:
                if str(d.get("code")).lower() != code.lower():
                    continue
                doc_time = d.get("dateTime")
                if isinstance(doc_time, str) and doc_time:
                    try:
                        t = dt.datetime.fromisoformat(doc_time.replace("Z", "+00:00"))
                    except Exception:
                        t = now
                else:
                    t = now
                if now - t <= dt.timedelta(days=max_age):
                    found = True
                    break
            if not found:
                missing.append(
                    {
                        "type": "document",
                        "code": code,
                        "display": rd.get("display") or code,
                        "maxAgeDays": max_age,
                    }
                )

        if missing:
            return {
                "outcome": "pending-info",
                "reasonCodes": policy.get("pendingInfoReasonCodes")
                or [{"code": "missing-documentation", "display": "Missing required documentation"}],
                "rationale": policy.get("pendingInfoRationale") or "Additional documentation required.",
                "requestedAdditionalInfo": missing,
            }

        outcome = policy.get("outcome") or "denied"
        reason = policy.get("reasonCodes") or [{"code": "policy", "display": "Policy determination"}]
        rationale = policy.get("rationale") or "Determined by policy."
        return {
            "outcome": outcome,
            "reasonCodes": reason,
            "rationale": rationale,
            "requestedAdditionalInfo": [],
        }

    # Default deny.
    return {
        "outcome": "denied",
        "reasonCodes": [{"code": "no-policy-match", "display": "No matching policy rule"}],
        "rationale": "No matching policy for request.",
        "requestedAdditionalInfo": [],
    }
