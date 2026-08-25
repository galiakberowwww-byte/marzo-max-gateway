import hashlib
import hmac

from app.contact_verification import is_verified_max_contact, phone_from_vcf


def test_verifies_official_max_request_contact_hash() -> None:
    token = "test-token"
    vcf = "BEGIN:VCARD\\r\\nTEL;TYPE=cell:79990000000\\r\\nEND:VCARD\\r\\n"
    expected = hmac.new(token.encode(), vcf.replace("\\r\\n", "\r\n").encode(), hashlib.sha256).hexdigest()
    assert is_verified_max_contact(token=token, vcf_info=vcf, received_hash=expected)
    assert not is_verified_max_contact(token=token, vcf_info=vcf, received_hash="0" * 64)
    assert phone_from_vcf(vcf) == "79990000000"
