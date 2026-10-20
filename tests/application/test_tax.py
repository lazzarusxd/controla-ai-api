from uuid import uuid4
from decimal import Decimal
from typing import List, Optional, Tuple
from datetime import date, datetime, timezone

import pytest

from app.domain.entities import TaxDeduction, Transaction
from app.domain.types import TaxDeductionCategory, TaxableIncomeSource
from app.application.usecases.tax.get_tax_deductions import GetTaxDeductionsUseCase
from app.application.services.tax_consolidation_service import TaxConsolidationService
from app.application.usecases.tax.get_refund_projection import GetRefundProjectionUseCase
from app.application.usecases.tax.recalculate_tax_deductions import RecalculateTaxDeductionsUseCase
from app.domain.exceptions.tax_exceptions import (
    InvalidFiscalYearError,
    TaxOwnerNotFoundError,
    TaxableIncomeUnavailableError
)
from app.domain.value_objects import (
    TaxPolicy,
    CategoryVolume,
    MonthlyNetFlow,
    CategoryDeduction,
    RefundProjection,
    ConsolidatedBalance,
    ProgressiveTaxTable,
    normalize_label
)
from app.application.dto import (
    GetTransactionRequestDTO,
    SavingsCapacityRequestDTO,
    RefundProjectionRequestDTO,
    ExpenseOffendersRequestDTO,
    ListTransactionsRequestDTO,
    ListTaxDeductionsRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    TaxConsolidationCandidateDTO,
    ConsolidatedBalanceRequestDTO,
    PersistTaxDeductionsRequestDTO,
    StaleTaxConsolidationRequestDTO,
    RecalculateTaxDeductionsRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()
FISCAL_YEAR = date.today().year

BRACKETS = [
    f"{FISCAL_YEAR}:26963.20:0:0",
    f"{FISCAL_YEAR}:33919.80:0.075:2022.24",
    f"{FISCAL_YEAR}:45012.60:0.15:4566.23",
    f"{FISCAL_YEAR}:55976.16:0.225:7942.17",
    f"{FISCAL_YEAR}::0.275:10740.98"
]

TABLE = ProgressiveTaxTable.build(entries=BRACKETS)

POLICY = TaxPolicy.build(
    table=TABLE,
    unlimited_ceiling=Decimal("9999999999999.99"),
    education_ceiling_by_year={FISCAL_YEAR: Decimal("3561.50")},
    health_categories=["Saúde", "Plano de Saúde", "Odontologia"],
    education_categories=["Educação", "Mensalidade Escolar"]
)


def build_volume(category: str, amount: str, total: int = 1) -> CategoryVolume:
    return CategoryVolume(total=total, category=category, amount=Decimal(amount))


def build_deduction(
        total_amount: str,
        legal_ceiling: str,
        category: TaxDeductionCategory,
        updated_at: Optional[datetime] = None
) -> TaxDeduction:
    total = Decimal(total_amount)
    ceiling = Decimal(legal_ceiling)

    return TaxDeduction(
        user_id=USER_ID,
        category=category,
        total_amount=total,
        deduction_id=uuid4(),
        updated_at=updated_at,
        partner_id=PARTNER_ID,
        legal_ceiling=ceiling,
        fiscal_year=FISCAL_YEAR,
        eligible_amount=min(total, ceiling),
        created_at=datetime.now(timezone.utc)
    )


class FakeTransactionRepository:

    def __init__(
            self,
            balance: Optional[ConsolidatedBalance] = None,
            volumes: Optional[List[CategoryVolume]] = None
    ) -> None:
        self._volumes = volumes or []
        self.aggregate_calls: List[ExpenseOffendersRequestDTO] = []
        self.summarize_calls: List[ConsolidatedBalanceRequestDTO] = []
        self._balance = balance or ConsolidatedBalance(
            settled_income=Decimal("0.00"),
            pending_income=Decimal("0.00"),
            settled_expense=Decimal("0.00"),
            pending_expense=Decimal("0.00")
        )

    async def create(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        raise NotImplementedError

    async def find_by_id(self, get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        raise NotImplementedError

    async def list_by_filter(
            self,
            list_transactions_request: ListTransactionsRequestDTO
    ) -> Tuple[List[Transaction], int]:
        raise NotImplementedError

    async def update(self, update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        raise NotImplementedError

    async def delete(self, delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        raise NotImplementedError

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        self.summarize_calls.append(consolidated_balance_request)

        return self._balance

    async def aggregate_expense_by_category(
            self,
            expense_offenders_request: ExpenseOffendersRequestDTO
    ) -> List[CategoryVolume]:
        self.aggregate_calls.append(expense_offenders_request)

        return list(self._volumes)

    async def aggregate_monthly_net_flow(
            self,
            savings_capacity_request: SavingsCapacityRequestDTO
    ) -> List[MonthlyNetFlow]:
        raise NotImplementedError


class FakeTaxDeductionRepository:

    def __init__(
            self,
            deductions: Optional[List[TaxDeduction]] = None,
            user_exists: bool = True,
            candidates: Optional[List[TaxConsolidationCandidateDTO]] = None
    ) -> None:
        self._user_exists = user_exists
        self._candidates = candidates or []
        self._deductions = deductions or []
        self.persisted: List[PersistTaxDeductionsRequestDTO] = []

    async def list_by_year(self, list_tax_deductions_request: ListTaxDeductionsRequestDTO) -> List[TaxDeduction]:
        return [
            deduction for deduction in self._deductions
            if deduction.fiscal_year == list_tax_deductions_request.fiscal_year
        ]

    async def replace(self, persist_tax_deductions_request: PersistTaxDeductionsRequestDTO) -> List[TaxDeduction]:
        self.persisted.append(persist_tax_deductions_request)

        self._deductions = [
            build_deduction(
                category=entry.category,
                total_amount=str(entry.total_amount),
                legal_ceiling=str(entry.legal_ceiling)
            )
            for entry in persist_tax_deductions_request.entries
        ]

        return list(self._deductions)

    async def list_stale_candidates(
            self,
            stale_tax_consolidation_request: StaleTaxConsolidationRequestDTO
    ) -> List[TaxConsolidationCandidateDTO]:
        _ = stale_tax_consolidation_request

        return list(self._candidates)

    async def user_exists(self, list_tax_deductions_request: ListTaxDeductionsRequestDTO) -> bool:
        _ = list_tax_deductions_request

        return self._user_exists


def build_service(
        volumes: Optional[List[CategoryVolume]] = None,
        transaction_repository: Optional[FakeTransactionRepository] = None,
        tax_deduction_repository: Optional[FakeTaxDeductionRepository] = None
) -> Tuple[TaxConsolidationService, FakeTransactionRepository, FakeTaxDeductionRepository]:
    transactions = transaction_repository or FakeTransactionRepository(volumes=volumes)
    deductions = tax_deduction_repository or FakeTaxDeductionRepository()

    service = TaxConsolidationService(
        tax_policy=POLICY,
        transaction_repository=transactions,
        tax_deduction_repository=deductions
    )

    return service, transactions, deductions


class TestProgressiveTaxTable:

    def test_isento_nao_gera_imposto(self) -> None:
        assert TABLE.tax_due(base=Decimal("20000.00"), fiscal_year=FISCAL_YEAR) == Decimal("0.00")

    def test_faixa_intermediaria_aplica_parcela_a_deduzir(self) -> None:
        due = TABLE.tax_due(base=Decimal("40000.00"), fiscal_year=FISCAL_YEAR)

        assert due == Decimal("1433.77")

    def test_faixa_aberta_incide_acima_do_ultimo_teto(self) -> None:
        due = TABLE.tax_due(base=Decimal("96000.00"), fiscal_year=FISCAL_YEAR)

        assert due == Decimal("15659.02")

    def test_base_nao_positiva_nao_gera_imposto(self) -> None:
        assert TABLE.tax_due(base=Decimal("-500.00"), fiscal_year=FISCAL_YEAR) == Decimal("0.00")

    def test_exercicio_sem_tabela_propria_herda_a_mais_recente_anterior(self) -> None:
        assert TABLE.resolve_year(fiscal_year=FISCAL_YEAR + 5) == FISCAL_YEAR

    def test_exercicio_anterior_a_toda_tabela_usa_a_mais_antiga_declarada(self) -> None:
        assert TABLE.resolve_year(fiscal_year=1998) == FISCAL_YEAR

    def test_faixa_mal_declarada_e_recusada_na_montagem(self) -> None:
        with pytest.raises(ValueError):
            ProgressiveTaxTable.build(entries=["2026:1000:0.1"])


class TestTaxPolicy:

    def test_enquadramento_ignora_caixa_e_acentuacao(self) -> None:
        assert POLICY.classify(category="SAUDE") is TaxDeductionCategory.HEALTH
        assert POLICY.classify(category="  educacao  ") is TaxDeductionCategory.EDUCATION

    def test_categoria_fora_da_taxonomia_nao_e_dedutivel(self) -> None:
        assert POLICY.classify(category="Delivery") is None

    def test_saude_recebe_teto_sentinela_inalcancavel(self) -> None:
        ceiling = POLICY.ceiling_for(category=TaxDeductionCategory.HEALTH, fiscal_year=FISCAL_YEAR)

        assert ceiling == Decimal("9999999999999.99")

    def test_instrucao_observa_teto_do_exercicio(self) -> None:
        ceiling = POLICY.ceiling_for(category=TaxDeductionCategory.EDUCATION, fiscal_year=FISCAL_YEAR)

        assert ceiling == Decimal("3561.50")

    def test_exercicio_sem_teto_declarado_herda_o_anterior(self) -> None:
        ceiling = POLICY.ceiling_for(
            category=TaxDeductionCategory.EDUCATION,
            fiscal_year=FISCAL_YEAR + 1
        )

        assert ceiling == Decimal("3561.50")

    def test_normalizador_e_o_mesmo_do_ranqueamento(self) -> None:
        assert normalize_label("Energia  ELÉTRICA") == "energia eletrica"


class TestCategoryDeduction:

    def test_elegivel_e_o_menor_entre_declarado_e_teto(self) -> None:
        deduction = CategoryDeduction(
            total=4,
            total_amount=Decimal("5000.00"),
            legal_ceiling=Decimal("3561.50"),
            category=TaxDeductionCategory.EDUCATION
        )

        assert deduction.eligible_amount == Decimal("3561.50")
        assert deduction.disallowed_amount == Decimal("1438.50")
        assert deduction.is_capped is True

    def test_abaixo_do_teto_nao_ha_descarte(self) -> None:
        deduction = CategoryDeduction(
            total=2,
            total_amount=Decimal("1200.00"),
            legal_ceiling=Decimal("3561.50"),
            category=TaxDeductionCategory.EDUCATION
        )

        assert deduction.eligible_amount == Decimal("1200.00")
        assert deduction.is_capped is False

    def test_montante_negativo_e_recusado(self) -> None:
        with pytest.raises(ValueError):
            CategoryDeduction(
                total=1,
                total_amount=Decimal("-1.00"),
                legal_ceiling=Decimal("10.00"),
                category=TaxDeductionCategory.HEALTH
            )


class TestRefundProjection:

    def test_apuracao_em_duplicidade_captura_o_rebaixamento_de_faixa(self) -> None:
        projection = RefundProjection.build(
            table=TABLE,
            fiscal_year=FISCAL_YEAR,
            taxable_income=Decimal("56000.00"),
            deductible_base=Decimal("1000.00")
        )

        assert projection.tax_without_deductions == Decimal("4659.02")
        assert projection.tax_with_deductions == Decimal("4432.83")
        assert projection.estimated_refund == Decimal("226.19")

    def test_base_liquida_nunca_e_negativa(self) -> None:
        projection = RefundProjection.build(
            table=TABLE,
            fiscal_year=FISCAL_YEAR,
            taxable_income=Decimal("1000.00"),
            deductible_base=Decimal("4000.00")
        )

        assert projection.net_taxable_base == Decimal("0.00")
        assert projection.estimated_refund == Decimal("0.00")

    def test_aliquota_efetiva_cai_com_a_deducao(self) -> None:
        projection = RefundProjection.build(
            table=TABLE,
            fiscal_year=FISCAL_YEAR,
            taxable_income=Decimal("96000.00"),
            deductible_base=Decimal("11981.50")
        )

        assert projection.nominal_rate > projection.effective_rate


class TestTaxConsolidationService:

    @pytest.mark.asyncio
    async def test_consolida_apenas_categorias_dedutiveis(self) -> None:
        service, transactions, deductions = build_service(
            volumes=[
                build_volume(category="Saúde", amount="4000.00", total=3),
                build_volume(category="Odontologia", amount="1200.00", total=2),
                build_volume(category="Delivery", amount="2500.00", total=18),
                build_volume(category="Mensalidade Escolar", amount="5000.00", total=10)
            ]
        )

        result = await service.consolidate(
            recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        categories = [item.category for item in result.summary.items]

        assert categories == TaxDeductionCategory.canonical_order()
        assert result.summary.find(TaxDeductionCategory.HEALTH).total_amount == Decimal("5200.00")
        assert result.summary.find(TaxDeductionCategory.HEALTH).total == 5

    @pytest.mark.asyncio
    async def test_teto_de_instrucao_limita_o_elegivel(self) -> None:
        service, _, _ = build_service(
            volumes=[build_volume(category="Educação", amount="5000.00", total=10)]
        )

        result = await service.consolidate(
            recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        assert result.summary.total_eligible == Decimal("3561.50")
        assert result.summary.total_disallowed == Decimal("1438.50")
        assert result.summary.capped_categories == [TaxDeductionCategory.EDUCATION]

    @pytest.mark.asyncio
    async def test_saude_nao_e_limitada_pelo_sentinela(self) -> None:
        service, _, _ = build_service(
            volumes=[build_volume(category="Plano de Saúde", amount="48000.00", total=12)]
        )

        result = await service.consolidate(
            recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        assert result.summary.total_eligible == Decimal("48000.00")
        assert result.summary.capped_categories == []

    @pytest.mark.asyncio
    async def test_apuracao_cobre_o_exercicio_inteiro(self) -> None:
        service, transactions, _ = build_service(volumes=[])

        await service.consolidate(
            recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        request = transactions.aggregate_calls[0]

        assert request.start_date == date(FISCAL_YEAR, 1, 1)
        assert request.end_date == date(FISCAL_YEAR, 12, 31)
        assert request.include_essential is True

    @pytest.mark.asyncio
    async def test_categoria_que_zerou_desaparece_da_consolidacao(self) -> None:
        repository = FakeTaxDeductionRepository(
            deductions=[
                build_deduction(
                    category=TaxDeductionCategory.EDUCATION,
                    total_amount="5000.00",
                    legal_ceiling="3561.50"
                )
            ]
        )

        service, _, _ = build_service(
            volumes=[build_volume(category="Saúde", amount="900.00", total=1)],
            tax_deduction_repository=repository
        )

        result = await service.consolidate(
            recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        assert [item.category for item in result.items] == [TaxDeductionCategory.HEALTH]
        assert repository.persisted[0].entries[0].category is TaxDeductionCategory.HEALTH

    @pytest.mark.asyncio
    async def test_reprocessar_duas_vezes_devolve_o_mesmo_retrato(self) -> None:
        service, _, repository = build_service(
            volumes=[build_volume(category="Saúde", amount="900.00", total=1)]
        )

        request = RecalculateTaxDeductionsRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            fiscal_year=FISCAL_YEAR
        )

        first = await service.consolidate(recalculate_tax_deductions_request=request)
        second = await service.consolidate(recalculate_tax_deductions_request=request)

        assert first.summary.total_eligible == second.summary.total_eligible
        assert len(repository.persisted) == 2

    @pytest.mark.asyncio
    async def test_leitura_nao_reapura_nem_grava(self) -> None:
        repository = FakeTaxDeductionRepository(
            deductions=[
                build_deduction(
                    category=TaxDeductionCategory.HEALTH,
                    total_amount="900.00",
                    legal_ceiling="9999999999999.99"
                )
            ]
        )

        service, transactions, _ = build_service(tax_deduction_repository=repository)

        result = await service.read(
            list_tax_deductions_request=ListTaxDeductionsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        assert result.summary.total_eligible == Decimal("900.00")
        assert transactions.aggregate_calls == []
        assert repository.persisted == []


class TestGetTaxDeductionsUseCase:

    @pytest.mark.asyncio
    async def test_exercicio_sem_deducao_devolve_consolidacao_vazia(self) -> None:
        service, _, repository = build_service()
        usecase = GetTaxDeductionsUseCase(
            tax_consolidation_service=service,
            tax_deduction_repository=repository
        )

        result = await usecase.execute(
            list_tax_deductions_request=ListTaxDeductionsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        assert result.items == []
        assert result.is_consolidated is False

    @pytest.mark.asyncio
    async def test_usuario_inexistente_e_distinguido_de_exercicio_vazio(self) -> None:
        repository = FakeTaxDeductionRepository(user_exists=False)
        service, _, _ = build_service(tax_deduction_repository=repository)

        usecase = GetTaxDeductionsUseCase(
            tax_consolidation_service=service,
            tax_deduction_repository=repository
        )

        with pytest.raises(TaxOwnerNotFoundError):
            await usecase.execute(
                list_tax_deductions_request=ListTaxDeductionsRequestDTO(
                    user_id=USER_ID,
                    partner_id=PARTNER_ID,
                    fiscal_year=FISCAL_YEAR
                )
            )

    @pytest.mark.asyncio
    async def test_exercicio_futuro_e_recusado(self) -> None:
        service, _, repository = build_service()
        usecase = GetTaxDeductionsUseCase(
            tax_consolidation_service=service,
            tax_deduction_repository=repository
        )

        with pytest.raises(InvalidFiscalYearError):
            await usecase.execute(
                list_tax_deductions_request=ListTaxDeductionsRequestDTO(
                    user_id=USER_ID,
                    partner_id=PARTNER_ID,
                    fiscal_year=FISCAL_YEAR + 1
                )
            )


class TestRecalculateTaxDeductionsUseCase:

    @pytest.mark.asyncio
    async def test_reprocessamento_persiste_a_consolidacao(self) -> None:
        service, _, repository = build_service(
            volumes=[build_volume(category="Saúde", amount="2500.00", total=4)]
        )

        usecase = RecalculateTaxDeductionsUseCase(tax_consolidation_service=service)

        result = await usecase.execute(
            recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        assert result.summary.total_eligible == Decimal("2500.00")
        assert len(repository.persisted) == 1

    @pytest.mark.asyncio
    async def test_exercicio_futuro_nao_chega_ao_banco(self) -> None:
        service, transactions, _ = build_service()
        usecase = RecalculateTaxDeductionsUseCase(tax_consolidation_service=service)

        with pytest.raises(InvalidFiscalYearError):
            await usecase.execute(
                recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
                    user_id=USER_ID,
                    partner_id=PARTNER_ID,
                    fiscal_year=FISCAL_YEAR + 3
                )
            )

        assert transactions.aggregate_calls == []


class TestGetRefundProjectionUseCase:

    @pytest.mark.asyncio
    async def test_renda_informada_prevalece_sobre_o_historico(self) -> None:
        transactions = FakeTransactionRepository(
            balance=ConsolidatedBalance(
                settled_income=Decimal("50000.00"),
                pending_income=Decimal("0.00"),
                settled_expense=Decimal("0.00"),
                pending_expense=Decimal("0.00")
            )
        )

        repository = FakeTaxDeductionRepository(
            deductions=[
                build_deduction(
                    category=TaxDeductionCategory.HEALTH,
                    total_amount="11981.50",
                    legal_ceiling="9999999999999.99"
                )
            ]
        )

        service, _, _ = build_service(
            transaction_repository=transactions,
            tax_deduction_repository=repository
        )

        usecase = GetRefundProjectionUseCase(
            tax_policy=POLICY,
            transaction_repository=transactions,
            tax_consolidation_service=service
        )

        result = await usecase.execute(
            refund_projection_request=RefundProjectionRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR,
                taxable_income=Decimal("96000.00")
            )
        )

        assert result.income_source is TaxableIncomeSource.DECLARED
        assert result.projection.taxable_income == Decimal("96000.00")
        assert transactions.summarize_calls == []

    @pytest.mark.asyncio
    async def test_sem_renda_informada_infere_das_receitas_liquidadas(self) -> None:
        transactions = FakeTransactionRepository(
            balance=ConsolidatedBalance(
                settled_income=Decimal("72000.00"),
                pending_income=Decimal("9000.00"),
                settled_expense=Decimal("0.00"),
                pending_expense=Decimal("0.00")
            )
        )

        service, _, _ = build_service(transaction_repository=transactions)

        usecase = GetRefundProjectionUseCase(
            tax_policy=POLICY,
            transaction_repository=transactions,
            tax_consolidation_service=service
        )

        result = await usecase.execute(
            refund_projection_request=RefundProjectionRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR
            )
        )

        assert result.income_source is TaxableIncomeSource.TRANSACTION_HISTORY
        assert result.projection.taxable_income == Decimal("72000.00")
        assert transactions.summarize_calls[0].start_date == date(FISCAL_YEAR, 1, 1)

    @pytest.mark.asyncio
    async def test_sem_renda_alguma_a_projecao_e_recusada(self) -> None:
        transactions = FakeTransactionRepository()
        service, _, _ = build_service(transaction_repository=transactions)

        usecase = GetRefundProjectionUseCase(
            tax_policy=POLICY,
            transaction_repository=transactions,
            tax_consolidation_service=service
        )

        with pytest.raises(TaxableIncomeUnavailableError):
            await usecase.execute(
                refund_projection_request=RefundProjectionRequestDTO(
                    user_id=USER_ID,
                    partner_id=PARTNER_ID,
                    fiscal_year=FISCAL_YEAR
                )
            )

    @pytest.mark.asyncio
    async def test_projecao_carrega_a_consolidacao_que_a_fundamentou(self) -> None:
        repository = FakeTaxDeductionRepository(
            deductions=[
                build_deduction(
                    category=TaxDeductionCategory.EDUCATION,
                    total_amount="5000.00",
                    legal_ceiling="3561.50"
                )
            ]
        )

        transactions = FakeTransactionRepository()
        service, _, _ = build_service(
            transaction_repository=transactions,
            tax_deduction_repository=repository
        )

        usecase = GetRefundProjectionUseCase(
            tax_policy=POLICY,
            transaction_repository=transactions,
            tax_consolidation_service=service
        )

        result = await usecase.execute(
            refund_projection_request=RefundProjectionRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                fiscal_year=FISCAL_YEAR,
                taxable_income=Decimal("96000.00")
            )
        )

        assert result.deductions.summary.total_disallowed == Decimal("1438.50")
        assert result.projection.deductible_base == Decimal("3561.50")
