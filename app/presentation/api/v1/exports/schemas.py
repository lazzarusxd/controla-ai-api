from uuid import UUID
from typing import List, Optional
from datetime import date, datetime

from fastapi import Query
from pydantic import BaseModel, Field

from app.domain.entities import DataExport
from app.application.dto import DataExportHistoryDTO
from app.domain.types import ExportFormat, ExportSection, ExportStatus


class ListDataExportsQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos no histórico de solicitações."""
    status: Optional[ExportStatus] = Query(
        default=None,
        description="Restringe o histórico a um estágio. Ausente, devolve todas as solicitações vivas.",
        examples=[ExportStatus.COMPLETED]
    )
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Trunca a lista às solicitações mais recentes. `is_truncated` sinaliza quando o "
                    "corte foi do limite, e não do fim da janela de retenção.",
        examples=[50]
    )


class RequestDataExportRequest(BaseModel):
    """Corpo da solicitação de exportação."""
    format: ExportFormat = Field(
        default=...,
        description="Formato do artefato. `JSON` e `CSV` são os formatos de portabilidade, sempre íntegros. "
                    "`PDF` é relatório legível e admite truncamento por seção, sinalizado na resposta.",
        examples=["JSON"]
    )
    sections: Optional[List[ExportSection]] = Field(
        default=None,
        description="Seções que compõem o dossiê. Ausente, exporta tudo. Uma lista explicitamente vazia é "
                    "recusada: exportação sem conteúdo não é pedido legítimo.",
        examples=[["TRANSACTIONS", "RECEIPTS"]]
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Início da janela apurada. Incide apenas sobre lançamentos e comprovantes, que são "
                    "histórico datado. Perfil, recorrências, patrimônio e metas são estado corrente e "
                    "viajam inteiros: filtrar estado por janela devolveria um retrato falso.",
        examples=["2026-01-01"]
    )
    end_date: Optional[date] = Field(
        default=None,
        description="Fim da janela apurada, inclusivo.",
        examples=["2026-03-31"]
    )


class ExportScopeResponse(BaseModel):
    """Recorte efetivamente aplicado à exportação."""
    sections: List[ExportSection] = Field(
        default=...,
        description="Seções apuradas, em ordem canônica.",
        examples=[["PROFILE", "TRANSACTIONS"]]
    )
    start_date: Optional[date] = Field(
        default=...,
        description="Início da janela. Nulo quando a apuração cobriu todo o histórico.",
        examples=["2026-01-01"]
    )
    end_date: Optional[date] = Field(
        default=...,
        description="Fim da janela. Nulo quando a apuração foi até o registro mais recente.",
        examples=["2026-03-31"]
    )


class ExportArtifactResponse(BaseModel):
    """Atributos do arquivo gerado."""
    file_name: str = Field(
        default=...,
        description="Nome sugerido no `Content-Disposition` da retirada.",
        examples=["controla-ai-export-0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44-20260823101500.json"]
    )
    media_type: str = Field(
        default=...,
        description="Tipo de mídia devolvido na retirada. CSV de seção única sai como `text/csv`; "
                    "de várias seções, como `application/zip`.",
        examples=["application/json"]
    )
    byte_size: int = Field(
        default=...,
        description="Tamanho do artefato em bytes.",
        examples=[184320]
    )
    checksum: str = Field(
        default=...,
        description="Resumo SHA-256 do conteúdo, em hexadecimal. Repetido como `ETag` na retirada, o que "
                    "permite ao parceiro provar que recebeu exatamente o que foi apurado.",
        examples=["9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"]
    )
    total_records: int = Field(
        default=...,
        description="Registros apurados no pacote, somando todas as seções.",
        examples=[1842]
    )
    truncated: bool = Field(
        default=...,
        description="Indica que ao menos uma seção foi cortada na montagem. Só ocorre em `PDF`.",
        examples=[False]
    )


class DataExportResponse(BaseModel):
    """Estado corrente de uma exportação."""
    export_id: UUID = Field(
        default=...,
        description="Identificador da exportação, devolvido no aceite.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    user_id: UUID = Field(
        default=...,
        description="Titular dos dados exportados.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    status: ExportStatus = Field(
        default=...,
        description="Estágio da geração. Enquanto for `PENDING` ou `PROCESSING`, o artefato ainda não "
                    "existe e `artifact` permanece nulo.",
        examples=["PENDING"]
    )
    format: ExportFormat = Field(
        default=...,
        description="Formato solicitado.",
        examples=["JSON"]
    )
    requested_at: datetime = Field(
        default=...,
        description="Instante do aceite.",
        examples=[datetime.now()]
    )
    expires_at: datetime = Field(
        default=...,
        description="Prazo de retenção. Metadado e artefato expiram juntos: passado esse instante, a "
                    "consulta devolve 404 e a exportação precisa ser refeita.",
        examples=[datetime.now()]
    )
    completed_at: Optional[datetime] = Field(
        default=...,
        description="Instante do desfecho, em sucesso ou em falha. Nulo enquanto a geração não termina.",
        examples=[datetime.now()]
    )
    failure_reason: Optional[str] = Field(
        default=...,
        description="Classe do erro que interrompeu a geração. Nulo fora de `FAILED`. Não expõe detalhe "
                    "interno, apenas o suficiente para o integrador decidir entre repetir e abrir chamado.",
        examples=[None]
    )
    scope: ExportScopeResponse = Field(
        default=...,
        description="Recorte aplicado, devolvido para que o integrador saiba sob qual escopo o artefato "
                    "foi montado sem guardar a requisição original."
    )
    artifact: Optional[ExportArtifactResponse] = Field(
        default=...,
        description="Atributos do arquivo. Nulo até a conclusão."
    )

    @classmethod
    def from_entity(cls, data_export: DataExport) -> "DataExportResponse":
        artifact = data_export.artifact

        return cls(
            status=data_export.status,
            user_id=data_export.user_id,
            export_id=data_export.export_id,
            format=data_export.export_format,
            expires_at=data_export.expires_at,
            requested_at=data_export.requested_at,
            completed_at=data_export.completed_at,
            failure_reason=data_export.failure_reason,
            scope=ExportScopeResponse(
                end_date=data_export.scope.end_date,
                start_date=data_export.scope.start_date,
                sections=data_export.scope.ordered_sections
            ),
            artifact=None if artifact is None else ExportArtifactResponse(
                checksum=artifact.checksum,
                truncated=artifact.truncated,
                file_name=artifact.file_name,
                byte_size=artifact.byte_size,
                media_type=artifact.media_type,
                total_records=artifact.total_records
            )
        )


class DataExportHistoryResponse(BaseModel):
    """Histórico de solicitações de exportação do titular, limitado à janela de retenção."""
    total: int = Field(
        default=...,
        description="Solicitações vivas que satisfazem o filtro, antes do truncamento por `limit`.",
        examples=[3]
    )
    limit: int = Field(
        default=...,
        description="Limite aplicado à lista devolvida.",
        examples=[50]
    )
    status: Optional[ExportStatus] = Field(
        default=...,
        description="Ecoa o filtro recebido, para que o consumidor distinga histórico completo de recorte.",
        examples=[ExportStatus.COMPLETED]
    )
    is_truncated: bool = Field(
        default=...,
        description="Indica que a lista foi cortada pelo limite pedido, e não pelo fim da retenção.",
        examples=[False]
    )
    items: List[DataExportResponse] = Field(
        default=...,
        description="Solicitações da mais recente para a mais antiga."
    )

    @classmethod
    def from_dto(cls, data_export_history: DataExportHistoryDTO) -> "DataExportHistoryResponse":
        return cls(
            total=data_export_history.total,
            limit=data_export_history.limit,
            status=data_export_history.status,
            is_truncated=data_export_history.is_truncated,
            items=[DataExportResponse.from_entity(item) for item in data_export_history.items]
        )
