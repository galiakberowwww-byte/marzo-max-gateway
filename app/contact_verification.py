import hashlib
import hmac


def is_verified_max_contact(*, token: str, vcf_info: str, received_hash: str) -> bool:
    """Validate the hash returned only by MAX request_contact.

    MAX defines this as HMAC-SHA256(access_token, vcf_info).  JSON escapes
    have already been decoded by FastAPI; normalise an accidental literal CRLF
    representation as the platform documentation requires.
    """
    normalized = vcf_info.replace("\\r\\n", "\r\n")
    expected = hmac.new(token.encode(), normalized.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_hash)


def phone_from_vcf(vcf_info: str) -> str | None:
    for line in vcf_info.replace("\\r\\n", "\r\n").splitlines():
        if line.upper().startswith("TEL") and ":" in line:
            return line.split(":", 1)[1].strip()
    return None
