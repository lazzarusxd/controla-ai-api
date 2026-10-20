from decimal import Decimal
from uuid import UUID, uuid4
from typing import List, Optional, Tuple
from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.entities import Asset
from app.domain.types import AssetType
from app.application.usecases.assets.get_asset import GetAssetUseCase
from app.domain.value_objects import DepreciationPolicy, OwnershipCost
from app.application.usecases.assets.list_assets import ListAssetsUseCase
from app.application.usecases.assets.create_asset import CreateAssetUseCase
from app.application.usecases.assets.delete_asset import DeleteAssetUseCase
from app.application.usecases.assets.update_asset import UpdateAssetUseCase
from app.application.usecases.assets.get_asset_cost_summary import GetAssetCostSummaryUseCase
from app.domain.exceptions.asset_exceptions import (
    AssetNotFoundError,
    InvalidAssetValuationError,
    InvalidAcquisitionDateError
)
from app.application.dto import (
    AssetTypeCostDTO,
    GetAssetRequestDTO,
    ListAssetsRequestDTO,
    CreateAssetRequestDTO,
    DeleteAssetRequestDTO,
    UpdateAssetRequestDTO,
    PersistAssetRequestDTO,
    AssetCostSummaryRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()
POLICY = DepreciationPolicy(
    property_rate=Decimal("0"),
    other_rate=Decimal("0.0083"),
    vehicle_rate=Decimal("0.0167")
)


def build_asset(
        annual_taxes: str = "2740.00",
        market_value: str = "68500.00",
        total_monthly_cost: str = "1372.28",
        monthly_depreciation: str = "1143.95",
        monthly_tax_provision: str = "228.33",
        asset_type: AssetType = AssetType.VEHICLE
) -> Asset:
    return Asset(
        user_id=USER_ID,
        asset_id=uuid4(),
        partner_id=PARTNER_ID,
        asset_type=asset_type,
        annual_taxes=Decimal(annual_taxes),
        market_value=Decimal(market_value),
        created_at=datetime.now(timezone.utc),
        description="Fiat Argo Drive 1.3 2022",
        total_monthly_cost=Decimal(total_monthly_cost),
        acquisition_date=date(2022, 3, 15),
        monthly_depreciation=Decimal(monthly_depreciation),
        monthly_tax_provision=Decimal(monthly_tax_provision)
    )


class FakeAssetRepository:

    def __init__(
            self,
            delete_result: bool = True,
            stored: Optional[Asset] = None,
            listing: Optional[List[Asset]] = None,
            breakdown: Optional[List[AssetTypeCostDTO]] = None
    ) -> None:
        self._stored = stored
        self._listing = listing or []
        self._breakdown = breakdown or []
        self._delete_result = delete_result
        self.persisted: Optional[PersistAssetRequestDTO] = None

    async def create(self, persist_asset_request: PersistAssetRequestDTO) -> Asset:
        self.persisted = persist_asset_request

        return build_asset(
            asset_type=persist_asset_request.asset_type,
            market_value=str(persist_asset_request.market_value),
            annual_taxes=str(persist_asset_request.annual_taxes),
            total_monthly_cost=str(persist_asset_request.total_monthly_cost),
            monthly_depreciation=str(persist_asset_request.monthly_depreciation),
            monthly_tax_provision=str(persist_asset_request.monthly_tax_provision)
        )

    async def find_by_id(self, get_asset_request: GetAssetRequestDTO) -> Optional[Asset]:
        _ = self, get_asset_request

        return self._stored

    async def list_by_filter(self, list_assets_request: ListAssetsRequestDTO) -> Tuple[List[Asset], int]:
        _ = list_assets_request

        return self._listing, len(self._listing)

    async def update(self, persist_asset_request: PersistAssetRequestDTO) -> Optional[Asset]:
        self.persisted = persist_asset_request

        if self._stored is None:
            return None

        return build_asset(
            asset_type=persist_asset_request.asset_type,
            market_value=str(persist_asset_request.market_value),
            annual_taxes=str(persist_asset_request.annual_taxes),
            total_monthly_cost=str(persist_asset_request.total_monthly_cost),
            monthly_depreciation=str(persist_asset_request.monthly_depreciation),
            monthly_tax_provision=str(persist_asset_request.monthly_tax_provision)
        )

    async def delete(self, delete_asset_request: DeleteAssetRequestDTO) -> bool:
        _ = delete_asset_request

        return self._delete_result

    async def summarize_cost(self, cost_summary_request: AssetCostSummaryRequestDTO) -> List[AssetTypeCostDTO]:
        _ = cost_summary_request

        return self._breakdown


def test_ownership_cost_splits_taxes_and_depreciation() -> None:
    cost = OwnershipCost(
        annual_taxes=Decimal("2740.00"),
        market_value=Decimal("68500.00"),
        monthly_depreciation_rate=Decimal("0.0167")
    )

    assert cost.monthly_tax_provision == Decimal("228.33")
    assert cost.monthly_depreciation == Decimal("1143.95")
    assert cost.total_monthly_cost == cost.monthly_tax_provision + cost.monthly_depreciation


def test_ownership_cost_total_always_has_two_decimal_places() -> None:
    cost = OwnershipCost(
        market_value=Decimal("33333.33"),
        annual_taxes=Decimal("1000.00"),
        monthly_depreciation_rate=Decimal("0.0167")
    )

    assert cost.total_monthly_cost == cost.total_monthly_cost.quantize(Decimal("0.01"))


def test_property_does_not_depreciate() -> None:
    cost = OwnershipCost(
        annual_taxes=Decimal("3500.00"),
        market_value=Decimal("350000.00"),
        monthly_depreciation_rate=POLICY.rate_for(asset_type=AssetType.PROPERTY)
    )

    assert cost.monthly_depreciation == Decimal("0.00")
    assert cost.total_monthly_cost == Decimal("291.67")


def test_depreciation_policy_resolves_rate_by_asset_type() -> None:
    assert POLICY.rate_for(asset_type=AssetType.PROPERTY) == Decimal("0")
    assert POLICY.rate_for(asset_type=AssetType.OTHER) == Decimal("0.0083")
    assert POLICY.rate_for(asset_type=AssetType.VEHICLE) == Decimal("0.0167")


async def test_create_asset_persists_calculated_cost() -> None:
    repository = FakeAssetRepository()
    usecase = CreateAssetUseCase(asset_repository=repository, depreciation_policy=POLICY)

    asset = await usecase.execute(
        create_asset_request=CreateAssetRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            asset_type=AssetType.VEHICLE,
            annual_taxes=Decimal("2740.00"),
            market_value=Decimal("68500.00"),
            description="Fiat Argo Drive 1.3 2022",
            acquisition_date=date(2022, 3, 15)
        )
    )

    assert repository.persisted is not None
    assert repository.persisted.monthly_tax_provision == Decimal("228.33")
    assert asset.total_monthly_cost == Decimal("1372.28")


async def test_create_asset_rejects_future_acquisition_date() -> None:
    repository = FakeAssetRepository()
    usecase = CreateAssetUseCase(asset_repository=repository, depreciation_policy=POLICY)

    with pytest.raises(InvalidAcquisitionDateError):
        await usecase.execute(
            create_asset_request=CreateAssetRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                asset_type=AssetType.VEHICLE,
                annual_taxes=Decimal("2740.00"),
                market_value=Decimal("68500.00"),
                description="Veículo ainda não adquirido",
                acquisition_date=date.today() + timedelta(days=1)
            )
        )


async def test_create_asset_rejects_negative_valuation() -> None:
    repository = FakeAssetRepository()
    usecase = CreateAssetUseCase(asset_repository=repository, depreciation_policy=POLICY)

    with pytest.raises(InvalidAssetValuationError):
        await usecase.execute(
            create_asset_request=CreateAssetRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                asset_type=AssetType.VEHICLE,
                market_value=Decimal("-1.00"),
                annual_taxes=Decimal("2740.00"),
                description="Fiat Argo Drive 1.3 2022",
                acquisition_date=date(2022, 3, 15)
            )
        )


async def test_update_asset_recalculates_cost_on_new_market_value() -> None:
    repository = FakeAssetRepository(stored=build_asset())
    usecase = UpdateAssetUseCase(asset_repository=repository, depreciation_policy=POLICY)

    updated = await usecase.execute(
        update_asset_request=UpdateAssetRequestDTO(
            user_id=USER_ID,
            asset_id=uuid4(),
            partner_id=PARTNER_ID,
            market_value=Decimal("61200.00"),
            provided_fields=frozenset({"market_value"})
        )
    )

    assert updated.monthly_depreciation == Decimal("1022.04")
    assert updated.monthly_tax_provision == Decimal("228.33")
    assert updated.total_monthly_cost == Decimal("1250.37")


async def test_update_asset_preserves_untouched_fields() -> None:
    repository = FakeAssetRepository(stored=build_asset())
    usecase = UpdateAssetUseCase(asset_repository=repository, depreciation_policy=POLICY)

    await usecase.execute(
        update_asset_request=UpdateAssetRequestDTO(
            user_id=USER_ID,
            asset_id=uuid4(),
            partner_id=PARTNER_ID,
            description="Fiat Argo, placa ABC1D23",
            provided_fields=frozenset({"description"})
        )
    )

    assert repository.persisted is not None
    assert repository.persisted.market_value == Decimal("68500.00")
    assert repository.persisted.asset_type is AssetType.VEHICLE


async def test_update_asset_type_switches_depreciation_curve() -> None:
    repository = FakeAssetRepository(stored=build_asset())
    usecase = UpdateAssetUseCase(asset_repository=repository, depreciation_policy=POLICY)

    updated = await usecase.execute(
        update_asset_request=UpdateAssetRequestDTO(
            user_id=USER_ID,
            asset_id=uuid4(),
            partner_id=PARTNER_ID,
            asset_type=AssetType.PROPERTY,
            provided_fields=frozenset({"asset_type"})
        )
    )

    assert updated.monthly_depreciation == Decimal("0.00")
    assert updated.total_monthly_cost == Decimal("228.33")


async def test_update_asset_absent_raises_not_found() -> None:
    repository = FakeAssetRepository(stored=None)
    usecase = UpdateAssetUseCase(asset_repository=repository, depreciation_policy=POLICY)

    with pytest.raises(AssetNotFoundError):
        await usecase.execute(
            update_asset_request=UpdateAssetRequestDTO(
                user_id=USER_ID,
                asset_id=uuid4(),
                partner_id=PARTNER_ID,
                market_value=Decimal("10.00"),
                provided_fields=frozenset({"market_value"})
            )
        )


async def test_get_asset_absent_raises_not_found() -> None:
    usecase = GetAssetUseCase(asset_repository=FakeAssetRepository(stored=None))

    with pytest.raises(AssetNotFoundError):
        await usecase.execute(
            get_asset_request=GetAssetRequestDTO(
                user_id=USER_ID,
                asset_id=uuid4(),
                partner_id=PARTNER_ID
            )
        )


async def test_list_assets_returns_page_metadata() -> None:
    usecase = ListAssetsUseCase(asset_repository=FakeAssetRepository(listing=[build_asset(), build_asset()]))

    page = await usecase.execute(
        list_assets_request=ListAssetsRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID, page_size=1)
    )

    assert page.total == 2
    assert page.total_pages == 2
    assert page.has_next_page is True


async def test_delete_asset_absent_raises_not_found() -> None:
    usecase = DeleteAssetUseCase(asset_repository=FakeAssetRepository(delete_result=False))

    with pytest.raises(AssetNotFoundError):
        await usecase.execute(
            delete_asset_request=DeleteAssetRequestDTO(
                user_id=USER_ID,
                asset_id=uuid4(),
                partner_id=PARTNER_ID
            )
        )


async def test_cost_summary_consolidates_breakdown() -> None:
    breakdown = [
        AssetTypeCostDTO(
            total=1,
            asset_type=AssetType.VEHICLE,
            market_value=Decimal("68500.00"),
            total_monthly_cost=Decimal("1372.28"),
            monthly_depreciation=Decimal("1143.95"),
            monthly_tax_provision=Decimal("228.33")
        ),
        AssetTypeCostDTO(
            total=1,
            asset_type=AssetType.PROPERTY,
            market_value=Decimal("350000.00"),
            total_monthly_cost=Decimal("291.67"),
            monthly_depreciation=Decimal("0.00"),
            monthly_tax_provision=Decimal("291.67")
        )
    ]

    usecase = GetAssetCostSummaryUseCase(asset_repository=FakeAssetRepository(breakdown=breakdown))

    summary = await usecase.execute(
        cost_summary_request=AssetCostSummaryRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID)
    )

    assert summary.total_assets == 2
    assert summary.total_monthly_cost == Decimal("1663.95")
    assert summary.total_annual_cost == Decimal("19967.40")


async def test_cost_summary_without_assets_is_zeroed() -> None:
    usecase = GetAssetCostSummaryUseCase(asset_repository=FakeAssetRepository())

    summary = await usecase.execute(
        cost_summary_request=AssetCostSummaryRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID)
    )

    assert summary.total_assets == 0
    assert summary.total_monthly_cost == Decimal("0.00")


def test_age_in_months_counts_complete_months() -> None:
    asset = build_asset()

    assert asset.age_in_months(reference_date=date(2022, 3, 14)) == 0
    assert asset.age_in_months(reference_date=date(2023, 3, 15)) == 12
    assert isinstance(asset.user_id, UUID)
