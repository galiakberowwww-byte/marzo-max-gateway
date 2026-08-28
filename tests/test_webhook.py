import os
import tempfile

os.environ.setdefault("MAX_BOT_TOKEN", "test-token")
os.environ["MARZO_DATABASE_PATH"] = tempfile.mktemp(suffix=".sqlite3")

from fastapi.testclient import TestClient

from app.main import app, _message_target
from app.settings import get_settings


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["tenant"] == "marzo"


def test_webhook_acknowledges_update() -> None:
    response = client.post(
        "/webhooks/max",
        headers={"X-Max-Bot-Api-Secret": get_settings().max_webhook_secret},
        json={"update_type": "unknown"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_extracts_dialog_user() -> None:
    update = {
        "message": {
            "sender": {"user_id": 42},
            "recipient": {"chat_type": "dialog", "chat_id": 99},
        }
    }
    assert _message_target(update) == ("user_id", 42)


def test_ignores_bot_messages() -> None:
    update = {"message": {"sender": {"user_id": 42, "is_bot": True}}}
    assert _message_target(update) is None
