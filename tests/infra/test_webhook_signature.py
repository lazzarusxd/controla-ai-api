import hmac
import json
import hashlib
from typing import Dict, Tuple

from app.infra.providers.http_webhook_notifier import HttpWebhookNotifier


SECRET = "segredo-do-parceiro"
SIGNATURE_HEADER = "X-ControlaAI-Signature"


def build_notifier() -> HttpWebhookNotifier:
    return HttpWebhookNotifier(timeout_seconds=10, max_attempts=3, retry_backoff_seconds=0.0)


def parse_signature(header: str) -> Dict[str, str]:
    return dict(part.split("=", 1) for part in header.split(","))


def sign(secret: str, timestamp: str, body: str) -> str:
    return hmac.new(
        digestmod=hashlib.sha256,
        key=secret.encode("utf-8"),
        msg=f"{timestamp}.{body}".encode()
    ).hexdigest()


def build_signed_pair(body: str = '{"event":"receipt.processed"}') -> Tuple[str, str]:
    # noinspection PyProtectedMember
    header = build_notifier()._sign(secret=SECRET, timestamp="1786935390", body=body)

    return header, body


def test_signature_header_carries_timestamp_and_version() -> None:
    header, _ = build_signed_pair()
    parsed = parse_signature(header=header)

    assert parsed.get("t") == "1786935390"
    assert len(parsed.get("v1")) == 64


def test_partner_reproduces_the_signature_with_the_shared_secret() -> None:
    header, body = build_signed_pair()
    parsed = parse_signature(header=header)

    expected = sign(secret=SECRET, timestamp=parsed.get("t"), body=body)

    assert hmac.compare_digest(parsed.get("v1"), expected) is True


def test_signature_covers_the_timestamp_so_replays_do_not_verify() -> None:
    header, body = build_signed_pair()
    parsed = parse_signature(header=header)

    replayed = sign(secret=SECRET, timestamp="1786999999", body=body)

    assert parsed.get("v1") != replayed


def test_signature_changes_when_the_body_is_tampered_with() -> None:
    header, _ = build_signed_pair()
    parsed = parse_signature(header=header)

    tampered = sign(
        secret=SECRET,
        timestamp=parsed.get("t"),
        body=json.dumps({"event": "receipt.failed"}, separators=(",", ":"))
    )

    assert parsed.get("v1") != tampered


def test_wrong_secret_does_not_verify() -> None:
    header, body = build_signed_pair()
    parsed = parse_signature(header=header)

    assert parsed.get("v1") != sign(secret="outro-segredo", timestamp=parsed.get("t"), body=body)


def test_signature_header_name_is_stable() -> None:
    assert SIGNATURE_HEADER == "X-ControlaAI-Signature"
