from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer

from app.domain.entities import Invoice, MeteringLog
from app.application.dto import InvoicePageDTO, InvoiceStatementDTO
from app.domain.types import BillingActor, InvoiceStatus, PricingSource


Money = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]

UnitPrice = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]

ReferenceMonthPath = Annotated[
    str,
    Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
]


class ListInvoicesQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos na listagem de faturas."""
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


class UsageVolumeResponse(BaseModel):
    """Volumetria medida na competência."""
    api_requests: int = Field(
        default=...,
        description="Requisições autenticadas atendidas. Falhas internas do serviço não entram na conta.",
        examples=[184320]
    )
    llm_tokens_in: int = Field(
        default=...,
        description="Tokens de entrada processados pelos modelos de linguagem.",
        examples=[2410558]
    )
    llm_tokens_out: int = Field(
        default=...,
        description="Tokens de saída gerados pelos modelos de linguagem.",
        examples=[318902]
    )
    ocr_images: int = Field(
        default=...,
        description="Imagens lidas pelo motor de OCR. Cada página renderizada de um PDF conta como uma.",
        examples=[4127]
    )


class DailyUsageResponse(BaseModel):
    """Consumo consolidado de um dia da competência."""
    reference_date: date = Field(
        default=...,
        description="Dia de referência do consumo.",
        examples=[date.today()]
    )
    volume: UsageVolumeResponse = Field(
        default=...,
        description="Volumetria acumulada no dia."
    )
    consolidated_at: datetime = Field(
        default=...,
        description="Última vez que um lote de consumo foi somado a este dia.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_entity(cls, metering_log: MeteringLog) -> "DailyUsageResponse":
        return cls(
            reference_date=metering_log.reference_date,
            consolidated_at=metering_log.consolidated_at,
            volume=UsageVolumeResponse(**metering_log.volume.as_counters())
        )


class PricingResponse(BaseModel):
    """Tabela tarifária aplicada, copiada para a fatura no fechamento."""
    source: PricingSource = Field(
        default=...,
        description="`CONTRACT` para tabela negociada do parceiro, `LIST_PRICE` para a tabela de balcão.",
        examples=[PricingSource.CONTRACT]
    )
    plan_id: Optional[UUID] = Field(
        default=...,
        description="Versão do contrato aplicada. Nulo quando a cobrança seguiu a tabela de balcão.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    base_monthly_fee: Money = Field(
        default=...,
        description="Taxa base mensal de licenciamento. Não é proporcional ao tempo de uso no mês.",
        examples=[499.00]
    )
    price_per_thousand_requests: UnitPrice = Field(
        default=...,
        description="Preço por mil requisições.",
        examples=[2.50]
    )
    price_per_million_tokens_in: UnitPrice = Field(
        default=...,
        description="Preço por milhão de tokens de entrada.",
        examples=[4.00]
    )
    price_per_million_tokens_out: UnitPrice = Field(
        default=...,
        description="Preço por milhão de tokens de saída.",
        examples=[16.00]
    )
    price_per_ocr_image: UnitPrice = Field(
        default=...,
        description="Preço por imagem processada pelo OCR.",
        examples=[0.08]
    )


class ChargesResponse(BaseModel):
    """Componentes da cobrança híbrida, cada um arredondado ao centavo."""
    base_fee: Money = Field(
        default=...,
        description="Parcela fixa de licenciamento.",
        examples=[499.00]
    )
    api_fee: Money = Field(
        default=...,
        description="Parcela por volumetria de requisições.",
        examples=[460.80]
    )
    llm_fee: Money = Field(
        default=...,
        description="Parcela por tokens processados, somando entrada e saída antes do arredondamento.",
        examples=[14.74]
    )
    ocr_fee: Money = Field(
        default=...,
        description="Parcela por imagens processadas pelo OCR.",
        examples=[330.16]
    )
    total: Money = Field(
        default=...,
        description="Soma dos componentes já arredondados, que é o valor devido da competência.",
        examples=[1304.70]
    )


class InvoiceResponse(BaseModel):
    """Fatura da competência: documento emitido ou prévia do que está sendo acumulado."""
    reference_month: str = Field(
        default=...,
        description="Competência no formato `YYYY-MM`.",
        examples=["2026-08"]
    )
    status: InvoiceStatus = Field(
        default=...,
        description="`CLOSED` para documento emitido e imutável, `OPEN` para prévia da competência em curso.",
        examples=[InvoiceStatus.CLOSED]
    )
    is_preview: bool = Field(
        default=...,
        description="Indica cálculo feito na leitura, que ainda pode mudar até o fechamento.",
        examples=[False]
    )
    invoice_id: Optional[UUID] = Field(
        default=...,
        description="Identificador do documento. Nulo na prévia, que não é persistida.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    volume: UsageVolumeResponse = Field(
        default=...,
        description="Volumetria da competência."
    )
    pricing: PricingResponse = Field(
        default=...,
        description="Tabela tarifária aplicada."
    )
    charges: ChargesResponse = Field(
        default=...,
        description="Composição do valor devido."
    )
    closed_at: Optional[datetime] = Field(
        default=...,
        description="Instante do fechamento. Nulo enquanto a competência não foi fechada.",
        examples=[datetime.now()]
    )
    closed_by: Optional[BillingActor] = Field(
        default=...,
        description="Origem do fechamento: `PARTNER` pela rota, `SCHEDULER` pela rotina de virada de mês.",
        examples=[BillingActor.SCHEDULER]
    )
    daily: List[DailyUsageResponse] = Field(
        default=...,
        description="Consumo dia a dia da competência, em ordem cronológica."
    )

    @classmethod
    def from_dto(cls, invoice_statement: InvoiceStatementDTO) -> "InvoiceResponse":
        pricing = invoice_statement.pricing
        charges = invoice_statement.charges

        return cls(
            status=invoice_statement.status,
            closed_at=invoice_statement.closed_at,
            closed_by=invoice_statement.closed_by,
            invoice_id=invoice_statement.invoice_id,
            is_preview=invoice_statement.is_preview,
            reference_month=str(invoice_statement.reference_month),
            volume=UsageVolumeResponse(**invoice_statement.volume.as_counters()),
            daily=[DailyUsageResponse.from_entity(item) for item in invoice_statement.daily],
            charges=ChargesResponse(
                total=charges.total,
                api_fee=charges.api_fee,
                llm_fee=charges.llm_fee,
                ocr_fee=charges.ocr_fee,
                base_fee=charges.base_fee
            ),
            pricing=PricingResponse(
                source=pricing.source,
                plan_id=pricing.plan_id,
                base_monthly_fee=pricing.base_monthly_fee,
                price_per_ocr_image=pricing.price_per_ocr_image,
                price_per_thousand_requests=pricing.price_per_thousand_requests,
                price_per_million_tokens_in=pricing.price_per_million_tokens_in,
                price_per_million_tokens_out=pricing.price_per_million_tokens_out
            )
        )


class InvoiceSummaryResponse(BaseModel):
    """Fatura fechada, na visão resumida do histórico."""
    invoice_id: UUID = Field(
        default=...,
        description="Identificador do documento.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    reference_month: str = Field(
        default=...,
        description="Competência no formato `YYYY-MM`.",
        examples=["2026-08"]
    )
    total: Money = Field(
        default=...,
        description="Valor devido da competência.",
        examples=[1304.70]
    )
    closed_at: Optional[datetime] = Field(
        default=...,
        description="Instante do fechamento.",
        examples=[datetime.now()]
    )
    closed_by: Optional[BillingActor] = Field(
        default=...,
        description="Origem do fechamento.",
        examples=[BillingActor.SCHEDULER]
    )
    pricing_source: PricingSource = Field(
        default=...,
        description="Procedência da tabela aplicada.",
        examples=[PricingSource.CONTRACT]
    )

    @classmethod
    def from_entity(cls, invoice: Invoice) -> "InvoiceSummaryResponse":
        return cls(
            total=invoice.total,
            closed_at=invoice.closed_at,
            closed_by=invoice.closed_by,
            invoice_id=invoice.invoice_id,
            pricing_source=invoice.pricing.source,
            reference_month=str(invoice.reference_month)
        )


class InvoicePageResponse(BaseModel):
    """Página do histórico de faturas fechadas."""
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
        description="Total de faturas fechadas do parceiro.",
        examples=[7]
    )
    total_pages: int = Field(
        default=...,
        description="Total de páginas para o tamanho informado.",
        examples=[1]
    )
    has_next_page: bool = Field(
        default=...,
        description="Indica se existe página seguinte.",
        examples=[False]
    )
    items: List[InvoiceSummaryResponse] = Field(
        default=...,
        description="Faturas da página, da competência mais recente para a mais antiga."
    )

    @classmethod
    def from_dto(cls, invoice_page: InvoicePageDTO) -> "InvoicePageResponse":
        return cls(
            page=invoice_page.page,
            total=invoice_page.total,
            page_size=invoice_page.page_size,
            total_pages=invoice_page.total_pages,
            has_next_page=invoice_page.page < invoice_page.total_pages,
            items=[InvoiceSummaryResponse.from_entity(item) for item in invoice_page.items]
        )
