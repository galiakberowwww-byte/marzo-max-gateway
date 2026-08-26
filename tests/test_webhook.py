import base64
import os
from pathlib import Path

os.environ.setdefault("MAX_BOT_TOKEN", "test-token")
os.environ.setdefault("MAX_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault(
    "RODCOM_WEBHOOK_URL",
    "https://rodcom.example/api/v1/integrations/max/webhook",
)
os.environ.setdefault("RODCOM_BRIDGE_SECRET", "bridge-secret-1234567890")

from fastapi.testclient import TestClient

import app.main as main
from app.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def _encode_qr_target(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def test_health_identifies_rodcom_gateway() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "rodcom-max-gateway",
        "rodcomWebhookConfigured": True,
        "rodcomBridgeConfigured": True,
    }


def test_max_identity_health_returns_only_public_bot_fields(monkeypatch) -> None:
    class FakeMaxClient:
        async def get_me(self):
            return {
                "user_id": 12345,
                "username": "rodcom_test_bot",
                "name": "Родком",
                "token": "must-not-leak",
                "phone": "+79990000000",
                "nested": {"secret": "hidden"},
            }

    monkeypatch.setattr(main, "_max_client", lambda settings: FakeMaxClient())
    response = client.get("/health/max-identity")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "bot": {
            "user_id": 12345,
            "username": "rodcom_test_bot",
            "name": "Родком",
        },
    }


def test_invite_qr_is_generated_locally_as_png() -> None:
    target = "https://max.ru/id0278198770_bot?start=ri_abcdefghijklmnopqrstuvwxyz012345"
    response = client.get("/public/qr/invite.png", params={"data": _encode_qr_target(target)})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "no-store" in response.headers["cache-control"]
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_invite_qr_rejects_non_max_or_malformed_targets() -> None:
    wrong_host = _encode_qr_target("https://example.com/?start=ri_abcdefghijklmnopqrstuvwxyz012345")
    assert client.get("/public/qr/invite.png", params={"data": wrong_host}).status_code == 422
    assert client.get("/public/qr/invite.png", params={"data": "%%%"}).status_code == 422


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


def test_bridge_requires_rodcom_secret() -> None:
    response = client.post(
        "/internal/rodcom/send",
        headers={"X-Rodcom-Bridge-Secret": "wrong"},
        json={"mode": "message", "externalUserId": "42", "view": {"text": "Родком", "buttons": []}},
    )
    assert response.status_code == 401


def test_bridge_sends_message_and_callback_views(monkeypatch) -> None:
    calls = []

    class FakeMaxClient:
        async def send_view(self, user_id, view):
            calls.append(("message", user_id, view))
            return {"ok": True}

        async def answer_callback(self, callback_id, view):
            calls.append(("callback", callback_id, view))
            return {"ok": True}

    monkeypatch.setattr(main, "_max_client", lambda settings: FakeMaxClient())

    message_view = {
        "text": "Родком",
        "buttons": [[{"text": "Мои сборы", "payload": "rodcom:collections"}]],
    }
    response = client.post(
        "/internal/rodcom/send",
        headers={"X-Rodcom-Bridge-Secret": "bridge-secret-1234567890"},
        json={"mode": "message", "externalUserId": "42", "view": message_view},
    )
    assert response.status_code == 200

    callback_view = {"text": "Обновлено", "buttons": []}
    response = client.post(
        "/internal/rodcom/send",
        headers={"X-Rodcom-Bridge-Secret": "bridge-secret-1234567890"},
        json={"mode": "callback", "callbackId": "cb-1", "view": callback_view},
    )
    assert response.status_code == 200
    assert calls == [
        ("message", 42, message_view),
        ("callback", "cb-1", callback_view),
    ]


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
