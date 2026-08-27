import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class MaxWebAppValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedMaxWebAppData:
    external_user_id: str
    auth_date: int
    start_param: str | None
    first_name: str | None
    last_name: str | None


def _signature(data_check_string: str, bot_token: str) -> str:
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_max_webapp_init_data(
    init_data: str,
    bot_token: str,
    *,
    now: int | None = None,
    max_age_seconds: int = 3600,
) -> ValidatedMaxWebAppData:
    if not init_data or not bot_token:
        raise MaxWebAppValidationError("invalid_init_data")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise MaxWebAppValidationError("invalid_init_data") from exc

    if not pairs:
        raise MaxWebAppValidationError("invalid_init_data")

    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise MaxWebAppValidationError("invalid_init_data")

    payload = dict(pairs)
    received_hash = payload.pop("hash", None)
    if not received_hash or len(received_hash) != 64:
        raise MaxWebAppValidationError("invalid_init_data")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(payload.items())
    )
    expected_hash = _signature(data_check_string, bot_token)
    if not hmac.compare_digest(received_hash.lower(), expected_hash.lower()):
        raise MaxWebAppValidationError("invalid_init_data")

    try:
        auth_date = int(payload["auth_date"])
        raw_user = json.loads(payload["user"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MaxWebAppValidationError("invalid_init_data") from exc

    if not isinstance(raw_user, dict) or "id" not in raw_user:
        raise MaxWebAppValidationError("invalid_init_data")
    external_user_id = str(raw_user["id"]).strip()
    if not external_user_id:
        raise MaxWebAppValidationError("invalid_init_data")

    current = int(time.time()) if now is None else now
    age = current - auth_date
    if age < -60 or age > max_age_seconds:
        raise MaxWebAppValidationError("expired_init_data")

    first_name = raw_user.get("first_name")
    last_name = raw_user.get("last_name")
    return ValidatedMaxWebAppData(
        external_user_id=external_user_id,
        auth_date=auth_date,
        start_param=payload.get("start_param") or None,
        first_name=first_name.strip() if isinstance(first_name, str) and first_name.strip() else None,
        last_name=last_name.strip() if isinstance(last_name, str) and last_name.strip() else None,
    )
