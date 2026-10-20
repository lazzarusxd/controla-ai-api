from decimal import Decimal
from typing import Dict, List

from app.config.logging_setup import logger
from app.domain.entities import Asset, Transaction
from app.application.interfaces import IEmbeddingProvider, IEmbeddingRepository
from app.domain.types import AssetType, EmbeddingSourceType, TransactionType
from app.application.dto import EmbeddingRecordDTO, IndexUserContextRequestDTO, IndexingResultDTO


_ASSET_TYPE_LABEL: Dict[AssetType, str] = {
    AssetType.VEHICLE: "Veículo",
    AssetType.PROPERTY: "Imóvel",
    AssetType.OTHER: "Bem durável"
}

_ASSET_TAX_LABEL: Dict[AssetType, str] = {
    AssetType.VEHICLE: "IPVA",
    AssetType.PROPERTY: "IPTU",
    AssetType.OTHER: "tributos"
}


def _format_brl(amount: Decimal) -> str:
    """Formata no padrão monetário brasileiro (R$ 1.234,56), independente do locale do processo."""
    return f"R$ {amount:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


class ContextIndexingService:

    def __init__(
            self,
            embedding_provider: IEmbeddingProvider,
            embedding_repository: IEmbeddingRepository
    ) -> None:
        self._embedding_provider = embedding_provider
        self._embedding_repository = embedding_repository

    async def index(self, index_user_context_request: IndexUserContextRequestDTO) -> IndexingResultDTO:
        transactions = await self._embedding_repository.list_stale_transactions(
            user_id=index_user_context_request.user_id,
            partner_id=index_user_context_request.partner_id,
            batch_size=index_user_context_request.batch_size
        )

        assets = await self._embedding_repository.list_stale_assets(
            user_id=index_user_context_request.user_id,
            partner_id=index_user_context_request.partner_id,
            batch_size=index_user_context_request.batch_size
        )

        records = self._pending_records(transactions=transactions, assets=assets)

        if not records:
            return IndexingResultDTO(partner_id=index_user_context_request.partner_id)

        vectors = await self._embedding_provider.embed(texts=[record.context_text for record in records])

        vectorized = [
            EmbeddingRecordDTO(
                vector=vector,
                user_id=record.user_id,
                source_id=record.source_id,
                partner_id=record.partner_id,
                source_type=record.source_type,
                context_text=record.context_text
            )
            for record, vector in zip(records, vectors, strict=True)
        ]

        indexed = await self._embedding_repository.upsert_many(
            records=vectorized,
            partner_id=index_user_context_request.partner_id
        )

        logger.info(
            "assistant_context_indexed",
            indexed=indexed,
            candidates=len(records),
            assets=len(assets),
            transactions=len(transactions),
            partner_id=str(index_user_context_request.partner_id),
            user_id=str(index_user_context_request.user_id) if index_user_context_request.user_id else None
        )

        return IndexingResultDTO(
            indexed=indexed,
            skipped=len(records) - indexed,
            partner_id=index_user_context_request.partner_id
        )

    def _pending_records(self, transactions: List[Transaction], assets: List[Asset]) -> List[EmbeddingRecordDTO]:
        """Registros ainda sem vetor: o texto é montado aqui e vetorizado em uma única chamada ao provedor."""
        records: List[EmbeddingRecordDTO] = [
            EmbeddingRecordDTO(
                vector=[],
                user_id=transaction.user_id,
                partner_id=transaction.partner_id,
                source_id=transaction.transaction_id,
                source_type=EmbeddingSourceType.TRANSACTION,
                context_text=self._transaction_text(transaction=transaction)
            )
            for transaction in transactions
        ]

        records.extend(
            EmbeddingRecordDTO(
                vector=[],
                user_id=asset.user_id,
                source_id=asset.asset_id,
                partner_id=asset.partner_id,
                source_type=EmbeddingSourceType.ASSET,
                context_text=self._asset_text(asset=asset)
            )
            for asset in assets
        )

        return records

    @staticmethod
    def _transaction_text(transaction: Transaction) -> str:
        """Narrativa em português: o texto indexado é o mesmo que o modelo vai ler."""
        nature = "Receita" if transaction.type is TransactionType.INCOME else "Despesa"

        parts: List[str] = [
            f"{nature} de {_format_brl(transaction.amount)} em {transaction.transaction_date.strftime('%d/%m/%Y')}",
            f"categoria {transaction.category}",
            f"descrição {transaction.description}",
            f"situação {transaction.status.value}"
        ]

        if transaction.due_date is not None:
            parts.append(f"vencimento em {transaction.due_date.strftime('%d/%m/%Y')}")

        if transaction.receipt_id is not None:
            parts.append("originada de comprovante processado por OCR")

        return ". ".join(parts) + "."

    @staticmethod
    def _asset_text(asset: Asset) -> str:
        """Narrativa do bem com o custo de propriedade, nos termos em que o usuário pergunta."""
        label = _ASSET_TYPE_LABEL.get(asset.asset_type, "Bem durável")
        tax_label = _ASSET_TAX_LABEL.get(asset.asset_type, "tributos")

        parts: List[str] = [
            f"{label} cadastrado no patrimônio: {asset.description}",
            f"valor de mercado {_format_brl(asset.market_value)}",
            f"adquirido em {asset.acquisition_date.strftime('%d/%m/%Y')}",
            f"{tax_label} anual de {_format_brl(asset.annual_taxes)}, "
            f"equivalente a {_format_brl(asset.monthly_tax_provision)} por mês"
        ]

        if asset.depreciates:
            parts.append(f"depreciação mensal de {_format_brl(asset.monthly_depreciation)}")

        parts.append(
            f"custo mensal de manter o bem {_format_brl(asset.total_monthly_cost)}, "
            f"ou {_format_brl(asset.total_annual_cost)} por ano"
        )

        return ". ".join(parts) + "."
