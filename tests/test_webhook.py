import os
from pathlib import Path

os.environ.setdefault("MAX_BOT_TOKEN", "test-token")
os.environ.setdefault("MAX_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault(
    "RODCOM_WEBHOOK_URL",
    "https://rodcom.example/api/v1/integrations/max/webhook",
)

from fastapi.testclient import TestClient

import app.main as main
from app.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_health_identifies_rodcom_gateway() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "rodcom-max-gateway",
        "rodcomWebhookConfigured": True,
    }


def test_rejects_invalid_max_secret() -> None:
    response = client.post(
        "/webhooks/max",
        headers={"X-Max-Bot-Api-Secret": "wrong"},
        json={"update_type": "bot_started", "user": {"user_id": 42}},
    )
    assert response.status_code == 401


def test_forwards_start_and_core_commands_unchanged(monkeypatch) -> None:
    forwarded = []

    async def fake_forward(update):
        forwarded.append(update)

    monkeypatch.setattr(main, "forward_to_rodcom", fake_forward)

    updates = [
        {"update_type": "bot_started", "user": {"user_id": 42}},
        {
            "update_type": "message_created",
            "message": {"sender": {"user_id": 42}, "body": {"text": "/start"}},
        },
        {
            "update_type": "message_created",
            "message": {"sender": {"user_id": 42}, "body": {"text": "/communities"}},
        },
        {
            "update_type": "message_created",
            "message": {"sender": {"user_id": 42}, "body": {"text": "/collections"}},
        },
        {
            "update_type": "message_created",
            "message": {"sender": {"user_id": 42}, "body": {"text": "/help"}},
        },
        {
            "update_type": "message_callback",
            "callback": {
                "callback_id": "cb-1",
                "payload": "rodcom:communities",
                "user": {"user_id": 42},
            },
        },
    ]

    for update in updates:
        response = client.post(
            "/webhooks/max",
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
            json=update,
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    assert forwarded == updates


def test_gateway_has_no_product_router_or_legacy_copy() -> None:
    source = Path(main.__file__).read_text(encoding="utf-8").lower()
    assert "marzo" not in source
    assert "квалификац" not in source
    assert "плитк" not in source
    assert "ремонт" not in source


def test_subscription_includes_callback_updates() -> None:
    script = (ROOT / "scripts" / "register_webhook.py").read_text(encoding="utf-8")
    assert '"message_created"' in script
    assert '"message_callback"' in script
    assert '"bot_started"' in script
