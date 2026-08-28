import hmac
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.leads import LeadDraft, LeadStore, QUESTIONS
from app.max_client import MaxClient
from app.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marzo.max.gateway")

app = FastAPI(title="MARZO MAX Gateway", version="0.1.0")


@dataclass
class Dialog:
    draft: LeadDraft


dialogs: dict[str, Dialog] = {}


class ManualLead(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    direction: str
    source: str = "manager"
    customer_name: str | None = None
    brief: dict[str, str] = Field(default_factory=dict)


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
    message = update.get("message") or {}
    sender = message.get("sender") or update.get("user") or {}
    max_user_id = str(sender.get("user_id") or update.get("user_id") or "")
    if not max_user_id:
        return
    dialog = dialogs.get(max_user_id)

    async def send(text: str) -> None:
        await client.send_text(text, **{target_name: target_id})

    async def menu(text: str) -> None:
        await client.send_keyboard(text, [
            {"type": "message", "text": "Плитка / керамогранит"},
            {"type": "message", "text": "Дизайн"},
            {"type": "message", "text": "Ремонт / отделка"},
            {"type": "message", "text": "Комплектация / под ключ"},
        ], **{target_name: target_id})

    if update_type == "bot_started":
        payload = update.get("payload")
        source = payload[7:80] if isinstance(payload, str) and payload.startswith("source=") else "max_direct"
        dialogs[max_user_id] = Dialog(LeadDraft(max_user_id=max_user_id, source=source))
        await menu("Здравствуйте! MARZO поможет с плиткой, дизайном и ремонтом. С чего начнём?")
        return
    if update_type != "message_created":
        return

    body = message.get("body") or {}
    text = (body.get("text") or "").strip()
    directions = {"Плитка / керамогранит", "Дизайн", "Ремонт / отделка", "Комплектация / под ключ"}
    if text in directions:
        draft = LeadDraft(max_user_id=max_user_id, source=(dialog.draft.source if dialog else "max_direct"), direction=text)
        dialogs[max_user_id] = Dialog(draft)
        await send(QUESTIONS[0][1])
        return
    if dialog is None or dialog.draft.direction is None:
        await menu("Выберите направление, чтобы начать короткий бриф.")
        return
    if not text:
        return
    key, _ = QUESTIONS[dialog.draft.question_index]
    dialog.draft.answers[key] = text[:1000]
    dialog.draft.question_index += 1
    if dialog.draft.question_index < len(QUESTIONS):
        await send(QUESTIONS[dialog.draft.question_index][1])
        return
    lead_id = LeadStore(settings.marzo_database_path).save(dialog.draft, phone=None, customer_name=str(sender.get("name") or ""))
    dialogs.pop(max_user_id, None)
    await send(f"Спасибо! Заявка {lead_id} передана менеджеру MARZO. Он уточнит удобный способ связи.")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "marzo-max-gateway", "tenant": "marzo"}


@app.get("/miniapp/config")
async def mini_app_config() -> dict[str, str]:
    return {"tenant": "marzo", "integration": "interior-project"}


@app.post("/internal/leads/manual")
async def create_manual_lead(payload: ManualLead, x_marzo_admin_token: str | None = Header(default=None)) -> dict[str, str]:
    settings = get_settings()
    if not settings.marzo_admin_token or not hmac.compare_digest(x_marzo_admin_token or "", settings.marzo_admin_token):
        raise HTTPException(status_code=401, detail="Invalid manager token")
    lead_id = LeadStore(settings.marzo_database_path).add_manual(**payload.model_dump())
    return {"id": lead_id, "status": "qualified", "interior_project": "pending"}


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
