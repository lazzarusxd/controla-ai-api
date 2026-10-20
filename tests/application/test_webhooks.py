from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pytest

from app.domain.entities import PartnerWebhook
from app.application.interfaces import IPartnerWebhookRepository
from app.domain.exceptions.receipt_exceptions import WebhookNotRegisteredError
from app.application.usecases.receipts.register_webhook import RegisterWebhookUseCase
from app.application.dto import RegisterWebhookRequestDTO, RotateWebhookSecretRequestDTO
from app.application.usecases.receipts.rotate_webhook_secret import RotateWebhookSecretUseCase


PARTNER_ID = uuid4()
TARGET_URL = "https://parceiro.example.com/callbacks"


def build_webhook(
        is_active: bool = True,
        target_url: str = TARGET_URL,
        secret: str = "segredo-vigente",
        updated_at: Optional[datetime] = None
) -> PartnerWebhook:
    return PartnerWebhook(
        secret=secret,
        is_active=is_active,
        updated_at=updated_at,
        target_url=target_url,
        partner_id=PARTNER_ID,
        created_at=datetime.now(timezone.utc)
    )


class FakePartnerWebhookRepository(IPartnerWebhookRepository):

    def __init__(self, stored: Optional[PartnerWebhook] = None) -> None:
        self._stored = stored
        self.rotated_secrets: List[str] = []
        self.discarded_secrets: List[str] = []

    async def upsert(
            self,
            secret: str,
            register_webhook_request: RegisterWebhookRequestDTO
    ) -> Tuple[PartnerWebhook, bool]:
        was_created = self._stored is None

        if not was_created:
            self.discarded_secrets.append(secret)

        self._stored = build_webhook(
            is_active=register_webhook_request.is_active,
            target_url=register_webhook_request.target_url,
            secret=secret if was_created else self._stored.secret
        )

        return self._stored, was_created

    async def rotate_secret(self, partner_id: UUID, secret: str) -> Optional[PartnerWebhook]:
        _ = partner_id

        if self._stored is None:
            return None

        self.rotated_secrets.append(secret)
        self._stored = build_webhook(
            secret=secret,
            is_active=self._stored.is_active,
            target_url=self._stored.target_url,
            updated_at=datetime.now(timezone.utc)
        )

        return self._stored

    async def find_by_partner(self, partner_id: UUID) -> Optional[PartnerWebhook]:
        _ = partner_id

        return self._stored


def build_register_request(is_active: bool = True, target_url: str = TARGET_URL) -> RegisterWebhookRequestDTO:
    return RegisterWebhookRequestDTO(
        is_active=is_active,
        target_url=target_url,
        partner_id=PARTNER_ID
    )


async def test_first_registration_issues_the_secret() -> None:
    usecase = RegisterWebhookUseCase(partner_webhook_repository=FakePartnerWebhookRepository())

    registered = await usecase.execute(register_webhook_request=build_register_request())

    assert registered.was_secret_issued is True
    assert registered.secret is not None
    assert registered.target_url == TARGET_URL


async def test_update_preserves_the_secret_in_force() -> None:
    repository = FakePartnerWebhookRepository(stored=build_webhook())
    usecase = RegisterWebhookUseCase(partner_webhook_repository=repository)

    registered = await usecase.execute(
        register_webhook_request=build_register_request(target_url="https://parceiro.example.com/v2")
    )

    stored = await repository.find_by_partner(partner_id=PARTNER_ID)

    assert registered.secret is None
    assert registered.was_secret_issued is False
    assert registered.target_url == "https://parceiro.example.com/v2"
    assert stored.secret == "segredo-vigente"


async def test_repeated_registration_is_idempotent() -> None:
    repository = FakePartnerWebhookRepository()
    usecase = RegisterWebhookUseCase(partner_webhook_repository=repository)

    first = await usecase.execute(register_webhook_request=build_register_request())
    await usecase.execute(register_webhook_request=build_register_request())
    await usecase.execute(register_webhook_request=build_register_request())

    stored = await repository.find_by_partner(partner_id=PARTNER_ID)

    assert stored.secret == first.secret
    assert stored.target_url == TARGET_URL


async def test_candidate_secret_is_discarded_on_update() -> None:
    repository = FakePartnerWebhookRepository(stored=build_webhook())
    usecase = RegisterWebhookUseCase(partner_webhook_repository=repository)

    await usecase.execute(register_webhook_request=build_register_request())

    assert len(repository.discarded_secrets) == 1
    assert repository.rotated_secrets == []


async def test_registration_can_suspend_delivery_without_losing_the_secret() -> None:
    repository = FakePartnerWebhookRepository(stored=build_webhook())
    usecase = RegisterWebhookUseCase(partner_webhook_repository=repository)

    registered = await usecase.execute(register_webhook_request=build_register_request(is_active=False))

    stored = await repository.find_by_partner(partner_id=PARTNER_ID)

    assert registered.is_active is False
    assert stored.is_deliverable is False
    assert stored.secret == "segredo-vigente"


async def test_rotation_replaces_the_secret_in_force() -> None:
    repository = FakePartnerWebhookRepository(stored=build_webhook())
    usecase = RotateWebhookSecretUseCase(partner_webhook_repository=repository)

    rotated = await usecase.execute(
        rotate_webhook_secret_request=RotateWebhookSecretRequestDTO(partner_id=PARTNER_ID)
    )

    stored = await repository.find_by_partner(partner_id=PARTNER_ID)

    assert rotated.secret != "segredo-vigente"
    assert stored.secret == rotated.secret
    assert repository.rotated_secrets == [rotated.secret]


async def test_rotation_is_not_idempotent_by_design() -> None:
    repository = FakePartnerWebhookRepository(stored=build_webhook())
    usecase = RotateWebhookSecretUseCase(partner_webhook_repository=repository)

    first = await usecase.execute(
        rotate_webhook_secret_request=RotateWebhookSecretRequestDTO(partner_id=PARTNER_ID)
    )
    second = await usecase.execute(
        rotate_webhook_secret_request=RotateWebhookSecretRequestDTO(partner_id=PARTNER_ID)
    )

    assert first.secret != second.secret


async def test_rotation_preserves_the_registered_destination() -> None:
    repository = FakePartnerWebhookRepository(stored=build_webhook())
    usecase = RotateWebhookSecretUseCase(partner_webhook_repository=repository)

    await usecase.execute(
        rotate_webhook_secret_request=RotateWebhookSecretRequestDTO(partner_id=PARTNER_ID)
    )

    stored = await repository.find_by_partner(partner_id=PARTNER_ID)

    assert stored.target_url == TARGET_URL
    assert stored.is_active is True


async def test_rotation_without_registered_webhook_is_rejected() -> None:
    usecase = RotateWebhookSecretUseCase(partner_webhook_repository=FakePartnerWebhookRepository())

    with pytest.raises(WebhookNotRegisteredError):
        await usecase.execute(
            rotate_webhook_secret_request=RotateWebhookSecretRequestDTO(partner_id=PARTNER_ID)
        )


async def test_rotation_timestamp_comes_from_the_persisted_row() -> None:
    repository = FakePartnerWebhookRepository(stored=build_webhook())
    usecase = RotateWebhookSecretUseCase(partner_webhook_repository=repository)

    rotated = await usecase.execute(
        rotate_webhook_secret_request=RotateWebhookSecretRequestDTO(partner_id=PARTNER_ID)
    )

    stored = await repository.find_by_partner(partner_id=PARTNER_ID)

    assert rotated.rotated_at == stored.updated_at


async def test_registered_dto_reports_whether_a_secret_was_issued() -> None:
    repository = FakePartnerWebhookRepository()
    usecase = RegisterWebhookUseCase(partner_webhook_repository=repository)

    created = await usecase.execute(register_webhook_request=build_register_request())
    updated = await usecase.execute(register_webhook_request=build_register_request())

    assert created.was_secret_issued is True
    assert updated.was_secret_issued is False
    assert isinstance(created.partner_id, UUID)
