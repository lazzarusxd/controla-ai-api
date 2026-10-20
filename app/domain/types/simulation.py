from enum import Enum


class PurchaseRecommendation(str, Enum):
    """Desfecho da comparação entre pagar à vista e parcelar, sob a taxa de custo de oportunidade vigente."""

    # Pagamento à vista com desconto. É também o desfecho do empate, porque a regra
    # de comparação exige vantagem estrita do parcelamento para recomendá-lo.
    CASH = "CASH"

    # Parcelamento, cujo valor presente ficou estritamente abaixo do preço à vista.
    INSTALLMENTS = "INSTALLMENTS"
