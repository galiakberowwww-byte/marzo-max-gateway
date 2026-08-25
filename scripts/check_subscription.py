import asyncio

from app.max_client import MaxClient
from app.settings import get_settings


async def main() -> None:
    settings = get_settings()
    client = MaxClient(
        settings.max_bot_token,
        settings.max_api_base_url,
        settings.max_ca_bundle,
    )
    result = await client.get_subscriptions()
    subscriptions = result.get("subscriptions") or []
    print(f"Subscriptions: {len(subscriptions)}")
    for subscription in subscriptions:
        print(subscription.get("url", "unknown"))
        print(", ".join(subscription.get("update_types") or []))


if __name__ == "__main__":
    asyncio.run(main())
