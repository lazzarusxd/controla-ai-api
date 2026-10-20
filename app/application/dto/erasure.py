from uuid import UUID
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from app.domain.types import ErasedResource
from app.domain.value_objects import ErasureManifest


@dataclass(frozen=True, slots=True)
class EraseAccountRequestDTO:
    """Entrada da eliminação definitiva. A confirmação viaja em cabeçalho, não em corpo."""
    user_id: UUID
    partner_id: UUID
    confirmation: Optional[str] = None

    @property
    def is_confirmed(self) -> bool:
        """A confirmação precisa repetir o identificador do caminho, e nada além dele."""
        if self.confirmation is None:
            return False

        return self.confirmation.strip().casefold() == str(self.user_id).casefold()


@dataclass(frozen=True, slots=True)
class ErasedAccountDTO:
    """Saída do expurgo transacional: o que a cascata levou e o que sobrou fora do banco."""
    user_id: UUID
    partner_id: UUID
    receipt_file_paths: List[str] = field(default_factory=list)
    totals: Dict[ErasedResource, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AccountErasureResultDTO:
    """Comprovante consolidado da eliminação, incluindo o expurgo fora do banco."""
    user_id: UUID
    partner_id: UUID
    erased_at: datetime
    manifest: ErasureManifest

    @property
    def is_complete(self) -> bool:
        return self.manifest.is_complete
