from uuid import UUID
from typing import List, Optional, Protocol

from app.domain.entities import Asset, Transaction
from app.domain.value_objects import ContextChunk
from app.application.dto import EmbeddingRecordDTO, VectorSearchRequestDTO


class IEmbeddingRepository(Protocol):

    async def search(self, vector_search_request: VectorSearchRequestDTO) -> List[ContextChunk]:
        """Recupera os vizinhos mais próximos no escopo do parceiro e do usuário."""
        ...

    async def upsert_many(self, partner_id: UUID, records: List[EmbeddingRecordDTO]) -> int:
        """Grava ou atualiza os vetores pela chave natural da origem. Devolve o total afetado."""
        ...

    async def list_stale_transactions(
            self,
            batch_size: int,
            partner_id: UUID,
            user_id: Optional[UUID] = None
    ) -> List[Transaction]:
        """Lançamentos sem vetor ou com vetor anterior à última alteração do registro."""
        ...

    async def list_stale_assets(
            self,
            batch_size: int,
            partner_id: UUID,
            user_id: Optional[UUID] = None
    ) -> List[Asset]:
        """Bens patrimoniais sem vetor ou com vetor anterior à última alteração do registro."""
        ...
