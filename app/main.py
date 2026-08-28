import base64
import hmac
import io
import logging
import os
import re
from typing import Any

import httpx
import qrcode
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response

from app.max_client import MaxClient
from app.max_webapp import MaxWebAppValidationError, validate_max_webapp_init_data
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rodcom.max.gateway")

app = FastAPI(title="RODCOM MAX Gateway", version="0.4.0")

_INVITE_TARGET = re.compile(
    r"^https://max\.ru/[A-Za-z0-9_]+\?(?:start=ri_[A-Za-z0-9_-]{16,120}|startapp=(?:invite|ref)_[A-Za-z0-9_-]{16,120})$"
)


def _max_client(settings: Settings) -> MaxClient:
    return MaxClient(
        settings.max_bot_token,
        settings.max_api_base_url,
        settings.max_ca_bundle,
    )


def _public_bot_identity(profile: dict[str, Any]) -> dict[str, str | int]:
    safe: dict[str, str | int] = {}
    for key in ("user_id", "username", "name", "first_name", "last_name"):
        value = profile.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            safe[key] = value
    return safe


def _decode_invite_qr_target(data: str) -> str:
    if not data or len(data) > 4096:
        raise HTTPException(status_code=422, detail="Invalid invite QR payload")
    try:
        padded = data + "=" * (-len(data) % 4)
        raw = base64.b64decode(padded, altchars=b"-_", validate=True)
        target = raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid invite QR payload") from exc
    if not _INVITE_TARGET.fullmatch(target):
        raise HTTPException(status_code=422, detail="Invalid invite QR target")
    return target


def _require_rodcom_bridge(settings: Settings, received: str | None) -> None:
    if not settings.rodcom_bridge_secret:
        raise HTTPException(status_code=503, detail="RODCOM bridge is not configured")
    if not hmac.compare_digest(received or "", settings.rodcom_bridge_secret):
        raise HTTPException(status_code=401, detail="Invalid RODCOM bridge secret")


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


async def log_max_identity() -> None:
    settings = get_settings()
    try:
        profile = await _max_client(settings).get_me()
    except Exception as exc:
        logger.warning("MAX bot identity startup check failed: %s", exc)
        return
    logger.info("MAX bot identity: %s", _public_bot_identity(profile))


@app.on_event("startup")
async def startup() -> None:
    await ensure_max_subscription()
    await log_max_identity()
    if os.getenv("RODCOM_FORWARD_SMOKE") == "1":
        await forward_to_rodcom({"update_type": "timeweb_smoke"})
        logger.info("RODCOM forward smoke passed")


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
    return {"status": "ok", "bot": _public_bot_identity(profile)}


@app.get("/public/qr/invite.png")
async def invite_qr(data: str) -> Response:
    """Render an invite/referral QR locally; opaque tokens never leave Rodcom infrastructure."""
    target = _decode_invite_qr_target(data)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(target)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return Response(
        content=output.getvalue(),
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "X-Content-Type-Options": "nosniff",
        },
    )


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


@app.post("/internal/rodcom/verify-miniapp")
async def verify_rodcom_miniapp(
    request: Request,
    x_rodcom_bridge_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Verify MAX WebApp initData without exposing the bot token to Rodcom."""
    settings = get_settings()
    _require_rodcom_bridge(settings, x_rodcom_bridge_secret)
    payload = await request.json()
    init_data = payload.get("initData") if isinstance(payload, dict) else None
    if not isinstance(init_data, str) or not init_data or len(init_data) > 16384:
        raise HTTPException(status_code=422, detail="Invalid MAX initData payload")
    try:
        verified = validate_max_webapp_init_data(init_data, settings.max_bot_token)
    except MaxWebAppValidationError as exc:
        detail = "MAX Mini App session expired" if str(exc) == "expired_init_data" else "Invalid MAX initData"
        raise HTTPException(status_code=401, detail=detail) from exc
    return {
        "ok": True,
        "externalUserId": verified.external_user_id,
        "authDate": verified.auth_date,
        "startParam": verified.start_param,
        "firstName": verified.first_name,
        "lastName": verified.last_name,
    }


@app.post("/internal/rodcom/send")
async def rodcom_send(
    request: Request,
    x_rodcom_bridge_secret: str | None = Header(default=None),
) -> dict[str, bool]:
    settings = get_settings()
    _require_rodcom_bridge(settings, x_rodcom_bridge_secret)

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
