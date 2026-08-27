import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

os.environ.setdefault("MAX_BOT_TOKEN", "test-token")
os.environ.setdefault("MAX_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("RODCOM_BRIDGE_SECRET", "bridge-secret-1234567890")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
TOKEN = "test-token"
BRIDGE = "bridge-secret-1234567890"


def _signed_init_data(*, auth_date: int, user_id: int = 12345) -> str:
    values = {
        "auth_date": str(auth_date),
        "query_id": "q-1",
        "start_param": "collection_11111111-1111-1111-1111-111111111111",
        "user": json.dumps(
            {"id": user_id, "first_name": "Иван", "last_name": "Петров"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**values, "hash": signature})


def test_verify_miniapp_requires_bridge_secret() -> None:
    response = client.post(
        "/internal/rodcom/verify-miniapp",
        json={"initData": _signed_init_data(auth_date=int(time.time()))},
    )
    assert response.status_code == 401


def test_verify_miniapp_returns_only_validated_identity() -> None:
    now = int(time.time())
    response = client.post(
        "/internal/rodcom/verify-miniapp",
        headers={"X-Rodcom-Bridge-Secret": BRIDGE},
        json={"initData": _signed_init_data(auth_date=now)},
    )
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "externalUserId": "12345",
        "authDate": now,
        "startParam": "collection_11111111-1111-1111-1111-111111111111",
        "firstName": "Иван",
        "lastName": "Петров",
    }


def test_verify_miniapp_rejects_tampering() -> None:
    data = _signed_init_data(auth_date=int(time.time())).replace("12345", "12346")
    response = client.post(
        "/internal/rodcom/verify-miniapp",
        headers={"X-Rodcom-Bridge-Secret": BRIDGE},
        json={"initData": data},
    )
    assert response.status_code == 401


def test_verify_miniapp_rejects_expired_session() -> None:
    response = client.post(
        "/internal/rodcom/verify-miniapp",
        headers={"X-Rodcom-Bridge-Secret": BRIDGE},
        json={"initData": _signed_init_data(auth_date=int(time.time()) - 3700)},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
