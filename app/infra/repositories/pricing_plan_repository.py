from uuid import UUID
from typing import Optional

from app.domain.types import PricingSource
from app.domain.value_objects import PricingPlan
from app.infra.database.postgres import PostgresPool
from app.application.dto import PricingPlanRequestDTO
from app.application.interfaces import IPricingPlanRepository


class PricingPlanRepository(IPricingPlanRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def find_effective(self, pricing_plan_request: PricingPlanRequestDTO) -> Optional[PricingPlan]:
        async with self._pool.tenant_transaction(pricing_plan_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT
                        plan_id,
                        base_monthly_fee,
                        price_per_thousand_requests,
                        price_per_million_tokens_in,
                        price_per_million_tokens_out,
                        price_per_ocr_image
                    FROM partner_pricing_plans
                    WHERE partner_id = $1
                        AND effective_from <= $2
                    ORDER BY effective_from DESC
                    LIMIT 1
                """,
                pricing_plan_request.partner_id,
                str(pricing_plan_request.reference_month)
            )

        if record is None:
            return None

        return PricingPlan(
            source=PricingSource.CONTRACT,
            plan_id=UUID(str(record.get("plan_id"))),
            base_monthly_fee=record.get("base_monthly_fee"),
            price_per_ocr_image=record.get("price_per_ocr_image"),
            price_per_thousand_requests=record.get("price_per_thousand_requests"),
            price_per_million_tokens_in=record.get("price_per_million_tokens_in"),
            price_per_million_tokens_out=record.get("price_per_million_tokens_out")
        )
