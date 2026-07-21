from fastapi.testclient import TestClient

from cbs.main import app

client = TestClient(app)


def test_plan_alert_count_today() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "How many ALERT events happened today?",
            "mode": "events",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["strategy"] == "neo4j_direct"
    assert body["intent_id"] == "planned_graph"
    assert body["planned"][0]["label"] == "count"
    assert "SecurityEvent" in body["planned"][0]["cypher"]
    assert body["meta"]["cypher_class"] == "deterministic"
    assert body["meta"]["builder_version"]
    assert "count" in body["meta"]["plan_labels"]


def test_plan_unmatched() -> None:
    response = client.post(
        "/v1/plan",
        json={"question": "zzzz not a graph question at all", "mode": "events"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is False
    assert body["planned"] == []
    assert body["intent_id"] is None


def test_plan_lob_scoped_embeds_owning_lob() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "How many instruction policy denials happened this week?",
            "mode": "events",
            "options": {"lob_scoped": True, "allowed_lobs": ["FX"]},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    cypher = body["planned"][0]["cypher"]
    assert "owning_lob" in cypher
    assert "FX" in cypher


def test_plan_payment_status_by_id() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "What is the status of payment 20260720-FICC-P-1?",
            "mode": "payments",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["intent_id"] == "payment.status_by_id"
    assert body["planned"][0]["label"] == "payment_detail"
    assert "20260720-FICC-P-1" in body["planned"][0]["cypher"]
    assert body["meta"]["source"] == "entity_detail"


def test_plan_instruction_status_by_id() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "What is the status of instruction 20260720-FICC-I-1?",
            "mode": "instructions",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["intent_id"] == "instruction.status_by_id"
    assert body["planned"][0]["label"] == "instruction_detail"


def test_plan_payment_creator_by_id() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "Who created payment 20260720-FICC-P-1?",
            "mode": "payments",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["intent_id"] == "payment.creator_by_id"
    assert body["planned"][0]["label"] == "payment_detail"


def test_plan_payment_creator_and_approver_by_id() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "Who created payment 20260720-FICC-P-1 and who approved it?",
            "mode": "payments",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["intent_id"] == "payment.creator_and_approver_by_id"
    assert body["planned"][0]["label"] == "payment_detail"
    assert body["meta"]["source"] == "entity_detail"


def test_plan_instruction_creator_and_approver_by_id() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "Who created instruction 20260720-FICC-I-1 and who approved it?",
            "mode": "instructions",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["intent_id"] == "instruction.creator_and_approver_by_id"
    assert body["planned"][0]["label"] == "instruction_detail"


def test_plan_entity_detail_any_mode() -> None:
    """ID-based status works from Events (default UI mode), not only payments."""
    response = client.post(
        "/v1/plan",
        json={
            "question": "What is the status of 20260720-FICC-P-19?",
            "mode": "events",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["intent_id"] == "payment.status_by_id"
    assert body["planned"][0]["label"] == "payment_detail"
    assert "20260720-FICC-P-19" in body["planned"][0]["cypher"]


def test_plan_payment_approver_fallback_mode_all() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "Who approved payment 20260720-FICC-P-1 and why?",
            "mode": "all",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["intent_id"] == "payment.approver_by_id"
    assert body["planned"][0]["label"] == "payment_approval_lookup"


def test_plan_payment_approver_bare_id_any_mode() -> None:
    """Who approved <P-id>? (no payment noun) works from Events."""
    response = client.post(
        "/v1/plan",
        json={
            "question": "Who approved 20260720-FICC-P-19?",
            "mode": "events",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    # Heuristic plan_graph hits first when bare payment id is present; entity_plan
    # fallback uses payment.approver_by_id when mode would miss (e.g. mode=all).
    assert body["intent_id"] in {"planned_graph", "payment.approver_by_id"}
    assert body["planned"][0]["label"] == "payment_approval_lookup"
    assert "Payment" in body["planned"][0]["cypher"]
    assert "has_approval" in body["planned"][0]["cypher"]
    assert "approver_user_id IS NOT NULL" in body["planned"][0]["cypher"]
    assert f"PaymentVersion {{payment_id: '20260720-FICC-P-19'}}" in body["planned"][0][
        "cypher"
    ]


def test_plan_payment_approver_events_via_heuristic() -> None:
    response = client.post(
        "/v1/plan",
        json={
            "question": "Who approved payment 20260720-FICC-P-1 and why?",
            "mode": "events",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["intent_id"] == "planned_graph"
    assert body["planned"][0]["label"] == "payment_approval_lookup"
