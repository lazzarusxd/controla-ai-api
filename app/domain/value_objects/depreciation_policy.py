from decimal import Decimal
from dataclasses import dataclass

from app.domain.types import AssetType


@dataclass(frozen=True, slots=True)
class DepreciationPolicy:
    """Taxa de depreciação mensal vigente para cada natureza de bem."""
    other_rate: Decimal
    vehicle_rate: Decimal
    property_rate: Decimal

    def __post_init__(self) -> None:
        for rate in (self.vehicle_rate, self.property_rate, self.other_rate):
            if rate < 0 or rate > 1:
                raise ValueError("A taxa de depreciação mensal deve estar entre 0 e 1.")

    def rate_for(self, asset_type: AssetType) -> Decimal:
        """Imóvel não deprecia como veículo: a curva é atributo do tipo, não do registro."""
        if asset_type is AssetType.VEHICLE:
            return self.vehicle_rate

        if asset_type is AssetType.PROPERTY:
            return self.property_rate

        return self.other_rate
