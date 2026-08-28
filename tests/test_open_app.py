import base64
import os

os.environ.setdefault("MAX_BOT_TOKEN", "test-token")
os.environ.setdefault("MAX_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("RODCOM_BRIDGE_SECRET", "bridge-secret-1234567890")

from fastapi.testclient import TestClient

from app.main import app
from app.max_client import MaxApiError, MaxClient


client = TestClient(app)


def _qr(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def test_gateway_serializes_special_button_as_native_open_app() -> None:
    max_client = MaxClient(
        "token",
        "https://platform-api2.max.ru",
        web_app="id0278198770_bot",
    )
    body = max_client._view_body({
        "text": "Готово",
        "buttons": [[
            {"text": "Открыть в приложении", "payload": "__open_app__:collection_11111111-1111-1111-1111-111111111111"},
            {"text": "Назад", "payload": "rodcom:home"},
        ]],
    })
    buttons = body["attachments"][0]["payload"]["buttons"][0]
    assert buttons[0] == {
        "type": "open_app",
        "text": "Открыть в приложении",
        "web_app": "id0278198770_bot",
        "payload": "collection_11111111-1111-1111-1111-111111111111",
    }
    assert buttons[1]["type"] == "callback"


def test_gateway_fails_closed_when_open_app_username_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("MAX_BOT_USERNAME", raising=False)
    max_client = MaxClient("token", "https://platform-api2.max.ru")
    try:
        max_client._view_body({
            "text": "Готово",
            "buttons": [[{"text": "Открыть", "payload": "__open_app__:home"}]],
        })
    except MaxApiError as exc:
        assert "username" in str(exc)
    else:
        raise AssertionError("open_app without web_app must fail closed")


def test_invite_qr_accepts_startapp_invite_and_referral_targets() -> None:
    invite = "https://max.ru/id0278198770_bot?startapp=invite_abcdefghijklmnopqrstuvwxyz012345"
    referral = "https://max.ru/id0278198770_bot?startapp=ref_abcdefghijklmnopqrstuvwxyz012345"
    assert client.get("/public/qr/invite.png", params={"data": _qr(invite)}).status_code == 200
    assert client.get("/public/qr/invite.png", params={"data": _qr(referral)}).status_code == 200
