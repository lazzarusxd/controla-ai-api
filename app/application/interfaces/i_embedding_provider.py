from typing import List, Protocol


class IEmbeddingProvider(Protocol):

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Converte os textos em vetores densos, preservando a ordem de entrada."""
        ...
