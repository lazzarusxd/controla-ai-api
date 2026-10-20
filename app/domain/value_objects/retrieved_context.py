from uuid import UUID
from typing import List
from dataclasses import dataclass

from app.domain.value_objects import ContextChunk


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """Conjunto de trechos que fundamenta a geração. Vazio, bloqueia a inferência."""
    chunks: List[ContextChunk]

    @property
    def is_empty(self) -> bool:
        return not self.chunks

    @property
    def source_ids(self) -> List[UUID]:
        return [chunk.source_id for chunk in self.chunks]

    def to_prompt_text(self, max_characters: int) -> str:
        """Serializa os trechos na ordem de relevância, truncando no teto configurado."""
        lines: List[str] = []
        consumed = 0

        for index, chunk in enumerate(self.chunks, start=1):
            line = f"[{index}] ({chunk.source_type.value}) {chunk.context_text}"

            if consumed + len(line) > max_characters:
                break

            lines.append(line)
            consumed += len(line)

        return "\n".join(lines)
