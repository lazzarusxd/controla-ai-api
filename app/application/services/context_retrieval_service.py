from typing import List
from decimal import Decimal

from app.config.logging_setup import logger
from app.domain.value_objects import ContextChunk, RetrievedContext
from app.application.interfaces import IEmbeddingProvider, IEmbeddingRepository
from app.application.dto import RetrieveContextRequestDTO, VectorSearchRequestDTO


class ContextRetrievalService:

    def __init__(
            self,
            top_k: int,
            minimum_similarity: Decimal,
            embedding_provider: IEmbeddingProvider,
            embedding_repository: IEmbeddingRepository
    ) -> None:
        self._top_k = top_k
        self._minimum_similarity = minimum_similarity
        self._embedding_provider = embedding_provider
        self._embedding_repository = embedding_repository

    async def retrieve(self, retrieve_context_request: RetrieveContextRequestDTO) -> RetrievedContext:
        vectors = await self._embedding_provider.embed(texts=[retrieve_context_request.question])

        if not vectors:
            return RetrievedContext(chunks=[])

        chunks = await self._embedding_repository.search(
            vector_search_request=VectorSearchRequestDTO(
                top_k=self._top_k,
                query_vector=vectors[0],
                user_id=retrieve_context_request.user_id,
                partner_id=retrieve_context_request.partner_id
            )
        )

        relevant: List[ContextChunk] = [
            chunk for chunk in chunks
            if chunk.is_relevant(minimum_similarity=self._minimum_similarity)
        ]

        logger.info(
            "assistant_context_retrieved",
            retrieved=len(chunks),
            relevant=len(relevant),
            user_id=str(retrieve_context_request.user_id),
            partner_id=str(retrieve_context_request.partner_id)
        )

        return RetrievedContext(chunks=relevant)
