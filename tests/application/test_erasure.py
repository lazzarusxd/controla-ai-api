from uuid import UUID, uuid4
from typing import Dict, List, Optional

import pytest

from app.domain.types import ErasedResource
from app.domain.value_objects import ErasureManifest
from app.application.dto import ErasedAccountDTO, EraseAccountRequestDTO
from app.application.usecases.erasure.erase_account import EraseAccountUseCase
from app.domain.exceptions.erasure_exceptions import (
    AccountNotFoundError,
    ErasureNotConfirmedError,
    InvalidErasureManifestError
)


USER_ID = uuid4()
PARTNER_ID = uuid4()


def build_totals() -> Dict[ErasedResource, int]:
    return {
        ErasedResource.PROFILE: 1,
        ErasedResource.TRANSACTIONS: 12,
        ErasedResource.RECEIPTS: 3,
        ErasedResource.SUBSCRIPTIONS: 2,
        ErasedResource.SUBSCRIPTION_ALERTS: 4,
        ErasedResource.ASSETS: 1,
        ErasedResource.GOALS: 2,
        ErasedResource.TAX_DEDUCTIONS: 0,
        ErasedResource.ASSISTANT_MESSAGES: 7,
        ErasedResource.VECTOR_EMBEDDINGS: 15
    }


class FakeErasureRepository:

    def __init__(self, erased: Optional[ErasedAccountDTO] = None, found: bool = True) -> None:
        self._found = found
        self.calls: List[EraseAccountRequestDTO] = []
        self._erased = erased if erased is not None else ErasedAccountDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            totals=build_totals(),
            receipt_file_paths=[
                f"{PARTNER_ID}/{USER_ID}/aa.jpg",
                f"{PARTNER_ID}/{USER_ID}/bb.pdf"
            ]
        )

    async def erase(self, erase_account_request: EraseAccountRequestDTO) -> Optional[ErasedAccountDTO]:
        self.calls.append(erase_account_request)

        return self._erased if self._found else None


class FakeExportPurger:

    def __init__(self, file_paths: Optional[List[str]] = None) -> None:
        self.calls: List[UUID] = []
        self.file_paths = file_paths if file_paths is not None else [f"{PARTNER_ID}/{USER_ID}/export.json"]

    async def purge_user(self, partner_id: UUID, user_id: UUID) -> List[str]:
        _ = partner_id
        self.calls.append(user_id)

        return list(self.file_paths)


class FakeStorage:

    def __init__(self, files: Optional[Dict[str, bytes]] = None, failing: Optional[List[str]] = None) -> None:
        self.failing: List[str] = failing if failing is not None else []
        self.files: Dict[str, bytes] = files if files is not None else {}

    async def save(self, *args: object, **kwargs: object) -> str:
        _ = self, args, kwargs

        return ""

    async def read(self, file_path: str) -> bytes:
        content = self.files.get(file_path)

        if content is None:
            raise FileNotFoundError(file_path)

        return content

    async def delete(self, file_path: str) -> bool:
        if file_path in self.failing:
            raise OSError(file_path)

        return self.files.pop(file_path, None) is not None


def build_usecase(
        export_storage: Optional[FakeStorage] = None,
        receipt_storage: Optional[FakeStorage] = None,
        export_purger: Optional[FakeExportPurger] = None,
        erasure_repository: Optional[FakeErasureRepository] = None
) -> EraseAccountUseCase:
    return EraseAccountUseCase(
        export_storage=export_storage if export_storage is not None else FakeStorage(),
        export_purger=export_purger if export_purger is not None else FakeExportPurger(),
        receipt_storage=receipt_storage if receipt_storage is not None else FakeStorage(),
        erasure_repository=erasure_repository if erasure_repository is not None else FakeErasureRepository()
    )


def build_request(confirmation: Optional[str] = None) -> EraseAccountRequestDTO:
    return EraseAccountRequestDTO(
        user_id=USER_ID,
        partner_id=PARTNER_ID,
        confirmation=confirmation if confirmation is not None else str(USER_ID)
    )


def test_request_without_confirmation_is_not_confirmed() -> None:
    assert EraseAccountRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID).is_confirmed is False


def test_confirmation_ignores_case_and_surrounding_space() -> None:
    request = build_request(confirmation=f"  {str(USER_ID).upper()}  ")

    assert request.is_confirmed is True


def test_confirmation_with_other_identifier_is_rejected() -> None:
    assert build_request(confirmation=str(uuid4())).is_confirmed is False


async def test_missing_confirmation_blocks_erasure() -> None:
    erasure_repository = FakeErasureRepository()
    usecase = build_usecase(erasure_repository=erasure_repository)

    with pytest.raises(ErasureNotConfirmedError):
        await usecase.execute(
            erase_account_request=EraseAccountRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID)
        )

    assert erasure_repository.calls == []


async def test_divergent_confirmation_blocks_erasure() -> None:
    erasure_repository = FakeErasureRepository()
    usecase = build_usecase(erasure_repository=erasure_repository)

    with pytest.raises(ErasureNotConfirmedError):
        await usecase.execute(erase_account_request=build_request(confirmation=str(uuid4())))

    assert erasure_repository.calls == []


async def test_unknown_account_raises_not_found() -> None:
    usecase = build_usecase(erasure_repository=FakeErasureRepository(found=False))

    with pytest.raises(AccountNotFoundError):
        await usecase.execute(erase_account_request=build_request())


async def test_second_call_over_same_account_raises_not_found() -> None:
    erasure_repository = FakeErasureRepository()
    usecase = build_usecase(erasure_repository=erasure_repository)

    await usecase.execute(erase_account_request=build_request())

    erasure_repository._found = False

    with pytest.raises(AccountNotFoundError):
        await usecase.execute(erase_account_request=build_request())


async def test_files_are_not_touched_when_account_is_absent() -> None:
    receipt_storage = FakeStorage(files={f"{PARTNER_ID}/{USER_ID}/aa.jpg": b"x"})
    usecase = build_usecase(
        receipt_storage=receipt_storage,
        erasure_repository=FakeErasureRepository(found=False)
    )

    with pytest.raises(AccountNotFoundError):
        await usecase.execute(erase_account_request=build_request())

    assert receipt_storage.files


async def test_erasure_counts_every_cascaded_resource() -> None:
    result = await build_usecase().execute(erase_account_request=build_request())

    assert result.manifest.total_of(ErasedResource.PROFILE) == 1
    assert result.manifest.total_of(ErasedResource.TRANSACTIONS) == 12
    assert result.manifest.total_of(ErasedResource.VECTOR_EMBEDDINGS) == 15
    assert result.manifest.total_records == sum(build_totals().values())


async def test_receipt_files_leave_the_volume() -> None:
    paths = [f"{PARTNER_ID}/{USER_ID}/aa.jpg", f"{PARTNER_ID}/{USER_ID}/bb.pdf"]
    receipt_storage = FakeStorage(files={path: b"conteudo" for path in paths})

    result = await build_usecase(receipt_storage=receipt_storage).execute(
        erase_account_request=build_request()
    )

    assert receipt_storage.files == {}
    assert set(paths).issubset(set(result.manifest.purged_files))


async def test_export_artifacts_and_state_are_purged() -> None:
    artifact_path = f"{PARTNER_ID}/{USER_ID}/export.json"
    export_purger = FakeExportPurger(file_paths=[artifact_path])
    export_storage = FakeStorage(files={artifact_path: b"{}"})

    result = await build_usecase(
        export_purger=export_purger,
        export_storage=export_storage
    ).execute(erase_account_request=build_request())

    assert export_purger.calls == [USER_ID]
    assert export_storage.files == {}
    assert artifact_path in result.manifest.purged_files


async def test_erasure_is_complete_when_no_file_resists() -> None:
    result = await build_usecase().execute(erase_account_request=build_request())

    assert result.is_complete is True
    assert result.manifest.outcome == "COMPLETE"


async def test_file_failure_yields_partial_outcome_without_interrupting_the_rest() -> None:
    stubborn = f"{PARTNER_ID}/{USER_ID}/aa.jpg"
    removable = f"{PARTNER_ID}/{USER_ID}/bb.pdf"
    receipt_storage = FakeStorage(
        failing=[stubborn],
        files={stubborn: b"x", removable: b"y"}
    )

    result = await build_usecase(receipt_storage=receipt_storage).execute(
        erase_account_request=build_request()
    )

    assert result.is_complete is False
    assert result.manifest.outcome == "PARTIAL"
    assert result.manifest.retained_files == (stubborn,)
    assert removable in result.manifest.purged_files
    assert removable not in receipt_storage.files


async def test_erasure_result_carries_only_opaque_identifiers() -> None:
    result = await build_usecase().execute(erase_account_request=build_request())

    assert result.user_id == USER_ID
    assert result.partner_id == PARTNER_ID
    assert result.erased_at.tzinfo is not None


def test_manifest_orders_resources_canonically() -> None:
    manifest = ErasureManifest.build(totals=build_totals())

    assert [count.resource for count in manifest.counts] == ErasedResource.canonical_order()


def test_manifest_label_omits_resources_without_records() -> None:
    manifest = ErasureManifest.build(totals=build_totals())

    assert "TAX_DEDUCTIONS" not in manifest.label
    assert "TRANSACTIONS=12" in manifest.label


def test_manifest_defaults_absent_resource_to_zero() -> None:
    manifest = ErasureManifest.build(totals={ErasedResource.PROFILE: 1})

    assert manifest.total_of(ErasedResource.GOALS) == 0
    assert manifest.total_records == 1


def test_manifest_rejects_negative_count() -> None:
    with pytest.raises(InvalidErasureManifestError):
        ErasureManifest.build(totals={ErasedResource.PROFILE: -1})


def test_only_receipts_carry_stored_files() -> None:
    with_files = [resource for resource in ErasedResource.canonical_order() if resource.has_stored_files]

    assert with_files == [ErasedResource.RECEIPTS]
