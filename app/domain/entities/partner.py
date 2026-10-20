from uuid import UUID
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Partner:
    """Empresa contratante da API no modelo B2B2C. Raiz do agregado de tenancy."""
    name: str
    is_active: bool
    partner_id: UUID
