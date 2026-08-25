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

    async def send_keyboard(
        self, text: str, buttons: list[dict[str, Any]], *, user_id: int | None = None, chat_id: int | None = None
    ) -> dict[str, Any]:
        if (user_id is None) == (chat_id is None):
            raise ValueError("Specify exactly one of user_id or chat_id")
        params = {"user_id": user_id} if user_id is not None else {"chat_id": chat_id}
        payload = {"text": text, "notify": True, "attachments": [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]}
        async with httpx.AsyncClient(timeout=15, verify=self._verify) as client:
            response = await client.post(f"{self._base_url}/messages", headers=self._headers, params=params, json=payload)
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
