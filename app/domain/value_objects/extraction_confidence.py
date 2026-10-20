from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


class ExtractionConfidenceWeights:
    """Pesos da composição do índice de confiança."""
    OCR = Decimal("0.4")
    SEMANTIC = Decimal("0.6")


@dataclass(frozen=True, slots=True)
class ExtractionConfidence:
    """Índice composto entre a leitura óptica e a validação semântica."""
    ocr_confidence: Decimal
    semantic_confidence: Decimal

    @property
    def score(self) -> Decimal:
        """Média ponderada das duas etapas, arredondada à escala de `transactions.confidence_score`."""
        weighted = (
            self.ocr_confidence * ExtractionConfidenceWeights.OCR
            + self.semantic_confidence * ExtractionConfidenceWeights.SEMANTIC
        )

        return weighted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def requires_review(self, threshold: Decimal) -> bool:
        """Abaixo do limiar, o lançamento nasce fora dos dois regimes contábeis."""
        return self.score < threshold
