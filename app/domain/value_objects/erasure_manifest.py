from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Tuple

from app.domain.types import ErasedResource
from app.domain.exceptions.erasure_exceptions import InvalidErasureManifestError


@dataclass(frozen=True, slots=True)
class ErasedRecordCount:
    """Quantos registros de um recurso saíram no expurgo."""
    total: int
    resource: ErasedResource

    def __post_init__(self) -> None:
        if self.total < 0:
            raise InvalidErasureManifestError()


@dataclass(frozen=True, slots=True)
class ErasureManifest:
    """Comprovante do expurgo: o que saiu, quantos, e o que resistiu no volume."""
    counts: Tuple[ErasedRecordCount, ...]
    purged_files: Tuple[str, ...] = ()
    retained_files: Tuple[str, ...] = ()

    @classmethod
    def build(
            cls,
            totals: Mapping[ErasedResource, int],
            purged_files: Optional[Iterable[str]] = None,
            retained_files: Optional[Iterable[str]] = None
    ) -> "ErasureManifest":
        """Monta o comprovante na ordem canônica, para que dois expurgos sejam comparáveis."""
        return cls(
            purged_files=tuple(purged_files or ()),
            retained_files=tuple(retained_files or ()),
            counts=tuple(
                ErasedRecordCount(resource=resource, total=int(totals.get(resource, 0)))
                for resource in ErasedResource.canonical_order()
            )
        )

    @property
    def total_records(self) -> int:
        return sum(count.total for count in self.counts)

    @property
    def total_purged_files(self) -> int:
        return len(self.purged_files)

    @property
    def is_complete(self) -> bool:
        """Expurgo íntegro é aquele em que nenhum byte sobreviveu ao comando."""
        return not self.retained_files

    @property
    def outcome(self) -> str:
        """Desfecho registrado na auditoria."""
        return "COMPLETE" if self.is_complete else "PARTIAL"

    @property
    def label(self) -> str:
        """Descrição compacta do que saiu, usada no registro de auditoria."""
        return ",".join(f"{count.resource.value}={count.total}" for count in self.counts if count.total > 0)

    def total_of(self, resource: ErasedResource) -> int:
        for count in self.counts:
            if count.resource is resource:
                return count.total

        return 0

    def as_resource_totals(self) -> List[Tuple[str, int]]:
        """Pares recurso/contagem prontos para serialização no evento de auditoria."""
        return [(count.resource.value, count.total) for count in self.counts]
