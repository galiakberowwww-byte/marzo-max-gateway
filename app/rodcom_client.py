from typing import Any
from uuid import uuid4

import httpx


class RodcomClient:
    def __init__(self, base_url: str, gateway_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Rodcom-Gateway-Token": gateway_token}

    async def _post(self, path: str, body: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        headers = dict(self._headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self._base_url}{path}", headers=headers, json=body)
        response.raise_for_status()
        return response.json()

    async def register_parent(self, *, max_user_id: str, phone: str, display_name: str, event_id: str) -> dict[str, Any]:
        return await self._post("/internal/v1/max/parents/register", {
            "maxUserId": max_user_id, "phone": phone, "displayName": display_name, "eventId": event_id,
        })

    async def create_community(self, *, actor_user_id: str, name: str) -> dict[str, Any]:
        return await self._post("/internal/v1/max/communities", {"actorUserId": actor_user_id, "name": name}, idempotency_key=str(uuid4()))

    async def create_invitation(self, *, actor_user_id: str, community_id: str) -> dict[str, Any]:
        return await self._post(f"/internal/v1/max/communities/{community_id}/invitations", {"actorUserId": actor_user_id, "maxUses": 100}, idempotency_key=str(uuid4()))

    async def accept_invitation(self, *, actor_user_id: str, token: str) -> dict[str, Any]:
        return await self._post("/internal/v1/max/community-invitations/accept", {"actorUserId": actor_user_id, "token": token}, idempotency_key=str(uuid4()))

    async def create_membership_request(self, *, actor_user_id: str, community_id: str, child_display_name: str) -> dict[str, Any]:
        return await self._post(f"/internal/v1/max/communities/{community_id}/membership-requests", {"actorUserId": actor_user_id, "childDisplayName": child_display_name}, idempotency_key=str(uuid4()))
