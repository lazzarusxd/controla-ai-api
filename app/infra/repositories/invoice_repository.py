import json
from uuid import UUID
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from app.domain.entities import Invoice
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IInvoiceRepository
from app.domain.value_objects import InvoiceCharges, PricingPlan, ReferenceMonth, UsageVolume
from app.domain.types import BillingActor, BillingAuditEventType, InvoiceStatus, PricingSource
from app.application.dto import (
    InvoiceClosureDTO,
    GetInvoiceRequestDTO,
    ListInvoicesRequestDTO,
    PersistInvoiceRequestDTO,
    RegisterCloseReplayRequestDTO
)


class InvoiceRepository(IInvoiceRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def find_by_month(self, get_invoice_request: GetInvoiceRequestDTO) -> Optional[Invoice]:
        async with self._pool.tenant_transaction(get_invoice_request.partner_id) as connection:
            record = await self._fetch_by_month(
                connection=connection,
                partner_id=get_invoice_request.partner_id,
                reference_month=get_invoice_request.reference_month
            )

        return self._to_entity(record) if record is not None else None

    async def close(self, persist_invoice_request: PersistInvoiceRequestDTO) -> InvoiceClosureDTO:
        composition = persist_invoice_request.composition
        charges = composition.charges
        pricing = composition.pricing
        volume = composition.volume

        async with self._pool.tenant_transaction(persist_invoice_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    INSERT INTO invoices (
                        partner_id,
                        reference_month,
                        base_fee,
                        api_fee,
                        llm_fee,
                        ocr_fee,
                        total,
                        status,
                        closed_at,
                        closed_by,
                        api_requests,
                        llm_tokens_in,
                        llm_tokens_out,
                        ocr_images,
                        price_per_thousand_requests,
                        price_per_million_tokens_in,
                        price_per_million_tokens_out,
                        price_per_ocr_image,
                        pricing_source,
                        pricing_plan_id
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, 'CLOSED', now(), $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18
                    )
                    ON CONFLICT ON CONSTRAINT uq_invoices_period DO NOTHING
                    RETURNING
                        invoice_id,
                        partner_id,
                        reference_month,
                        base_fee,
                        api_fee,
                        llm_fee,
                        ocr_fee,
                        total,
                        status,
                        closed_at,
                        closed_by,
                        created_at,
                        api_requests,
                        llm_tokens_in,
                        llm_tokens_out,
                        ocr_images,
                        price_per_thousand_requests,
                        price_per_million_tokens_in,
                        price_per_million_tokens_out,
                        price_per_ocr_image,
                        pricing_source,
                        pricing_plan_id
                """,
                persist_invoice_request.partner_id,
                str(composition.reference_month),
                charges.base_fee,
                charges.api_fee,
                charges.llm_fee,
                charges.ocr_fee,
                charges.total,
                persist_invoice_request.actor.value,
                volume.api_requests,
                volume.llm_tokens_in,
                volume.llm_tokens_out,
                volume.ocr_images,
                pricing.price_per_thousand_requests,
                pricing.price_per_million_tokens_in,
                pricing.price_per_million_tokens_out,
                pricing.price_per_ocr_image,
                pricing.source.value,
                pricing.plan_id
            )

            created = record is not None

            if record is None:
                record = await self._fetch_by_month(
                    connection=connection,
                    reference_month=composition.reference_month,
                    partner_id=persist_invoice_request.partner_id
                )

            if record is None:
                raise RuntimeError("Conflito de competência sem fatura correspondente visível ao parceiro.")

            invoice = self._to_entity(record)

            event_type = (
                BillingAuditEventType.INVOICE_CLOSED
                if created
                else BillingAuditEventType.INVOICE_CLOSE_REPLAYED
            )

            await self._audit(
                invoice=invoice,
                event_type=event_type,
                connection=connection,
                actor=persist_invoice_request.actor,
                client_id=persist_invoice_request.client_id
            )

        return InvoiceClosureDTO(invoice=invoice, created=created)

    async def register_close_replay(self, register_close_replay_request: RegisterCloseReplayRequestDTO) -> None:
        invoice = register_close_replay_request.invoice

        async with self._pool.tenant_transaction(invoice.partner_id) as connection:
            await self._audit(
                invoice=invoice,
                connection=connection,
                actor=register_close_replay_request.actor,
                client_id=register_close_replay_request.client_id,
                event_type=BillingAuditEventType.INVOICE_CLOSE_REPLAYED
            )

    async def list_closed(self, list_invoices_request: ListInvoicesRequestDTO) -> Tuple[List[Invoice], int]:
        async with self._pool.tenant_transaction(list_invoices_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        invoice_id,
                        partner_id,
                        reference_month,
                        base_fee,
                        api_fee,
                        llm_fee,
                        ocr_fee,
                        total,
                        status,
                        closed_at,
                        closed_by,
                        created_at,
                        api_requests,
                        llm_tokens_in,
                        llm_tokens_out,
                        ocr_images,
                        price_per_thousand_requests,
                        price_per_million_tokens_in,
                        price_per_million_tokens_out,
                        price_per_ocr_image,
                        pricing_source,
                        pricing_plan_id,
                        count(*) OVER () AS total_count
                    FROM invoices
                    WHERE partner_id = $1
                        AND status = 'CLOSED'
                    ORDER BY reference_month DESC
                    LIMIT $2 OFFSET $3
                """,
                list_invoices_request.partner_id,
                list_invoices_request.page_size,
                list_invoices_request.offset
            )

            if not records and list_invoices_request.page > 1:
                total = await connection.fetchval(
                    "SELECT count(*) FROM invoices WHERE partner_id = $1 AND status = 'CLOSED'",
                    list_invoices_request.partner_id
                )
            else:
                total = records[0].get("total_count") if records else 0

        return [self._to_entity(record) for record in records], int(total)

    @staticmethod
    async def _fetch_by_month(
            partner_id: UUID,
            connection: asyncpg.Connection,
            reference_month: ReferenceMonth
    ) -> Optional[asyncpg.Record]:
        return await connection.fetchrow(
            """
                SELECT
                    invoice_id,
                    partner_id,
                    reference_month,
                    base_fee,
                    api_fee,
                    llm_fee,
                    ocr_fee,
                    total,
                    status,
                    closed_at,
                    closed_by,
                    created_at,
                    api_requests,
                    llm_tokens_in,
                    llm_tokens_out,
                    ocr_images,
                    price_per_thousand_requests,
                    price_per_million_tokens_in,
                    price_per_million_tokens_out,
                    price_per_ocr_image,
                    pricing_source,
                    pricing_plan_id
                FROM invoices
                WHERE partner_id = $1
                    AND reference_month = $2
            """,
            partner_id,
            str(reference_month)
        )

    @staticmethod
    async def _audit(
            invoice: Invoice,
            actor: BillingActor,
            client_id: Optional[str],
            connection: asyncpg.Connection,
            event_type: BillingAuditEventType
    ) -> None:
        """Auditoria na transação do fato: sem COMMIT do fechamento não há evento, e vice-versa."""
        payload: Dict[str, Any] = {
            "total": str(invoice.total),
            "volume": invoice.volume.as_counters(),
            "pricing_source": invoice.pricing.source.value,
            "pricing_plan_id": str(invoice.pricing.plan_id) if invoice.pricing.plan_id else None
        }

        await connection.execute(
            """
                INSERT INTO billing_audit_events (
                    partner_id,
                    event_type,
                    actor,
                    client_id,
                    reference_month,
                    invoice_id,
                    payload
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7::jsonb
                )
            """,
            invoice.partner_id,
            event_type.value,
            actor.value,
            client_id,
            str(invoice.reference_month),
            invoice.invoice_id,
            json.dumps(payload)
        )

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> Invoice:
        closed_by = record.get("closed_by")
        plan_id = record.get("pricing_plan_id")

        return Invoice(
            closed_at=record.get("closed_at"),
            created_at=record.get("created_at"),
            status=InvoiceStatus(record.get("status")),
            invoice_id=UUID(str(record.get("invoice_id"))),
            partner_id=UUID(str(record.get("partner_id"))),
            closed_by=BillingActor(closed_by) if closed_by else None,
            reference_month=ReferenceMonth.parse(record.get("reference_month")),
            volume=UsageVolume(
                ocr_images=int(record.get("ocr_images")),
                api_requests=int(record.get("api_requests")),
                llm_tokens_in=int(record.get("llm_tokens_in")),
                llm_tokens_out=int(record.get("llm_tokens_out"))
            ),
            charges=InvoiceCharges(
                api_fee=record.get("api_fee"),
                llm_fee=record.get("llm_fee"),
                ocr_fee=record.get("ocr_fee"),
                base_fee=record.get("base_fee")
            ),
            pricing=PricingPlan(
                base_monthly_fee=record.get("base_fee"),
                plan_id=UUID(str(plan_id)) if plan_id else None,
                source=PricingSource(record.get("pricing_source")),
                price_per_ocr_image=record.get("price_per_ocr_image"),
                price_per_thousand_requests=record.get("price_per_thousand_requests"),
                price_per_million_tokens_in=record.get("price_per_million_tokens_in"),
                price_per_million_tokens_out=record.get("price_per_million_tokens_out")
            )
        )
