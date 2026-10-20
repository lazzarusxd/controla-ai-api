import re
from datetime import date
from calendar import monthrange
from dataclasses import dataclass
from typing import Final, Pattern


_MONTH_PATTERN: Final[Pattern[str]] = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


@dataclass(frozen=True, slots=True, order=True)
class ReferenceMonth:
    """Competência de faturamento no formato YYYY-MM. A ordenação natural é a cronológica."""
    year: int
    month: int

    def __post_init__(self) -> None:
        if not 2000 <= self.year <= 2999:
            raise ValueError("O ano da competência deve estar entre 2000 e 2999.")

        if not 1 <= self.month <= 12:
            raise ValueError("O mês da competência deve estar entre 1 e 12.")

    @classmethod
    def parse(cls, value: str) -> "ReferenceMonth":
        matched = _MONTH_PATTERN.match(value.strip())

        if matched is None:
            raise ValueError("A competência deve seguir o formato YYYY-MM.")

        return cls(year=int(matched.group(1)), month=int(matched.group(2)))

    @classmethod
    def containing(cls, day: date) -> "ReferenceMonth":
        return cls(year=day.year, month=day.month)

    @property
    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def last_day(self) -> date:
        _, last = monthrange(self.year, self.month)

        return date(self.year, self.month, last)

    def contains(self, day: date) -> bool:
        return self.first_day <= day <= self.last_day

    def preceding(self) -> "ReferenceMonth":
        if self.month == 1:
            return ReferenceMonth(year=self.year - 1, month=12)

        return ReferenceMonth(year=self.year, month=self.month - 1)

    def following(self) -> "ReferenceMonth":
        if self.month == 12:
            return ReferenceMonth(year=self.year + 1, month=1)

        return ReferenceMonth(year=self.year, month=self.month + 1)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
