from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer

from app.domain.entities import Receipt
from app.domain.types import ReceiptStatus


ConfidenceScore = Annotated[
    Decimal,
    Field(ge=0, le=1),
    PlainSerializer(float, return_type=float)
]


class ReceiptAcceptedResponse(BaseModel):
    """Confirmação de recebimento do comprovante, antes de qualquer extração."""
    receipt_id: UUID = Field(
        default=...,
        description="Identificador do comprovante, usado para acompanhar o processamento.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    status: ReceiptStatus = Field(
        default=...,
        description="Estágio no instante da resposta. Sempre `UPLOADED` aqui.",
        examples=[ReceiptStatus.UPLOADED]
    )
    file_type: str = Field(
        default=...,
        description="Tipo MIME aceito.",
        examples=["image/jpeg"]
    )
    file_size_bytes: int = Field(
        default=...,
        description="Tamanho do arquivo recebido.",
        examples=[284915]
    )
    created_at: datetime = Field(
        default=...,
        description="Instante do recebimento.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_entity(cls, receipt: Receipt) -> "ReceiptAcceptedResponse":
        return cls(
            status=receipt.status,
            file_type=receipt.file_type,
            created_at=receipt.created_at,
            receipt_id=receipt.receipt_id,
            file_size_bytes=receipt.file_size_bytes
        )


class ReceiptResponse(BaseModel):
    """Estado do comprovante e do que dele foi extraído."""
    receipt_id: UUID = Field(
        default=...,
        description="Identificador do comprovante.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    user_id: UUID = Field(
        default=...,
        description="Usuário final que enviou o comprovante.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    status: ReceiptStatus = Field(
        default=...,
        description="`UPLOADED` aguarda o worker, `PROCESSING` está em extração, `COMPLETED` gerou "
                    "lançamento e `FAILED` encerrou sem gerar nenhum.",
        examples=[ReceiptStatus.COMPLETED]
    )
    file_type: str = Field(
        default=...,
        description="Tipo MIME do arquivo original.",
        examples=["application/pdf"]
    )
    file_size_bytes: int = Field(
        default=...,
        description="Tamanho do arquivo original.",
        examples=[284915]
    )
    confidence_score: Optional[ConfidenceScore] = Field(
        default=...,
        description="Índice composto entre a leitura óptica e a validação semântica. Abaixo do limiar "
                    "de confiança, o lançamento nasce pendente de revisão. Nulo enquanto não processado.",
        examples=[0.91]
    )
    raw_text: Optional[str] = Field(
        default=...,
        description="Texto bruto devolvido pelo OCR. Nulo enquanto não processado.",
        examples=["SUPERMERCADO CENTRAL LTDA CNPJ 12.345.678/0001-90 TOTAL R$ 189,90 12/08/2026"]
    )
    processed_at: Optional[datetime] = Field(
        default=...,
        description="Instante do encerramento do pipeline. Nulo enquanto em andamento.",
        examples=[datetime.now()]
    )
    created_at: datetime = Field(
        default=...,
        description="Instante do recebimento.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_entity(cls, receipt: Receipt) -> "ReceiptResponse":
        return cls(
            status=receipt.status,
            user_id=receipt.user_id,
            raw_text=receipt.raw_text,
            file_type=receipt.file_type,
            receipt_id=receipt.receipt_id,
            created_at=receipt.created_at,
            processed_at=receipt.processed_at,
            file_size_bytes=receipt.file_size_bytes,
            confidence_score=receipt.confidence_score
        )


class ReceiptPageResponse(BaseModel):
    """Página do extrato de comprovantes."""
    page: int = Field(
        default=...,
        description="Página corrente.",
        examples=[1]
    )
    page_size: int = Field(
        default=...,
        description="Itens por página.",
        examples=[50]
    )
    total: int = Field(
        default=...,
        description="Total de comprovantes que satisfazem o filtro.",
        examples=[27]
    )
    total_pages: int = Field(
        default=...,
        description="Total de páginas para o filtro e o tamanho informados.",
        examples=[1]
    )
    has_next_page: bool = Field(
        default=...,
        description="Indica se existe página seguinte.",
        examples=[False]
    )
    items: List[ReceiptResponse] = Field(
        default=...,
        description="Comprovantes da página, do mais recente ao mais antigo."
    )


class ListReceiptsQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos na listagem de comprovantes."""
    page: int = Query(
        default=1,
        ge=1,
        description="Página desejada.",
        examples=[1]
    )
    page_size: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Itens por página.",
        examples=[50]
    )
    receipt_status: Optional[ReceiptStatus] = Query(
        default=None,
        alias="status",
        description="Isola um estágio do pipeline. Útil para reprocessar o que falhou.",
        examples=[ReceiptStatus.FAILED]
    )
