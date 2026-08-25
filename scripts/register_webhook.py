import argparse
import asyncio

from app.max_client import MaxClient
from app.settings import get_settings


async def main() -> None:
    parser = argparse.ArgumentParser(description="Register the MARZO MAX webhook")
    parser.add_argument("url", help="Public HTTPS URL ending in /webhooks/max")
    args = parser.parse_args()

    if not args.url.startswith("https://"):
        raise SystemExit("Webhook URL must start with https://")

    settings = get_settings()
    if not settings.max_webhook_secret:
        raise SystemExit("MAX_WEBHOOK_SECRET is not configured")

    client = MaxClient(
        settings.max_bot_token,
        settings.max_api_base_url,
        settings.max_ca_bundle,
    )
    result = await client.create_subscription(
        args.url,
        settings.max_webhook_secret,
        ["message_created", "bot_started"],
    )
    print("Webhook registered" if result.get("success") else "Registration failed")
    if result.get("message"):
        print(result["message"])


if __name__ == "__main__":
    asyncio.run(main())
