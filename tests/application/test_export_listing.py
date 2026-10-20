from uuid import uuid4
from typing import List, Optional
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.entities import DataExport
from app.domain.value_objects import ExportScope
from app.application.dto import ListDataExportsRequestDTO
from app.domain.types import ExportFormat, ExportSection, ExportStatus
from app.application.usecases.exports.list_data_exports import ListDataExportsUseCase


USER_ID = uuid4()
PARTNER_ID = uuid4()
NOW = datetime.now(timezone.utc)


def build_export(requested_minutes_ago: int, status: ExportStatus = ExportStatus.COMPLETED) -> DataExport:
    requested_at = NOW - timedelta(minutes=requested_minutes_ago)

    return DataExport(
        status=status,
        user_id=USER_ID,
        export_id=uuid4(),
        partner_id=PARTNER_ID,
        requested_at=requested_at,
        export_format=ExportFormat.JSON,
        expires_at=requested_at + timedelta(days=1),
        scope=ExportScope(sections=frozenset(ExportSection.canonical_order()))
    )


class FakeExportLister:

    def __init__(self, data_exports: Optional[List[DataExport]] = None) -> None:
        self._data_exports = data_exports or []
        self.calls: List[ListDataExportsRequestDTO] = []

    async def list_by_user(self, list_data_exports_request: ListDataExportsRequestDTO) -> List[DataExport]:
        self.calls.append(list_data_exports_request)

        selected = [
            data_export
            for data_export in self._data_exports
            if list_data_exports_request.status is None
            or data_export.status is list_data_exports_request.status
        ]

        return sorted(selected, key=lambda item: item.requested_at, reverse=True)


class TestListDataExportsUseCase:

    @pytest.mark.asyncio
    async def test_historico_vem_do_mais_recente_para_o_mais_antigo(self) -> None:
        oldest = build_export(requested_minutes_ago=90)
        newest = build_export(requested_minutes_ago=5)

        usecase = ListDataExportsUseCase(export_lister=FakeExportLister([oldest, newest]))

        history = await usecase.execute(
            list_data_exports_request=ListDataExportsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID
            )
        )

        assert [item.export_id for item in history.items] == [newest.export_id, oldest.export_id]
        assert history.total == 2

    @pytest.mark.asyncio
    async def test_usuario_sem_solicitacao_devolve_historico_vazio(self) -> None:
        usecase = ListDataExportsUseCase(export_lister=FakeExportLister())

        history = await usecase.execute(
            list_data_exports_request=ListDataExportsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID
            )
        )

        assert history.items == []
        assert history.is_truncated is False

    @pytest.mark.asyncio
    async def test_limite_trunca_a_lista_e_sinaliza_o_corte(self) -> None:
        exports = [build_export(requested_minutes_ago=minutes) for minutes in (5, 20, 40)]

        usecase = ListDataExportsUseCase(export_lister=FakeExportLister(exports))

        history = await usecase.execute(
            list_data_exports_request=ListDataExportsRequestDTO(
                limit=2,
                user_id=USER_ID,
                partner_id=PARTNER_ID
            )
        )

        assert len(history.items) == 2
        assert history.total == 3
        assert history.is_truncated is True

    @pytest.mark.asyncio
    async def test_filtro_por_estagio_e_repassado_ao_listador(self) -> None:
        pending = build_export(requested_minutes_ago=10, status=ExportStatus.PENDING)
        completed = build_export(requested_minutes_ago=30)

        lister = FakeExportLister([pending, completed])
        usecase = ListDataExportsUseCase(export_lister=lister)

        history = await usecase.execute(
            list_data_exports_request=ListDataExportsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                status=ExportStatus.PENDING
            )
        )

        assert [item.export_id for item in history.items] == [pending.export_id]
        assert lister.calls[0].status is ExportStatus.PENDING
        assert history.status is ExportStatus.PENDING
