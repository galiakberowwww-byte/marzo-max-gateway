from app.max_client import MaxClient


def test_view_body_preserves_safe_media_before_keyboard() -> None:
    client = MaxClient("test-token", "https://max.example")
    body = client._view_body(
        {
            "text": "Платежка",
            "mediaAttachments": [
                {"type": "image", "payload": {"token": "photo-token", "unsafe": "drop"}},
                {"type": "file", "payload": {"token": "file-token", "name": "receipt.pdf"}},
            ],
            "buttons": [[{"text": "К платежам", "payload": "rodcom:payment-claims:1"}]],
        }
    )

    assert body == {
        "text": "Платежка",
        "attachments": [
            {"type": "image", "payload": {"token": "photo-token"}},
            {"type": "file", "payload": {"token": "file-token"}},
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [[
                        {
                            "type": "callback",
                            "text": "К платежам",
                            "payload": "rodcom:payment-claims:1",
                        }
                    ]]
                },
            },
        ],
    }


def test_view_body_drops_untrusted_or_unsupported_media() -> None:
    client = MaxClient("test-token", "https://max.example")
    body = client._view_body(
        {
            "text": "Платежка",
            "mediaAttachments": [
                {"type": "audio", "payload": {"token": "audio-token"}},
                {"type": "file", "payload": {"url": "https://unsafe.example/file"}},
                {"type": "image", "payload": {"unsupported": True}},
                "not-an-object",
            ],
            "buttons": [],
        }
    )

    assert body == {"text": "Платежка", "attachments": []}


def test_view_body_limits_media_to_first_four_candidates() -> None:
    client = MaxClient("test-token", "https://max.example")
    body = client._view_body(
        {
            "text": "Платежка",
            "mediaAttachments": [
                {"type": "image", "payload": {"token": f"photo-{index}"}}
                for index in range(6)
            ],
            "buttons": [],
        }
    )

    assert [item["payload"]["token"] for item in body["attachments"]] == [
        "photo-0",
        "photo-1",
        "photo-2",
        "photo-3",
    ]
