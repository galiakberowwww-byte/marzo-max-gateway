import hmac
import logging
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

from app.max_client import MaxClient
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rodcom.max.gateway")

app = FastAPI(title="RODCOM MAX Gateway", version="0.3.0")


def _max_client(settings: Settings) -> MaxClient:
    return MaxClient(
        settings.max_bot_token,
        settings.max_api_base_url,
        settings.max_ca_bundle,
    )


async def forward_to_rodcom(update: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.rodcom_webhook_url:
        raise HTTPException(status_code=503, detail="RODCOM webhook target is not configured")

    secret = settings.rodcom_webhook_secret or settings.max_webhook_secret
    headers = {"X-Max-Bot-Api-Secret": secret} if secret else {}

    try:
        async with httpx.AsyncClient(timeout=settings.rodcom_request_timeout_seconds) as client:
            response = await client.post(
                settings.rodcom_webhook_url,
                json=update,
                headers=headers,
            )
    except httpx.RequestError as exc:
        logger.exception("RODCOM webhook request failed")
        raise HTTPException(status_code=502, detail="RODCOM webhook is unavailable") from exc

    if response.status_code < 200 or response.status_code >= 300:
        logger.error("RODCOM webhook rejected update: status=%s", response.status_code)
        raise HTTPException(status_code=502, detail="RODCOM webhook rejected the update")


async def ensure_max_subscription() -> None:
    settings = get_settings()
    if not settings.public_webhook_url:
        logger.info("PUBLIC_WEBHOOK_URL is not configured; keeping existing MAX subscription")
        return

    desired = {"message_created", "bot_started", "message_callback"}
    client = _max_client(settings)
    current = await client.get_subscriptions()
    subscriptions = current.get("subscriptions") or []
    matching = next(
        (item for item in subscriptions if item.get("url") == settings.public_webhook_url),
        None,
    )
    current_types = set((matching or {}).get("update_types") or [])
    if matching is not None and desired.issubset(current_types):
        logger.info("MAX webhook subscription already includes Rodcom callbacks")
        return

    if matching is not None:
        await client.delete_subscription(settings.public_webhook_url)

    result = await client.create_subscription(
        settings.public_webhook_url,
        settings.max_webhook_secret,
        sorted(desired),
    )
    if result.get("success") is not True:
        raise RuntimeError(f"MAX webhook subscription failed: {result.get('message') or 'unknown error'}")
    logger.info("MAX webhook subscription configured for Rodcom")


@app.on_event("startup")
async def startup() -> None:
    await ensure_max_subscription()


@app.get("/health")
async def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "rodcom-max-gateway",
        "rodcomWebhookConfigured": bool(settings.rodcom_webhook_url),
        "rodcomBridgeConfigured": bool(settings.rodcom_bridge_secret),
    }


@app.get("/health/max-identity")
async def max_identity() -> dict[str, Any]:
    """Return only public MAX bot identity fields for operational wiring checks."""
    settings = get_settings()
    try:
        profile = await _max_client(settings).get_me()
    except Exception as exc:
        logger.warning("MAX bot identity check failed: %s", exc)
        raise HTTPException(status_code=502, detail="MAX bot identity is unavailable") from exc

    safe: dict[str, str | int] = {}
    for key in ("user_id", "username", "name", "first_name", "last_name"):
        value = profile.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            safe[key] = value
    return {"status": "ok", "bot": safe}


@app.post("/webhooks/max")
async def max_webhook(
    request: Request,
    x_max_bot_api_secret: str | None = Header(default=None),
) -> dict[str, bool]:
    settings = get_settings()
    if settings.max_webhook_secret and not hmac.compare_digest(
        x_max_bot_api_secret or "",
        settings.max_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    update = await request.json()
    logger.info("MAX update received for RODCOM: type=%s", update.get("update_type", "unknown"))
    await forward_to_rodcom(update)
    return {"ok": True}


@app.post("/internal/rodcom/send")
async def rodcom_send(
    request: Request,
    x_rodcom_bridge_secret: str | None = Header(default=None),
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.rodcom_bridge_secret:
        raise HTTPException(status_code=503, detail="RODCOM bridge is not configured")
    if not hmac.compare_digest(
        x_rodcom_bridge_secret or "",
        settings.rodcom_bridge_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid RODCOM bridge secret")

    payload = await request.json()
    mode = payload.get("mode")
    view = payload.get("view")
    if not isinstance(view, dict) or not isinstance(view.get("text"), str):
        raise HTTPException(status_code=422, detail="Invalid Rodcom view")

    client = _max_client(settings)
    if mode == "message":
        raw_user_id = payload.get("externalUserId")
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid MAX user id") from None
        await client.send_view(user_id, view)
    elif mode == "callback":
        callback_id = payload.get("callbackId")
        if not isinstance(callback_id, str) or not callback_id:
            raise HTTPException(status_code=422, detail="Invalid callback id")
        await client.answer_callback(callback_id, view)
    else:
        raise HTTPException(status_code=422, detail="Invalid bridge mode")

    return {"ok": True}
