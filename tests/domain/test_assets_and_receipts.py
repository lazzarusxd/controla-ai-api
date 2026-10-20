from decimal import Decimal

import pytest

from app.domain.types import AssetType
from app.domain.value_objects import DepreciationPolicy, ExtractionConfidence, OwnershipCost, normalize_label


POLICY = DepreciationPolicy(
    other_rate=Decimal("0.005"),
    vehicle_rate=Decimal("0.01"),
    property_rate=Decimal("0.001")
)


class TestDepreciationPolicy:

    def test_curve_belongs_to_the_asset_type(self) -> None:
        assert POLICY.rate_for(asset_type=AssetType.OTHER) == Decimal("0.005")
        assert POLICY.rate_for(asset_type=AssetType.VEHICLE) == Decimal("0.01")
        assert POLICY.rate_for(asset_type=AssetType.PROPERTY) == Decimal("0.001")

    def test_rejects_rate_outside_the_unit_interval(self) -> None:
        with pytest.raises(ValueError):
            DepreciationPolicy(
                other_rate=Decimal("0.005"),
                vehicle_rate=Decimal("1.5"),
                property_rate=Decimal("0.001")
            )


class TestOwnershipCost:

    def test_total_is_the_sum_of_the_rounded_components(self) -> None:
        cost = OwnershipCost(
            annual_taxes=Decimal("2400.00"),
            market_value=Decimal("80000.00"),
            monthly_depreciation_rate=Decimal("0.01")
        )

        assert cost.total_monthly_cost == Decimal("1000.00")
        assert cost.total_annual_cost == Decimal("12000.00")
        assert cost.monthly_depreciation == Decimal("800.00")
        assert cost.monthly_tax_provision == Decimal("200.00")

    def test_asset_without_depreciation_costs_only_the_tax(self) -> None:
        cost = OwnershipCost(
            annual_taxes=Decimal("1200.00"),
            market_value=Decimal("500000.00"),
            monthly_depreciation_rate=Decimal("0")
        )

        assert cost.monthly_depreciation == Decimal("0.00")
        assert cost.total_monthly_cost == Decimal("100.00")

    def test_depreciation_is_computed_over_the_market_value(self) -> None:
        cost = OwnershipCost(
            annual_taxes=Decimal("0.00"),
            market_value=Decimal("1000.00"),
            monthly_depreciation_rate=Decimal("0.015")
        )

        assert cost.monthly_depreciation == Decimal("15.00")

    def test_rejects_negative_market_value(self) -> None:
        with pytest.raises(ValueError):
            OwnershipCost(
                annual_taxes=Decimal("0.00"),
                market_value=Decimal("-1.00"),
                monthly_depreciation_rate=Decimal("0.01")
            )

    def test_rejects_negative_taxes(self) -> None:
        with pytest.raises(ValueError):
            OwnershipCost(
                market_value=Decimal("1.00"),
                annual_taxes=Decimal("-1.00"),
                monthly_depreciation_rate=Decimal("0.01")
            )

    def test_rejects_rate_outside_the_unit_interval(self) -> None:
        with pytest.raises(ValueError):
            OwnershipCost(
                market_value=Decimal("1.00"),
                annual_taxes=Decimal("0.00"),
                monthly_depreciation_rate=Decimal("1.01")
            )


class TestExtractionConfidence:

    def test_semantic_validation_weighs_more_than_the_optical_reading(self) -> None:
        confidence = ExtractionConfidence(ocr_confidence=Decimal("0.50"), semantic_confidence=Decimal("1.00"))

        assert confidence.score == Decimal("0.80")

    def test_full_agreement_scores_the_maximum(self) -> None:
        assert ExtractionConfidence(
            ocr_confidence=Decimal("1.00"),
            semantic_confidence=Decimal("1.00")
        ).score == Decimal("1.00")

    def test_score_below_the_threshold_requires_review(self) -> None:
        confidence = ExtractionConfidence(ocr_confidence=Decimal("0.40"), semantic_confidence=Decimal("0.60"))

        assert confidence.score == Decimal("0.52")
        assert confidence.requires_review(threshold=Decimal("0.70")) is True

    def test_score_at_the_threshold_does_not_require_review(self) -> None:
        confidence = ExtractionConfidence(ocr_confidence=Decimal("0.70"), semantic_confidence=Decimal("0.70"))

        assert confidence.requires_review(threshold=Decimal("0.70")) is False


class TestTextNormalization:

    def test_removes_accents_case_and_redundant_spacing(self) -> None:
        assert normalize_label("  Energia   ELÉTRICA ") == "energia eletrica"

    def test_equivalent_labels_collapse_into_the_same_form(self) -> None:
        assert normalize_label("Saúde") == normalize_label("SAUDE")

    def test_distinct_labels_remain_distinct(self) -> None:
        assert normalize_label("Lazer") != normalize_label("Moradia")
