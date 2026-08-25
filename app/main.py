import hmac
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.max_client import MaxClient
from app.contact_verification import is_verified_max_contact, phone_from_vcf
from app.rodcom_client import RodcomClient
from app.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marzo.max.gateway")

app = FastAPI(title="MARZO MAX Gateway", version="0.1.0")


@dataclass
class Dialog:
    state: str = "new"
    parent_id: str | None = None
    community_id: str | None = None
    invitation_token: str | None = None


dialogs: dict[str, Dialog] = {}


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
    dialog = dialogs.setdefault(max_user_id, Dialog())
    rodcom = (
        RodcomClient(settings.rodcom_api_base_url, settings.rodcom_gateway_token)
        if settings.rodcom_api_base_url and settings.rodcom_gateway_token else None
    )

    async def send(text: str) -> None:
        await client.send_text(text, **{target_name: target_id})

    async def ask_contact(text: str) -> None:
        await client.send_keyboard(
            text, [{"type": "request_contact", "text": "Подтвердить номер"}], **{target_name: target_id}
        )

    async def menu(text: str) -> None:
        await client.send_keyboard(text, [
            {"type": "message", "text": "Создать комьюнити"},
            {"type": "message", "text": "Войти по приглашению"},
            {"type": "message", "text": "Добавить ребёнка"},
            {"type": "message", "text": "Заявки на вступление"},
        ], **{target_name: target_id})

    if update_type == "bot_started":
        payload = update.get("payload")
        dialog.invitation_token = payload[2:] if isinstance(payload, str) and payload.startswith("i_") else None
        dialog.state = "awaiting_contact"
        await ask_contact("Здравствуйте! Чтобы зарегистрироваться в RODCOM, подтвердите номер телефона из MAX.")
        return
    if update_type != "message_created":
        return

    body = message.get("body") or {}
    text = (body.get("text") or "").strip()
    contact = next(
        (item.get("payload") or {} for item in (message.get("attachments") or []) if item.get("type") == "contact"), None
    )
    if contact:
        vcf_info, contact_hash = contact.get("vcf_info"), contact.get("hash")
        phone = phone_from_vcf(vcf_info) if isinstance(vcf_info, str) else None
        if not isinstance(contact_hash, str) or not phone or not is_verified_max_contact(
            token=settings.max_bot_token, vcf_info=vcf_info, received_hash=contact_hash
        ):
            await ask_contact("Не удалось подтвердить номер. Нажмите кнопку «Подтвердить номер».")
            return
        if rodcom is None:
            await send("RODCOM временно недоступен. Попробуйте позже.")
            return
        profile = await rodcom.register_parent(
            max_user_id=max_user_id, phone=phone, display_name=str(sender.get("name") or "Родитель"),
            event_id=str(update.get("timestamp") or message.get("id") or f"contact:{max_user_id}"),
        )
        dialog.parent_id = profile["id"]
        if dialog.invitation_token:
            accepted = await rodcom.accept_invitation(actor_user_id=dialog.parent_id, token=dialog.invitation_token)
            dialog.community_id, dialog.state = accepted["communityId"], "awaiting_child"
            await send("Вы зарегистрированы. Напишите имя ребёнка, которого хотите добавить в это комьюнити.")
            return
        dialog.state = "ready"
        await menu("Номер подтверждён. Выберите действие.")
        return
    if not dialog.parent_id:
        await ask_contact("Сначала подтвердите номер телефона.")
        return
    if text == "Создать комьюнити":
        dialog.state = "awaiting_community_name"
        await send("Напишите название комьюнити, например «4А, школа № 12».")
        return
    if dialog.state == "awaiting_community_name" and text:
        if rodcom is None:
            await send("RODCOM временно недоступен. Попробуйте позже.")
            return
        community = await rodcom.create_community(actor_user_id=dialog.parent_id, name=text)
        invitation = await rodcom.create_invitation(actor_user_id=dialog.parent_id, community_id=community["id"])
        token = parse_qs(urlparse(invitation["inviteUrl"]).query)["token"][0]
        dialog.community_id, dialog.state = community["id"], "ready"
        await send(f"Комьюнити создано. Вы организатор. Отправьте родителям ссылку:\nhttps://max.ru/{settings.max_bot_username}?start=i_{token}")
        return
    if text == "Добавить ребёнка" and dialog.community_id:
        dialog.state = "awaiting_child"
        await send("Напишите имя ребёнка.")
        return
    if dialog.state == "awaiting_child" and text:
        if rodcom is None or not dialog.community_id:
            await send("Не найдено комьюнити для заявки. Откройте приглашение ещё раз.")
            return
        request = await rodcom.create_membership_request(
            actor_user_id=dialog.parent_id, community_id=dialog.community_id, child_display_name=text
        )
        dialog.state = "ready"
        await send(f"Заявка создана и ждёт решения организатора. Номер заявки: {request['id']}")
        return
    await menu("Выберите действие.")


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
