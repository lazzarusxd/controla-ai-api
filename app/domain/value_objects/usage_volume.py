from dataclasses import dataclass
from typing import Dict, Final, Mapping, Tuple, Union


_COUNTER_NAMES: Final[Tuple[str, ...]] = (
    "ocr_images",
    "api_requests",
    "llm_tokens_in",
    "llm_tokens_out"
)


@dataclass(frozen=True, slots=True)
class UsageVolume:
    """Volumetria faturável. Os nomes dos campos coincidem com as colunas de consumo persistidas."""
    ocr_images: int = 0
    api_requests: int = 0
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0

    def __post_init__(self) -> None:
        for name in _COUNTER_NAMES:
            if getattr(self, name) < 0:
                raise ValueError(f"O contador {name} não pode ser negativo.")

    def __add__(self, other: "UsageVolume") -> "UsageVolume":
        return UsageVolume(
            ocr_images=self.ocr_images + other.ocr_images,
            api_requests=self.api_requests + other.api_requests,
            llm_tokens_in=self.llm_tokens_in + other.llm_tokens_in,
            llm_tokens_out=self.llm_tokens_out + other.llm_tokens_out
        )

    @property
    def is_empty(self) -> bool:
        return all(value == 0 for value in self.as_counters().values())

    @property
    def llm_tokens(self) -> int:
        return self.llm_tokens_in + self.llm_tokens_out

    def as_counters(self) -> Dict[str, int]:
        return {name: getattr(self, name) for name in _COUNTER_NAMES}

    @classmethod
    def from_counters(cls, counters: Mapping[str, Union[str, int]]) -> "UsageVolume":
        """Reconstrói a partir de um mapa de contadores, ignorando campos desconhecidos."""
        return cls(**{name: int(value) for name, value in counters.items() if name in _COUNTER_NAMES})
