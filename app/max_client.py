import ssl
from pathlib import Path
from typing import Any

import httpx


class MaxApiError(RuntimeError):
    pass


class MaxClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        ca_bundle: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": token}
        self._verify: bool | ssl.SSLContext = True
        if ca_bundle:
            ca_path = Path(ca_bundle).expanduser().resolve()
            self._verify = ssl.create_default_context(cafile=str(ca_path))

    @staticmethod
    def _safe_media_attachments(view: dict[str, Any]) -> list[dict[str, Any]]:
        raw_items = view.get("mediaAttachments") or []
        if not isinstance(raw_items, list):
            return []

        result: list[dict[str, Any]] = []
        for raw in raw_items[:4]:
            if not isinstance(raw, dict):
                continue
            attachment_type = raw.get("type")
            payload = raw.get("payload")
            if not isinstance(payload, dict):
                continue

            if attachment_type == "image":
                token = payload.get("token")
                url = payload.get("url")
                if isinstance(token, str) and token:
                    result.append({"type": "image", "payload": {"token": token}})
                elif isinstance(url, str) and url:
                    result.append({"type": "image", "payload": {"url": url}})
            elif attachment_type == "file":
                token = payload.get("token")
                if isinstance(token, str) and token:
                    result.append({"type": "file", "payload": {"token": token}})

        return result

    @staticmethod
    def _keyboard_button(button: dict[str, Any]) -> dict[str, Any]:
        text = str(button.get("text") or "")[:128]
        payload = button.get("payload")
        if isinstance(payload, str) and payload.startswith("__open_app__:"):
            start_payload = payload.removeprefix("__open_app__:")[:512]
            result: dict[str, Any] = {"type": "open_app", "text": text}
            if start_payload:
                result["payload"] = start_payload
            return result
        return {
            "type": "callback",
            "text": text,
            "payload": str(payload or ""),
        }

    def _view_body(self, view: dict[str, Any]) -> dict[str, Any]:
        buttons = view.get("buttons") or []
        attachments = self._safe_media_attachments(view)
        if buttons:
            attachments.append(
                {
                    "type": "inline_keyboard",
                    "payload": {
                        "buttons": [
                            [self._keyboard_button(button) for button in row]
                            for row in buttons
                            if isinstance(row, list)
                        ]
                    },
                }
            )
        return {"text": str(view.get("text") or ""), "attachments": attachments}

    async def get_me(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20, verify=self._verify) as client:
            response = await client.get(
                f"{self._base_url}/me",
                headers=self._headers,
            )
        if response.is_error:
            raise MaxApiError(f"MAX API returned HTTP {response.status_code}")
        return response.json()

    async def send_text(
        self,
        text: str,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        if (user_id is None) == (chat_id is None):
            raise ValueError("Specify exactly one of user_id or chat_id")

        params = {"user_id": user_id} if user_id is not None else {"chat_id": chat_id}
        async with httpx.AsyncClient(timeout=15, verify=self._verify) as client:
            response = await client.post(
                f"{self._base_url}/messages",
                headers=self._headers,
                params=params,
                json={"text": text, "notify": True},
            )
        if response.is_error:
            raise MaxApiError(f"MAX API returned HTTP {response.status_code}")
        return response.json()

    async def send_view(self, user_id: int, view: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15, verify=self._verify) as client:
            response = await client.post(
                f"{self._base_url}/messages",
                headers=self._headers,
                params={"user_id": user_id},
                json=self._view_body(view),
            )
        if response.is_error:
            raise MaxApiError(f"MAX API returned HTTP {response.status_code}")
        return response.json()

    async def answer_callback(self, callback_id: str, view: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15, verify=self._verify) as client:
            response = await client.post(
                f"{self._base_url}/answers",
                headers=self._headers,
                params={"callback_id": callback_id},
                json={"message": self._view_body(view)},
            )
        if response.is_error:
            raise MaxApiError(f"MAX API returned HTTP {response.status_code}")
        return response.json()

    async def create_subscription(
        self,
        webhook_url: str,
        secret: str,
        update_types: list[str],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "url": webhook_url,
            "update_types": update_types,
        }
        if secret:
            payload["secret"] = secret

        async with httpx.AsyncClient(timeout=20, verify=self._verify) as client:
            response = await client.post(
                f"{self._base_url}/subscriptions",
                headers=self._headers,
                json=payload,
            )
        if response.is_error:
            raise MaxApiError(f"MAX API returned HTTP {response.status_code}")
        return response.json()

    async def get_subscriptions(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20, verify=self._verify) as client:
            response = await client.get(
                f"{self._base_url}/subscriptions",
                headers=self._headers,
            )
        if response.is_error:
            raise MaxApiError(f"MAX API returned HTTP {response.status_code}")
        return response.json()

    async def delete_subscription(self, webhook_url: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20, verify=self._verify) as client:
            response = await client.delete(
                f"{self._base_url}/subscriptions",
                headers=self._headers,
                params={"url": webhook_url},
            )
        if response.is_error:
            raise MaxApiError(f"MAX API returned HTTP {response.status_code}")
        return response.json()
