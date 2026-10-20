import json
from uuid import UUID
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from app.domain.entities import DataExport
from app.config.logging_setup import logger
from app.infra.cache.redis_client import RedisClient
from app.domain.value_objects import ExportArtifact, ExportScope
from app.domain.types import ExportFormat, ExportSection, ExportStatus
from app.application.dto import GetDataExportRequestDTO, ListDataExportsRequestDTO
from app.application.interfaces import IExportLister, IExportPurger, IExportRegistry


T = TypeVar("T")


class RedisExportRegistry(IExportRegistry, IExportPurger, IExportLister):

    def __init__(self, redis_client: RedisClient, retention_seconds: int) -> None:
        self._scan_batch_size = 200
        self._redis_client = redis_client
        self._retention_seconds = retention_seconds

    async def register(self, data_export: DataExport) -> DataExport:
        await self._write(data_export=data_export, ttl_seconds=self._retention_seconds)

        return data_export

    async def find(self, get_data_export_request: GetDataExportRequestDTO) -> Optional[DataExport]:
        raw = await self._redis_client.cache.get(
            self._key(
                user_id=get_data_export_request.user_id,
                export_id=get_data_export_request.export_id,
                partner_id=get_data_export_request.partner_id
            )
        )

        if raw is None:
            return None

        return self._to_entity_or_none(raw=raw, key=str(get_data_export_request.export_id))

    async def save(self, data_export: DataExport) -> DataExport:
        remaining = int((data_export.expires_at - datetime.now(timezone.utc)).total_seconds())

        if remaining <= 0:
            logger.warning(
                "data_export_state_expired",
                export_id=str(data_export.export_id),
                partner_id=str(data_export.partner_id)
            )

            return data_export

        await self._write(data_export=data_export, ttl_seconds=remaining)

        return data_export

    async def list_by_user(self, list_data_exports_request: ListDataExportsRequestDTO) -> List[DataExport]:
        data_exports: List[DataExport] = []

        async for key in self._redis_client.cache.scan_iter(
                count=self._scan_batch_size,
                match=self._key(
                    export_id="*",
                    user_id=list_data_exports_request.user_id,
                    partner_id=list_data_exports_request.partner_id
                )
        ):
            raw = await self._redis_client.cache.get(key)

            if raw is None:
                continue

            data_export = self._to_entity_or_none(raw=raw, key=key)

            if data_export is None:
                continue

            if list_data_exports_request.status is not None:
                if data_export.status is not list_data_exports_request.status:
                    continue

            data_exports.append(data_export)

        return sorted(data_exports, key=lambda item: item.requested_at, reverse=True)

    async def purge_user(self, partner_id: UUID, user_id: UUID) -> List[str]:
        keys: List[str] = []
        file_paths: List[str] = []

        async for key in self._redis_client.cache.scan_iter(
                count=self._scan_batch_size,
                match=self._key(partner_id=partner_id, user_id=user_id, export_id="*")
        ):
            keys.append(key)

        for key in keys:
            raw = await self._redis_client.cache.get(key)

            if raw is not None:
                data_export = self._to_entity_or_none(raw=raw, key=key)

                if data_export is not None and data_export.artifact is not None:
                    file_paths.append(data_export.artifact.file_path)

            await self._redis_client.cache.delete(key)

        logger.info(
            "data_export_state_purged",
            user_id=str(user_id),
            total_keys=len(keys),
            partner_id=str(partner_id),
            total_artifacts=len(file_paths)
        )

        return file_paths

    async def _write(self, data_export: DataExport, ttl_seconds: int) -> None:
        await self._redis_client.cache.set(
            name=self._key(
                user_id=data_export.user_id,
                export_id=data_export.export_id,
                partner_id=data_export.partner_id
            ),
            ex=ttl_seconds,
            value=json.dumps(self._to_payload(data_export=data_export), ensure_ascii=False)
        )

    @staticmethod
    def _key(partner_id: UUID, user_id: UUID, export_id: Union[UUID, str]) -> str:
        return f"export:{partner_id}:{user_id}:{export_id}"

    @staticmethod
    def _to_payload(data_export: DataExport) -> Dict[str, Any]:
        artifact = data_export.artifact
        scope = data_export.scope

        return {
            "status": data_export.status.value,
            "user_id": str(data_export.user_id),
            "export_id": str(data_export.export_id),
            "partner_id": str(data_export.partner_id),
            "failure_reason": data_export.failure_reason,
            "export_format": data_export.export_format.value,
            "expires_at": data_export.expires_at.isoformat(),
            "requested_at": data_export.requested_at.isoformat(),
            "completed_at": (
                data_export.completed_at.isoformat() if data_export.completed_at is not None else None
            ),
            "scope": {
                "sections": [section.value for section in scope.ordered_sections],
                "end_date": scope.end_date.isoformat() if scope.end_date is not None else None,
                "start_date": scope.start_date.isoformat() if scope.start_date is not None else None
            },
            "artifact": None if artifact is None else {
                "checksum": artifact.checksum,
                "file_path": artifact.file_path,
                "truncated": artifact.truncated,
                "file_name": artifact.file_name,
                "byte_size": artifact.byte_size,
                "media_type": artifact.media_type,
                "total_records": artifact.total_records
            }
        }

    def _to_entity_or_none(self, raw: str, key: str) -> Optional[DataExport]:
        """Converte o registro do armazenamento temporário, tratando conteúdo ilegível como ausente."""
        _ = self

        try:
            return self._to_entity(payload=json.loads(raw))

        except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("data_export_state_unreadable", key=key, error=type(exc).__name__)

            return None

    @classmethod
    def _to_entity(cls, payload: Dict[str, Any]) -> DataExport:
        completed_at: Optional[str] = payload.get("completed_at")
        scope_payload: Dict[str, Any] = payload.get("scope") or {}
        artifact_payload: Optional[Dict[str, Any]] = payload.get("artifact")

        end_date: Optional[str] = scope_payload.get("end_date")
        start_date: Optional[str] = scope_payload.get("start_date")

        scope = ExportScope(
            end_date=date.fromisoformat(end_date) if end_date is not None else None,
            start_date=date.fromisoformat(start_date) if start_date is not None else None,
            sections=frozenset(
                ExportSection(section) for section in scope_payload.get("sections") or []
            )
        )

        return DataExport(
            scope=scope,
            failure_reason=payload.get("failure_reason"),
            user_id=UUID(cls._required(payload=payload, field="user_id", expected=str)),
            export_id=UUID(cls._required(payload=payload, field="export_id", expected=str)),
            partner_id=UUID(cls._required(payload=payload, field="partner_id", expected=str)),
            status=ExportStatus(cls._required(payload=payload, field="status", expected=str)),
            completed_at=datetime.fromisoformat(completed_at) if completed_at is not None else None,
            export_format=ExportFormat(cls._required(payload=payload, field="export_format", expected=str)),
            expires_at=datetime.fromisoformat(cls._required(payload=payload, field="expires_at", expected=str)),
            requested_at=datetime.fromisoformat(cls._required(payload=payload, field="requested_at", expected=str)),
            artifact=None if artifact_payload is None else ExportArtifact(
                checksum=cls._required(payload=artifact_payload, field="checksum", expected=str),
                file_path=cls._required(payload=artifact_payload, field="file_path", expected=str),
                file_name=cls._required(payload=artifact_payload, field="file_name", expected=str),
                byte_size=cls._required(payload=artifact_payload, field="byte_size", expected=int),
                truncated=cls._required(payload=artifact_payload, field="truncated", expected=bool),
                media_type=cls._required(payload=artifact_payload, field="media_type", expected=str),
                total_records=cls._required(payload=artifact_payload, field="total_records", expected=int)
            )
        )

    @staticmethod
    def _required(payload: Dict[str, Any], field: str, expected: Type[T]) -> T:
        """Extrai um campo obrigatório já no tipo esperado, recusando ausência e tipo divergente."""
        value = payload.get(field)

        if not isinstance(value, expected) or isinstance(value, bool) is not (expected is bool):
            raise ValueError(f"Campo '{field}' ausente ou de tipo inesperado no estado da exportação.")

        return value
