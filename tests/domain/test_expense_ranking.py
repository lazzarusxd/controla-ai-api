from decimal import Decimal

import pytest

from app.domain.value_objects import ParetoPolicy, normalize_label
from app.domain.value_objects.expense_ranking import CategoryVolume, ExpenseRanking


POLICY = ParetoPolicy.build(cutoff_ratio=Decimal("0.8"), essential_categories=["Moradia", "Energia elétrica"])


def build_ranking(include_essential: bool = False) -> ExpenseRanking:
    return ExpenseRanking.from_volumes(
        policy=POLICY,
        include_essential=include_essential,
        volumes=[
            CategoryVolume(category="Lazer", amount=Decimal("1500.00"), total=8),
            CategoryVolume(category="moradia", amount=Decimal("9000.00"), total=1),
            CategoryVolume(category="Vestuário", amount=Decimal("500.00"), total=3),
            CategoryVolume(category="Transporte", amount=Decimal("3000.00"), total=20),
            CategoryVolume(category="Alimentação", amount=Decimal("5000.00"), total=40)
        ]
    )


class TestParetoPolicy:

    def test_rejects_cutoff_below_the_minimum(self) -> None:
        with pytest.raises(ValueError):
            ParetoPolicy(cutoff_ratio=Decimal("0.3"), essential_categories=frozenset())

    def test_rejects_cutoff_above_one(self) -> None:
        with pytest.raises(ValueError):
            ParetoPolicy(cutoff_ratio=Decimal("1.2"), essential_categories=frozenset())

    def test_essential_match_ignores_accent_case_and_spacing(self) -> None:
        assert POLICY.is_essential(category="  ENERGIA ELETRICA ") is True

    def test_variable_category_is_not_essential(self) -> None:
        assert POLICY.is_essential(category="Lazer") is False

    def test_blank_categories_do_not_enter_the_taxonomy(self) -> None:
        policy = ParetoPolicy.build(cutoff_ratio=Decimal("0.8"), essential_categories=["  ", "Moradia"])

        assert policy.essential_categories == frozenset({normalize_label("Moradia")})


class TestCategoryVolume:

    def test_rejects_negative_amount(self) -> None:
        with pytest.raises(ValueError):
            CategoryVolume(category="Lazer", amount=Decimal("-1.00"), total=1)

    def test_rejects_negative_count(self) -> None:
        with pytest.raises(ValueError):
            CategoryVolume(category="Lazer", amount=Decimal("1.00"), total=-1)


class TestExpenseRanking:

    def test_essential_expense_is_removed_before_the_cut(self) -> None:
        ranking = build_ranking()

        assert ranking.excluded_categories == ["moradia"]
        assert ranking.essential_amount == Decimal("9000.00")
        assert ranking.total_amount == Decimal("10000.00")
        assert ranking.total_transactions == 71

    def test_essential_expense_can_be_kept_in_the_dispute(self) -> None:
        ranking = build_ranking(include_essential=True)

        assert ranking.excluded_categories == []
        assert ranking.total_amount == Decimal("19000.00")

    def test_ordering_is_decreasing_by_amount(self) -> None:
        positions = [item.category for item in build_ranking().ranking]

        assert positions == ["Alimentação", "Transporte", "Lazer", "Vestuário"]

    def test_ties_are_broken_alphabetically_for_determinism(self) -> None:
        ranking = ExpenseRanking.from_volumes(
            policy=POLICY,
            include_essential=True,
            volumes=[
                CategoryVolume(category="Transporte", amount=Decimal("100.00"), total=1),
                CategoryVolume(category="Alimentação", amount=Decimal("100.00"), total=1)
            ]
        )

        assert [item.category for item in ranking.ranking] == ["Alimentação", "Transporte"]

    def test_vital_few_reach_at_least_the_cutoff(self) -> None:
        ranking = build_ranking()

        assert [item.category for item in ranking.vital_few] == ["Alimentação", "Transporte"]
        assert ranking.vital_few_amount == Decimal("8000.00")
        assert ranking.vital_few_amount / ranking.total_amount >= POLICY.cutoff_ratio

    def test_trivial_many_is_the_complement_of_the_vital_few(self) -> None:
        ranking = build_ranking()

        trivial = [item.category for item in ranking.ranking if item.is_trivial_many]

        assert trivial == ["Lazer", "Vestuário"]

    def test_cumulative_share_closes_at_one(self) -> None:
        ranking = build_ranking().ranking

        assert ranking[-1].cumulative_share == Decimal("1.0000")

    def test_shares_are_rounded_for_display_only(self) -> None:
        ranking = build_ranking().ranking

        assert ranking[0].share == Decimal("0.5000")
        assert ranking[1].cumulative_share == Decimal("0.8000")

    def test_concentration_measures_how_few_categories_dominate(self) -> None:
        assert build_ranking().concentration_ratio == Decimal("0.5000")

    def test_empty_ranking_yields_no_positions(self) -> None:
        ranking = ExpenseRanking.from_volumes(policy=POLICY, include_essential=True, volumes=[])

        assert ranking.ranking == []
        assert ranking.vital_few == []
        assert ranking.concentration_ratio == Decimal("0.0000")

    def test_only_essential_expense_leaves_nothing_to_rank(self) -> None:
        ranking = ExpenseRanking.from_volumes(
            policy=POLICY,
            include_essential=False,
            volumes=[CategoryVolume(category="Moradia", amount=Decimal("2000.00"), total=1)]
        )

        assert ranking.total_amount == Decimal("0.00")
        assert ranking.ranking == []
