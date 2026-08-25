import hmac
import logging
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.max_client import MaxClient
from app.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marzo.max.gateway")

app = FastAPI(title="MARZO MAX Gateway", version="0.1.0")


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _message_target(update: dict[str, Any]) -> tuple[str, int] | None:
    message = update.get("message") or {}
    sender = message.get("sender") or update.get("user") or {}
    recipient = message.get("recipient") or {}

    if sender.get("is_bot") is True:
        return None

    user_id = _as_int(sender.get("user_id") or update.get("user_id"))
    chat_id = _as_int(
        update.get("chat_id")
        or recipient.get("chat_id")
        or message.get("chat_id")
    )

    recipient_type = recipient.get("chat_type") or recipient.get("type")
    if recipient_type == "dialog" and user_id is not None:
        return ("user_id", user_id)
    if chat_id is not None:
        return ("chat_id", chat_id)
    if user_id is not None:
        return ("user_id", user_id)
    return None


async def process_update(update: dict[str, Any]) -> None:
    settings = get_settings()
    client = MaxClient(
        settings.max_bot_token,
        settings.max_api_base_url,
        settings.max_ca_bundle,
    )
    update_type = update.get("update_type", "unknown")
    logger.info("MAX update received: type=%s", update_type)

    target = _message_target(update)
    if target is None:
        return

    target_name, target_id = target
    if update_type == "bot_started":
        reply = (
            "Здравствуйте! Я бот MARZO. Помогу с плиткой, дизайном и ремонтом. "
            "Напишите, что вам требуется."
        )
    elif update_type == "message_created":
        message = update.get("message") or {}
        body = message.get("body") or {}
        text = (body.get("text") or "").strip()
        if not text:
            reply = "Файл получил. Скоро добавим его обработку в сценарий MARZO."
        else:
            reply = (
                "Спасибо, сообщение получил. Это первый тест MARZO Gateway. "
                "Следующим шагом подключим сценарий квалификации лида."
            )
    else:
        return

    await client.send_text(reply, **{target_name: target_id})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "marzo-max-gateway"}


@app.post("/webhooks/max")
async def max_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_max_bot_api_secret: str | None = Header(default=None),
) -> dict[str, bool]:
    settings = get_settings()
    if settings.max_webhook_secret and not hmac.compare_digest(
        x_max_bot_api_secret or "",
        settings.max_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    update = await request.json()
    background_tasks.add_task(process_update, update)
    return {"ok": True}
