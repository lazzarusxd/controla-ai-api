from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer

from app.domain.entities import Asset
from app.domain.types import AssetType
from app.application.dto import AssetCostSummaryDTO, AssetTypeCostDTO


MonetaryAmount = Annotated[
    Decimal,
    Field(ge=0, max_digits=15, decimal_places=2),
    PlainSerializer(float, return_type=float)
]

SignedAmount = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]


class AssetCreateRequest(BaseModel):
    """Corpo do registro de bem patrimonial."""
    asset_type: AssetType = Field(
        default=...,
        description="Natureza do bem. Determina a curva de depreciação aplicada no cálculo do CET: "
                    "veículo deprecia, imóvel não deprecia por padrão.",
        examples=["VEHICLE"]
    )
    description: str = Field(
        default=...,
        max_length=500,
        min_length=1,
        description="Identificação do bem: marca e modelo, endereço do imóvel ou descrição livre.",
        examples=["Fiat Argo Drive 1.3 2022"]
    )
    market_value: MonetaryAmount = Field(
        default=...,
        description="Valor de mercado atualizado do bem, base da depreciação mensal. Não é o valor de aquisição.",
        examples=[68500.00]
    )
    acquisition_date: date = Field(
        default=...,
        description="Data da aquisição declarada. Não pode ser futura.",
        examples=["2022-03-15"]
    )
    annual_taxes: MonetaryAmount = Field(
        default=...,
        description="Carga tributária anual do bem (IPVA para veículos, IPTU para imóveis). Informe o "
                    "valor cheio do exercício: o rateio mensal é responsabilidade da API.",
        examples=[2740.00]
    )


class AssetUpdateRequest(BaseModel):
    """Corpo da atualização parcial. Campos ausentes preservam o valor vigente."""
    asset_type: Optional[AssetType] = Field(
        default=None,
        description="Nova natureza do bem. Alterá-la troca a curva de depreciação e reabre o cálculo do CET.",
        examples=["OTHER"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        min_length=1,
        description="Nova identificação do bem.",
        examples=["Fiat Argo Drive 1.3 2022, placa ABC1D23"]
    )
    market_value: Optional[MonetaryAmount] = Field(
        default=None,
        description="Novo valor de mercado, após reavaliação. Reajustar aqui recalcula a depreciação "
                    "mensal e o CET na mesma operação.",
        examples=[61200.00]
    )
    acquisition_date: Optional[date] = Field(
        default=None,
        description="Correção da data de aquisição declarada.",
        examples=["2022-03-15"]
    )
    annual_taxes: Optional[MonetaryAmount] = Field(
        default=None,
        description="Nova carga tributária anual, tipicamente na virada do exercício fiscal. Recalcula "
                    "a provisão mensal e o CET.",
        examples=[2510.00]
    )


class AssetResponse(BaseModel):
    """Representação de um bem patrimonial com o CET mensal decomposto."""
    asset_id: UUID = Field(
        default=...,
        description="Identificador do bem.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    user_id: UUID = Field(
        default=...,
        description="Usuário final proprietário do bem.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    asset_type: AssetType = Field(
        default=...,
        description="Natureza do bem.",
        examples=["VEHICLE"]
    )
    description: str = Field(
        default=...,
        description="Identificação do bem.",
        examples=["Fiat Argo Drive 1.3 2022"]
    )
    market_value: SignedAmount = Field(
        default=...,
        description="Valor de mercado vigente considerado no cálculo.",
        examples=[68500.00]
    )
    acquisition_date: date = Field(
        default=...,
        description="Data da aquisição declarada.",
        examples=["2022-03-15"]
    )
    annual_taxes: SignedAmount = Field(
        default=...,
        description="Carga tributária anual declarada.",
        examples=[2740.00]
    )
    monthly_tax_provision: SignedAmount = Field(
        default=...,
        description="Primeira parcela do CET: os impostos anuais divididos por doze.",
        examples=[228.33]
    )
    monthly_depreciation: SignedAmount = Field(
        default=...,
        description="Segunda parcela do CET: a taxa mensal do tipo do bem aplicada ao valor de mercado. "
                    "Vale zero quando a natureza do bem não deprecia.",
        examples=[1143.95]
    )
    total_monthly_cost: SignedAmount = Field(
        default=...,
        description="Custo Efetivo Total mensal. É exatamente a soma das duas parcelas acima, invariante "
                    "garantida também no banco por restrição de verificação.",
        examples=[1372.28]
    )
    total_annual_cost: SignedAmount = Field(
        default=...,
        description="Projeção anual do CET, o custo de manter o bem por doze meses.",
        examples=[16467.36]
    )
    age_in_months: int = Field(
        default=...,
        description="Meses completos de posse desde a aquisição declarada.",
        examples=[41]
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
    def from_entity(cls, asset: Asset) -> "AssetResponse":
        return cls(
            user_id=asset.user_id,
            asset_id=asset.asset_id,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            asset_type=asset.asset_type,
            description=asset.description,
            market_value=asset.market_value,
            annual_taxes=asset.annual_taxes,
            acquisition_date=asset.acquisition_date,
            total_annual_cost=asset.total_annual_cost,
            total_monthly_cost=asset.total_monthly_cost,
            monthly_depreciation=asset.monthly_depreciation,
            monthly_tax_provision=asset.monthly_tax_provision,
            age_in_months=asset.age_in_months(reference_date=date.today())
        )


class AssetPageResponse(BaseModel):
    """Página de bens patrimoniais, com os metadados de navegação."""
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
        description="Total de bens que satisfazem o filtro.",
        examples=[3]
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
    items: List[AssetResponse] = Field(
        default=...,
        description="Bens da página, do maior para o menor custo efetivo mensal."
    )


class ListAssetsQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos na listagem de bens."""
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
    asset_type: Optional[AssetType] = Query(
        default=None,
        description="Isola uma natureza de bem. Ausente, devolve o patrimônio inteiro.",
        examples=["VEHICLE"]
    )


class AssetTypeCostResponse(BaseModel):
    """Custo efetivo agregado de uma natureza de bem."""
    asset_type: AssetType = Field(
        default=...,
        description="Natureza do bem agregada.",
        examples=["VEHICLE"]
    )
    total: int = Field(
        default=...,
        description="Quantidade de bens dessa natureza.",
        examples=[1]
    )
    market_value: SignedAmount = Field(
        default=...,
        description="Soma dos valores de mercado da natureza.",
        examples=[68500.00]
    )
    monthly_tax_provision: SignedAmount = Field(
        default=...,
        description="Soma das provisões mensais de imposto da natureza.",
        examples=[228.33]
    )
    monthly_depreciation: SignedAmount = Field(
        default=...,
        description="Soma das depreciações mensais da natureza.",
        examples=[1143.95]
    )
    total_monthly_cost: SignedAmount = Field(
        default=...,
        description="Soma do CET mensal da natureza.",
        examples=[1372.28]
    )

    @classmethod
    def from_dto(cls, asset_type_cost: AssetTypeCostDTO) -> "AssetTypeCostResponse":
        return cls(
            total=asset_type_cost.total,
            asset_type=asset_type_cost.asset_type,
            market_value=asset_type_cost.market_value,
            total_monthly_cost=asset_type_cost.total_monthly_cost,
            monthly_depreciation=asset_type_cost.monthly_depreciation,
            monthly_tax_provision=asset_type_cost.monthly_tax_provision
        )


class AssetCostSummaryResponse(BaseModel):
    """Custo efetivo consolidado do patrimônio do usuário."""
    total_assets: int = Field(
        default=...,
        description="Quantidade de bens registrados.",
        examples=[3]
    )
    total_market_value: SignedAmount = Field(
        default=...,
        description="Valor de mercado somado de todo o patrimônio declarado.",
        examples=[418500.00]
    )
    total_monthly_tax_provision: SignedAmount = Field(
        default=...,
        description="Provisão mensal de impostos de todo o patrimônio.",
        examples=[520.83]
    )
    total_monthly_depreciation: SignedAmount = Field(
        default=...,
        description="Depreciação mensal de todo o patrimônio.",
        examples=[1143.95]
    )
    total_monthly_cost: SignedAmount = Field(
        default=...,
        description="CET mensal consolidado. É o valor que o patrimônio consome do orçamento todo mês, "
                    "mesmo sem nenhum lançamento correspondente no extrato.",
        examples=[1665.38]
    )
    total_annual_cost: SignedAmount = Field(
        default=...,
        description="Projeção anual do CET consolidado.",
        examples=[19984.56]
    )
    computed_at: Optional[datetime] = Field(
        default=...,
        description="Instante da apuração. O consolidado é calculado sob demanda, nunca materializado.",
        examples=[datetime.now()]
    )
    breakdown: List[AssetTypeCostResponse] = Field(
        default=...,
        description="Abertura por natureza de bem, do maior para o menor custo efetivo mensal."
    )

    @classmethod
    def from_dto(cls, cost_summary: AssetCostSummaryDTO) -> "AssetCostSummaryResponse":
        return cls(
            computed_at=cost_summary.computed_at,
            total_assets=cost_summary.total_assets,
            total_annual_cost=cost_summary.total_annual_cost,
            total_monthly_cost=cost_summary.total_monthly_cost,
            total_market_value=cost_summary.total_market_value,
            total_monthly_depreciation=cost_summary.total_monthly_depreciation,
            total_monthly_tax_provision=cost_summary.total_monthly_tax_provision,
            breakdown=[AssetTypeCostResponse.from_dto(item) for item in cost_summary.breakdown]
        )
