import csv
import json
import zipfile
from uuid import UUID, uuid4
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.entities import DataExport
from app.domain.value_objects import ExportArtifact, ExportScope
from app.application.services.data_export_service import DataExportService
from app.infra.serializers.csv_export_serializer import CsvExportSerializer
from app.infra.serializers.json_export_serializer import JsonExportSerializer
from app.application.usecases.exports.get_data_export import GetDataExportUseCase
from app.domain.types import ExportEvent, ExportFormat, ExportSection, ExportStatus
from app.application.usecases.exports.request_data_export import RequestDataExportUseCase
from app.application.usecases.exports.download_data_export import DownloadDataExportUseCase
from app.domain.exceptions.export_exceptions import (
    ExportNotReadyError,
    EmptyExportScopeError,
    DataExportNotFoundError,
    InvalidExportPeriodError,
    ExportOwnerNotFoundError,
    ExportArtifactMissingError,
    ExportGenerationFailedError
)
from app.application.dto import (
    ExportPackageDTO,
    ExportSectionDTO,
    GetDataExportRequestDTO,
    ExportPackageRequestDTO,
    RequestDataExportRequestDTO,
    GenerateDataExportRequestDTO,
    DownloadDataExportRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()
RETENTION_SECONDS = 3600


def build_package(scope: Optional[ExportScope] = None) -> ExportPackageDTO:
    resolved = scope if scope is not None else ExportScope.build(
        sections=[ExportSection.PROFILE, ExportSection.TRANSACTIONS]
    )

    return ExportPackageDTO(
        scope=resolved,
        user_id=USER_ID,
        partner_id=PARTNER_ID,
        generated_at=datetime(2026, 8, 23, 10, 15, tzinfo=timezone.utc),
        sections=[
            ExportSectionDTO(
                name="profile",
                title="Perfil do titular",
                section=ExportSection.PROFILE,
                columns=["user_id", "name", "is_active"],
                rows=[{"user_id": str(USER_ID), "name": "Ana Beatriz", "is_active": True}]
            ),
            ExportSectionDTO(
                name="transactions",
                title="Lançamentos",
                section=ExportSection.TRANSACTIONS,
                columns=["transaction_id", "amount", "category", "due_date"],
                rows=[
                    {
                        "due_date": None,
                        "amount": "1284.90",
                        "category": "Delivery",
                        "transaction_id": str(uuid4())
                    },
                    {
                        "amount": "89.00",
                        "category": "Streaming",
                        "due_date": "2026-04-10",
                        "transaction_id": str(uuid4())
                    }
                ]
            )
        ]
    )


def build_export(
        failure_reason: Optional[str] = None,
        artifact: Optional[ExportArtifact] = None,
        status: ExportStatus = ExportStatus.PENDING
) -> DataExport:
    requested_at = datetime.now(timezone.utc)

    return DataExport(
        status=status,
        user_id=USER_ID,
        export_id=uuid4(),
        artifact=artifact,
        partner_id=PARTNER_ID,
        requested_at=requested_at,
        failure_reason=failure_reason,
        export_format=ExportFormat.JSON,
        scope=ExportScope.build(sections=[ExportSection.PROFILE]),
        expires_at=requested_at + timedelta(seconds=RETENTION_SECONDS)
    )


class FakeExportRepository:

    def __init__(self, owner_exists: bool = True, package: Optional[ExportPackageDTO] = None) -> None:
        self._owner_exists = owner_exists
        self.received: Optional[ExportPackageRequestDTO] = None
        self._package = package if package is not None else build_package()

    async def user_exists(self, partner_id: UUID, user_id: UUID) -> bool:
        _ = self, partner_id, user_id

        return self._owner_exists

    async def load_package(self, export_package_request: ExportPackageRequestDTO) -> ExportPackageDTO:
        self.received = export_package_request

        return self._package


class FakeExportRegistry:

    def __init__(self, stored: Optional[DataExport] = None) -> None:
        self.saved: List[DataExport] = []
        self._stored: Optional[DataExport] = stored

    async def register(self, data_export: DataExport) -> DataExport:
        self._stored = data_export
        self.saved.append(data_export)

        return data_export

    async def find(self, get_data_export_request: GetDataExportRequestDTO) -> Optional[DataExport]:
        stored = self._stored

        if stored is None:
            return None

        matches = (
            stored.user_id == get_data_export_request.user_id
            and stored.partner_id == get_data_export_request.partner_id
            and stored.export_id == get_data_export_request.export_id
        )

        return stored if matches else None

    async def save(self, data_export: DataExport) -> DataExport:
        self._stored = data_export
        self.saved.append(data_export)

        return data_export


class FakeExportStorage:

    def __init__(self, files: Optional[Dict[str, bytes]] = None) -> None:
        self.files: Dict[str, bytes] = files if files is not None else {}

    async def save(self, partner_id: UUID, user_id: UUID, export_id: UUID, extension: str, content: bytes) -> str:
        file_path = f"{partner_id}/{user_id}/{export_id}.{extension}"
        self.files[file_path] = content

        return file_path

    async def read(self, file_path: str) -> bytes:
        content = self.files.get(file_path)

        if content is None:
            raise FileNotFoundError(file_path)

        return content

    async def delete(self, file_path: str) -> bool:
        return self.files.pop(file_path, None) is not None


class FakeJobQueue:

    def __init__(self) -> None:
        self.calls: List[Any] = []

    async def enqueue(self, task_name: str, *args: Any) -> str:
        self.calls.append((task_name, args))

        return "job-0001"


class FakeExplodingSerializer:

    def serialize(self, export_package: ExportPackageDTO) -> Any:
        _ = self, export_package

        raise RuntimeError("provedor indisponível")


def test_scope_defaults_to_full_dossier() -> None:
    scope = ExportScope.build()

    assert scope.is_full_dossier is True
    assert scope.ordered_sections == ExportSection.canonical_order()


def test_scope_rejects_explicitly_empty_sections() -> None:
    with pytest.raises(EmptyExportScopeError):
        ExportScope.build(sections=[])


def test_scope_rejects_inverted_period() -> None:
    with pytest.raises(InvalidExportPeriodError):
        ExportScope.build(start_date=date(2026, 3, 31), end_date=date(2026, 1, 1))


def test_scope_orders_sections_canonically_regardless_of_input_order() -> None:
    scope = ExportScope.build(sections=[ExportSection.GOALS, ExportSection.PROFILE])

    assert scope.ordered_sections == [ExportSection.PROFILE, ExportSection.GOALS]


def test_only_dated_history_is_period_scoped() -> None:
    assert ExportSection.TRANSACTIONS.is_period_scoped is True
    assert ExportSection.RECEIPTS.is_period_scoped is True
    assert ExportSection.ASSETS.is_period_scoped is False


async def test_request_registers_pending_export_and_enqueues_job() -> None:
    registry = FakeExportRegistry()
    job_queue = FakeJobQueue()

    usecase = RequestDataExportUseCase(
        job_queue=job_queue,
        export_registry=registry,
        retention_seconds=RETENTION_SECONDS,
        export_repository=FakeExportRepository()
    )

    data_export = await usecase.execute(
        request_data_export_request=RequestDataExportRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            export_format=ExportFormat.JSON
        )
    )

    assert data_export.status is ExportStatus.PENDING
    assert data_export.artifact is None
    assert data_export.scope.is_full_dossier is True
    assert job_queue.calls[0][0] == "generate_data_export"
    assert job_queue.calls[0][1] == (str(PARTNER_ID), str(USER_ID), str(data_export.export_id))


async def test_request_sets_expiration_from_retention() -> None:
    usecase = RequestDataExportUseCase(
        job_queue=FakeJobQueue(),
        export_registry=FakeExportRegistry(),
        retention_seconds=RETENTION_SECONDS,
        export_repository=FakeExportRepository()
    )

    data_export = await usecase.execute(
        request_data_export_request=RequestDataExportRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            export_format=ExportFormat.CSV
        )
    )

    elapsed = (data_export.expires_at - data_export.requested_at).total_seconds()

    assert elapsed == pytest.approx(RETENTION_SECONDS)


async def test_request_rejects_unknown_owner_without_publishing_job() -> None:
    job_queue = FakeJobQueue()

    usecase = RequestDataExportUseCase(
        job_queue=job_queue,
        export_registry=FakeExportRegistry(),
        retention_seconds=RETENTION_SECONDS,
        export_repository=FakeExportRepository(owner_exists=False)
    )

    with pytest.raises(ExportOwnerNotFoundError):
        await usecase.execute(
            request_data_export_request=RequestDataExportRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                export_format=ExportFormat.JSON
            )
        )

    assert job_queue.calls == []


async def test_request_rejects_inverted_period_before_touching_the_database() -> None:
    repository = FakeExportRepository()

    usecase = RequestDataExportUseCase(
        job_queue=FakeJobQueue(),
        export_repository=repository,
        retention_seconds=RETENTION_SECONDS,
        export_registry=FakeExportRegistry()
    )

    with pytest.raises(InvalidExportPeriodError):
        await usecase.execute(
            request_data_export_request=RequestDataExportRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                export_format=ExportFormat.JSON,
                end_date=date(2026, 1, 1),
                start_date=date(2026, 3, 31)
            )
        )

    assert repository.received is None


async def test_get_export_from_another_partner_is_not_found() -> None:
    stored = build_export()
    usecase = GetDataExportUseCase(export_registry=FakeExportRegistry(stored=stored))

    with pytest.raises(DataExportNotFoundError):
        await usecase.execute(
            get_data_export_request=GetDataExportRequestDTO(
                user_id=USER_ID,
                partner_id=uuid4(),
                export_id=stored.export_id
            )
        )


async def test_generation_produces_artifact_and_completes_the_export() -> None:
    stored = build_export()
    registry = FakeExportRegistry(stored=stored)
    storage = FakeExportStorage()

    service = DataExportService(
        export_storage=storage,
        export_registry=registry,
        export_repository=FakeExportRepository(),
        export_serializers={ExportFormat.JSON: JsonExportSerializer()}
    )

    result = await service.generate(
        generate_data_export_request=GenerateDataExportRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            export_id=stored.export_id
        )
    )

    assert result.status is ExportStatus.COMPLETED
    assert result.event is ExportEvent.EXPORT_COMPLETED
    assert result.total_records == 3
    assert result.byte_size > 0
    assert len(storage.files) == 1


async def test_generation_is_idempotent_for_an_already_claimed_export() -> None:
    stored = build_export(status=ExportStatus.PROCESSING)
    storage = FakeExportStorage()

    service = DataExportService(
        export_storage=storage,
        export_repository=FakeExportRepository(),
        export_registry=FakeExportRegistry(stored=stored),
        export_serializers={ExportFormat.JSON: JsonExportSerializer()}
    )

    result = await service.generate(
        generate_data_export_request=GenerateDataExportRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            export_id=stored.export_id
        )
    )

    assert result.status is ExportStatus.PROCESSING
    assert storage.files == {}


async def test_generation_failure_is_recorded_without_leaving_an_artifact() -> None:
    stored = build_export()
    registry = FakeExportRegistry(stored=stored)
    storage = FakeExportStorage()

    service = DataExportService(
        export_storage=storage,
        export_registry=registry,
        export_repository=FakeExportRepository(),
        export_serializers={ExportFormat.JSON: FakeExplodingSerializer()}
    )

    result = await service.generate(
        generate_data_export_request=GenerateDataExportRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            export_id=stored.export_id
        )
    )

    assert result.status is ExportStatus.FAILED
    assert result.event is ExportEvent.EXPORT_FAILED
    assert result.failure_reason == "RuntimeError"
    assert storage.files == {}


async def test_generation_of_unknown_export_is_not_found() -> None:
    service = DataExportService(
        export_storage=FakeExportStorage(),
        export_registry=FakeExportRegistry(),
        export_repository=FakeExportRepository(),
        export_serializers={ExportFormat.JSON: JsonExportSerializer()}
    )

    with pytest.raises(DataExportNotFoundError):
        await service.generate(
            generate_data_export_request=GenerateDataExportRequestDTO(
                user_id=USER_ID,
                export_id=uuid4(),
                partner_id=PARTNER_ID
            )
        )


def build_completed_export(file_path: str, content: bytes) -> DataExport:
    pending = build_export()

    artifact = ExportArtifact.build(
        total_records=3,
        content=content,
        file_path=file_path,
        media_type="application/json",
        file_name="controla-ai-export.json"
    )

    return pending.complete(artifact=artifact, completed_at=datetime.now(timezone.utc))


async def test_download_returns_content_with_checksum_as_entity_tag() -> None:
    content = b'{"ok": true}'
    file_path = f"{PARTNER_ID}/{USER_ID}/artifact.json"
    stored = build_completed_export(file_path=file_path, content=content)

    usecase = DownloadDataExportUseCase(
        export_registry=FakeExportRegistry(stored=stored),
        export_storage=FakeExportStorage(files={file_path: content})
    )

    artifact = await usecase.execute(
        download_data_export_request=DownloadDataExportRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            export_id=stored.export_id
        )
    )

    assert artifact.content == content
    assert artifact.byte_size == len(content)
    assert artifact.media_type == "application/json"
    assert artifact.entity_tag.startswith('"sha256:')


async def test_download_before_completion_is_rejected() -> None:
    stored = build_export(status=ExportStatus.PROCESSING)

    usecase = DownloadDataExportUseCase(
        export_storage=FakeExportStorage(),
        export_registry=FakeExportRegistry(stored=stored)
    )

    with pytest.raises(ExportNotReadyError):
        await usecase.execute(
            download_data_export_request=DownloadDataExportRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                export_id=stored.export_id
            )
        )


async def test_download_after_failure_reports_the_failure() -> None:
    stored = build_export(status=ExportStatus.FAILED, failure_reason="RuntimeError")

    usecase = DownloadDataExportUseCase(
        export_storage=FakeExportStorage(),
        export_registry=FakeExportRegistry(stored=stored)
    )

    with pytest.raises(ExportGenerationFailedError):
        await usecase.execute(
            download_data_export_request=DownloadDataExportRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                export_id=stored.export_id
            )
        )


async def test_download_with_live_metadata_and_missing_file_is_gone() -> None:
    file_path = f"{PARTNER_ID}/{USER_ID}/artifact.json"
    stored = build_completed_export(file_path=file_path, content=b"{}")

    usecase = DownloadDataExportUseCase(
        export_storage=FakeExportStorage(),
        export_registry=FakeExportRegistry(stored=stored)
    )

    with pytest.raises(ExportArtifactMissingError):
        await usecase.execute(
            download_data_export_request=DownloadDataExportRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                export_id=stored.export_id
            )
        )


def test_json_serializer_preserves_monetary_values_as_text() -> None:
    serialized = JsonExportSerializer().serialize(export_package=build_package())
    document = json.loads(serialized.content.decode("utf-8"))

    transactions = next(section for section in document.get("sections") if section.get("name") == "transactions")

    assert serialized.media_type == "application/json"
    assert document.get("total_records") == 3
    assert transactions.get("records")[0].get("amount") == "1284.90"


def test_json_serializer_carries_the_scope_manifest() -> None:
    package = build_package(
        scope=ExportScope.build(
            end_date=date(2026, 3, 31),
            start_date=date(2026, 1, 1),
            sections=[ExportSection.PROFILE, ExportSection.TRANSACTIONS]
        )
    )

    document = json.loads(JsonExportSerializer().serialize(export_package=package).content.decode("utf-8"))

    assert document.get("scope").get("start_date") == "2026-01-01"
    assert document.get("scope").get("sections") == ["PROFILE", "TRANSACTIONS"]


def test_csv_serializer_emits_plain_text_for_a_single_section() -> None:
    package = build_package()
    single = ExportPackageDTO(
        scope=package.scope,
        user_id=package.user_id,
        partner_id=package.partner_id,
        sections=[package.sections[0]],
        generated_at=package.generated_at
    )

    serialized = CsvExportSerializer().serialize(export_package=single)
    rows = list(csv.reader(StringIO(serialized.content.decode("utf-8-sig"))))

    assert serialized.file_extension == "csv"
    assert serialized.media_type.startswith("text/csv")
    assert rows[0] == ["user_id", "name", "is_active"]
    assert rows[1][2] == "true"


def test_csv_serializer_packs_one_file_per_section_when_there_are_several() -> None:
    serialized = CsvExportSerializer().serialize(export_package=build_package())

    with zipfile.ZipFile(BytesIO(serialized.content)) as archive:
        names = sorted(archive.namelist())
        transactions = archive.read("transactions.csv").decode("utf-8-sig")

    assert serialized.media_type == "application/zip"
    assert names == ["profile.csv", "transactions.csv"]
    assert transactions.splitlines()[1].endswith(",")


def test_csv_serializer_renders_absent_values_as_empty_cells() -> None:
    serialized = CsvExportSerializer().serialize(export_package=build_package())

    with zipfile.ZipFile(BytesIO(serialized.content)) as archive:
        rows = list(csv.DictReader(StringIO(archive.read("transactions.csv").decode("utf-8-sig"))))

    assert rows[0].get("due_date") == ""
    assert rows[1].get("due_date") == "2026-04-10"


def test_only_a_pending_export_is_claimable() -> None:
    assert build_export().is_claimable is True
    assert build_export(status=ExportStatus.PROCESSING).is_claimable is False
    assert build_export(status=ExportStatus.COMPLETED).is_claimable is False


def test_failing_an_export_discards_any_artifact() -> None:
    completed = build_completed_export(file_path="p/u/a.json", content=b"{}")

    failed = completed.fail(failure_reason="RuntimeError", completed_at=datetime.now(timezone.utc))

    assert failed.artifact is None
    assert failed.is_downloadable is False
    assert failed.event is ExportEvent.EXPORT_FAILED
