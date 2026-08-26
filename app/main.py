import hmac
import logging
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

from app.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rodcom.max.gateway")

app = FastAPI(title="RODCOM MAX Gateway", version="0.2.0")


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


@app.get("/health")
async def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "rodcom-max-gateway",
        "rodcomWebhookConfigured": bool(settings.rodcom_webhook_url),
    }


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
