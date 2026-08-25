import argparse
import asyncio

from app.max_client import MaxClient
from app.settings import get_settings


async def main() -> None:
    parser = argparse.ArgumentParser(description="Replace the active MAX webhook")
    parser.add_argument("url")
    args = parser.parse_args()

    settings = get_settings()
    client = MaxClient(
        settings.max_bot_token,
        settings.max_api_base_url,
        settings.max_ca_bundle,
    )
    current = (await client.get_subscriptions()).get("subscriptions") or []
    current_urls = {item.get("url") for item in current}
    for old_url in current_urls - {args.url}:
        if old_url:
            await client.delete_subscription(old_url)

    if args.url not in current_urls:
        await client.create_subscription(
            args.url,
            settings.max_webhook_secret,
            ["message_created", "bot_started"],
        )

    verified = (await client.get_subscriptions()).get("subscriptions") or []
    verified_urls = [item.get("url") for item in verified]
    if verified_urls != [args.url]:
        raise SystemExit(f"Unexpected subscriptions: {verified_urls}")
    print("Webhook switched and verified")
    print(args.url)


if __name__ == "__main__":
    asyncio.run(main())
