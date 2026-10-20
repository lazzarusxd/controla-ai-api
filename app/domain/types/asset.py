from enum import Enum


class AssetType(str, Enum):
    """Natureza do bem durável, determinante da curva de depreciação aplicada."""

    # Veículo automotor, sujeito a IPVA e à depreciação mais acentuada do domínio.
    VEHICLE = "VEHICLE"

    # Imóvel urbano, sujeito a IPTU e, por convenção do projeto, sem depreciação.
    PROPERTY = "PROPERTY"

    # Demais bens duráveis declarados pelo usuário final.
    OTHER = "OTHER"
