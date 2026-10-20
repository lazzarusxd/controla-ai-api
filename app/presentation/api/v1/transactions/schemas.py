from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer, model_validator

from app.domain.entities import Transaction
from app.domain.types import ReviewDecision, TransactionStatus, TransactionType


MonetaryAmount = Annotated[
    Decimal,
    Field(gt=0, max_digits=15, decimal_places=2),
    PlainSerializer(float, return_type=float)
]

SignedAmount = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]

ConfidenceScore = Annotated[
    Decimal,
    Field(ge=0, le=1),
    PlainSerializer(float, return_type=float)
]


class TransactionCreateRequest(BaseModel):
    """Corpo da criação de lançamento."""
    type: TransactionType = Field(
        default=...,
        description="Natureza do lançamento.",
        examples=[TransactionType.EXPENSE]
    )
    amount: MonetaryAmount = Field(
        default=...,
        description="Valor absoluto. A direção do fluxo vem de `type`.",
        examples=[189.90]
    )
    category: str = Field(
        default=...,
        max_length=100,
        min_length=1,
        description="Categoria do plano de contas.",
        examples=["Alimentação"]
    )
    description: str = Field(
        default=...,
        max_length=500,
        min_length=1,
        description="Descrição livre do lançamento.",
        examples=["Mercado - compra da semana"]
    )
    transaction_date: date = Field(
        default=...,
        description="Data do fato gerador.",
        examples=[date.today()]
    )
    status: TransactionStatus = Field(
        default=TransactionStatus.SETTLED,
        description="`SETTLED` entra no saldo de caixa. `PENDING` fica restrito à projeção.",
        examples=[TransactionStatus.SETTLED]
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Vencimento. Exigido em `PENDING`, proibido em `SETTLED`.",
        examples=[date.today()]
    )

    @model_validator(mode="after")
    def _validate_regime_coherence(self) -> "TransactionCreateRequest":
        if self.status is TransactionStatus.PENDING and self.due_date is None:
            raise ValueError("Lançamento PENDING exige due_date para compor o regime de competência.")

        if self.status is TransactionStatus.SETTLED and self.due_date is not None:
            raise ValueError("Lançamento liquidado não admite due_date: ele já pertence ao regime de caixa.")

        return self


class TransactionUpdateRequest(BaseModel):
    """Corpo da atualização parcial. Campos ausentes preservam o valor vigente."""
    type: Optional[TransactionType] = Field(
        default=None,
        description="Nova natureza do lançamento.",
        examples=[TransactionType.EXPENSE]
    )
    amount: Optional[MonetaryAmount] = Field(
        default=None,
        description="Novo valor absoluto.",
        examples=[189.90]
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        min_length=1,
        description="Nova categoria.",
        examples=["Alimentação"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        min_length=1,
        description="Nova descrição.",
        examples=["Mercado - compra da semana"]
    )
    transaction_date: Optional[date] = Field(
        default=None,
        description="Nova data do fato gerador.",
        examples=[date.today()]
    )
    status: Optional[TransactionStatus] = Field(
        default=None,
        description="Nova transição de estado. `CANCELED` é terminal.",
        examples=[TransactionStatus.CANCELED]
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Novo vencimento. `null` explícito remove o atual.",
        examples=[date.today()]
    )


class TransactionResponse(BaseModel):
    """Representação de um lançamento."""
    transaction_id: UUID = Field(
        default=...,
        description="Identificador do lançamento.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    user_id: UUID = Field(
        default=...,
        description="Usuário final proprietário do lançamento.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    type: TransactionType = Field(
        default=...,
        description="Natureza do lançamento.",
        examples=[TransactionType.EXPENSE]
    )
    amount: SignedAmount = Field(
        default=...,
        description="Valor absoluto. A direção do fluxo vem de `type`.",
        examples=[189.90]
    )
    category: str = Field(
        default=...,
        description="Categoria do plano de contas.",
        examples=["Alimentação"]
    )
    description: str = Field(
        default=...,
        description="Descrição livre do lançamento.",
        examples=["Mercado - compra da semana"]
    )
    transaction_date: date = Field(
        default=...,
        description="Data do fato gerador.",
        examples=[date.today()]
    )
    due_date: Optional[date] = Field(
        default=...,
        description="Vencimento. Nulo em lançamentos liquidados.",
        examples=[date.today()]
    )
    status: TransactionStatus = Field(
        default=...,
        description="Estado contábil do lançamento.",
        examples=[TransactionStatus.SETTLED]
    )
    pending_review: bool = Field(
        default=...,
        description="Extração de OCR abaixo do limiar. Fica fora do saldo oficial.",
        examples=[False]
    )
    confidence_score: Optional[ConfidenceScore] = Field(
        default=...,
        description="Confiança da extração, de 0 a 1. Nulo em lançamento manual.",
        examples=[0.93]
    )
    receipt_id: Optional[UUID] = Field(
        default=...,
        description="Comprovante de origem. Nulo em lançamento manual.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    created_at: datetime = Field(
        default=...,
        description="Instante do registro.",
        examples=[datetime.now()]
    )
    updated_at: Optional[datetime] = Field(
        default=...,
        description="Instante da última alteração. Nulo se nunca alterado.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_entity(cls, transaction: Transaction) -> "TransactionResponse":
        return cls(
            type=transaction.type,
            amount=transaction.amount,
            status=transaction.status,
            user_id=transaction.user_id,
            due_date=transaction.due_date,
            category=transaction.category,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
            receipt_id=transaction.receipt_id,
            description=transaction.description,
            pending_review=transaction.pending_review,
            transaction_id=transaction.transaction_id,
            confidence_score=transaction.confidence_score,
            transaction_date=transaction.transaction_date
        )


class TransactionPageResponse(BaseModel):
    """Página do extrato, com os metadados de navegação."""
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
        description="Total de lançamentos que satisfazem o filtro.",
        examples=[340]
    )
    total_pages: int = Field(
        default=...,
        description="Total de páginas para o filtro e o tamanho informados.",
        examples=[7]
    )
    has_next_page: bool = Field(
        default=...,
        description="Indica se existe página seguinte.",
        examples=[True]
    )
    items: List[TransactionResponse] = Field(
        default=...,
        description="Lançamentos da página, do mais recente ao mais antigo."
    )


class ListTransactionQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos na listagem de transações."""
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
    transaction_type: Optional[TransactionType] = Query(
        default=None,
        alias="type",
        description="Filtra por natureza do lançamento.",
        examples=[TransactionType.EXPENSE]
    )
    transaction_status: Optional[TransactionStatus] = Query(
        default=None,
        alias="status",
        description="Filtra por estado contábil.",
        examples=[TransactionStatus.SETTLED]
    )
    category: Optional[str] = Query(
        default=None,
        max_length=100,
        description="Filtra por categoria.",
        examples=["Alimentação"]
    )
    pending_review: Optional[bool] = Query(
        default=None,
        description="Isola os lançamentos pendentes de revisão manual.",
        examples=[True]
    )
    start_date: Optional[date] = Query(
        default=None,
        description="Data inicial, inclusiva.",
        examples=[date.today()]
    )
    end_date: Optional[date] = Query(
        default=None,
        description="Data final, inclusiva.",
        examples=[date.today()]
    )


class ConsolidatedBalanceResponse(BaseModel):
    """Saldo consolidado com os dois regimes contábeis explicitamente separados."""
    current_balance: SignedAmount = Field(
        default=...,
        description="Regime de caixa: apenas lançamentos liquidados e não pendentes de revisão.",
        examples=[3200.00]
    )
    settled_income: SignedAmount = Field(
        default=...,
        description="Receitas liquidadas no período.",
        examples=[5000.00]
    )
    settled_expense: SignedAmount = Field(
        default=...,
        description="Despesas liquidadas no período.",
        examples=[1800.00]
    )
    pending_income: SignedAmount = Field(
        default=...,
        description="Receitas a receber dentro do horizonte de projeção.",
        examples=[300.00]
    )
    pending_expense: SignedAmount = Field(
        default=...,
        description="Despesas a vencer dentro do horizonte de projeção.",
        examples=[1200.00]
    )
    projected_balance: SignedAmount = Field(
        default=...,
        description="Regime de competência: caixa mais o que está em aberto. Projeção, não disponibilidade.",
        examples=[2300.00]
    )
    projection_until: Optional[date] = Field(
        default=None,
        description="Limite da projeção. Nulo considera todo o saldo em aberto.",
        examples=[date.today()]
    )
    reference_date: datetime = Field(
        default=...,
        description="Instante da apuração.",
        examples=[datetime.now()]
    )


class GetConsolidatedBalanceQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos na apuração do saldo consolidado."""
    start_date: Optional[date] = Query(
        default=None,
        description="Data inicial da apuração, inclusiva.",
        examples=[date.today()]
    )
    end_date: Optional[date] = Query(
        default=None,
        description="Data final da apuração, inclusiva.",
        examples=[date.today()]
    )
    projection_until: Optional[date] = Query(
        default=None,
        description="Horizonte do regime de competência. Ausente, projeta todo o saldo em aberto.",
        examples=[date.today()]
    )


class TransactionReviewRequest(BaseModel):
    """Corpo da revisão manual de lançamento extraído com baixa confiança."""
    decision: ReviewDecision = Field(
        default=...,
        description="`APPROVE` devolve o lançamento aos regimes contábeis. `REJECT` o leva a `CANCELED`.",
        examples=[ReviewDecision.APPROVE]
    )
    type: Optional[TransactionType] = Field(
        default=None,
        description="Correção da natureza inferida pelo modelo.",
        examples=[TransactionType.EXPENSE]
    )
    amount: Optional[MonetaryAmount] = Field(
        default=None,
        description="Correção do valor lido no comprovante.",
        examples=[189.90]
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        min_length=1,
        description="Correção da categoria atribuída.",
        examples=["Alimentação"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        min_length=1,
        description="Correção da descrição gerada.",
        examples=["Supermercado Central - compra da semana"]
    )
    transaction_date: Optional[date] = Field(
        default=None,
        description="Correção da data do fato gerador.",
        examples=[date.today()]
    )
    status: Optional[TransactionStatus] = Field(
        default=None,
        description="Regime do lançamento aprovado. Ignorado quando a decisão é `REJECT`.",
        examples=[TransactionStatus.SETTLED]
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Vencimento, quando o lançamento aprovado permanecer em `PENDING`.",
        examples=[date.today()]
    )
