import asyncio

import httpx

from app.max_client import MaxApiError, MaxClient
from app.settings import get_settings


async def main() -> None:
    settings = get_settings()
    client = MaxClient(
        settings.max_bot_token,
        settings.max_api_base_url,
        settings.max_ca_bundle,
    )
    try:
        bot = await client.get_me()
    except MaxApiError as exc:
        print(f"API error: {exc}")
        raise SystemExit(1) from None
    except httpx.HTTPError as exc:
        print(f"Connection error: {type(exc).__name__}")
        raise SystemExit(1) from None

    print("MAX API: connected")
    print(f"Bot: {bot.get('name', 'unknown')} (@{bot.get('username', 'unknown')})")


if __name__ == "__main__":
    asyncio.run(main())
