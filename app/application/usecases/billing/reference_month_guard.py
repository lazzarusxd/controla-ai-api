from datetime import date

from app.domain.value_objects import ReferenceMonth
from app.domain.exceptions.billing_exceptions import FutureReferenceMonthError, OpenReferenceMonthError


def ensure_started(reference_month: ReferenceMonth, today: date) -> ReferenceMonth:
    """Recusa competência que ainda não começou antes de qualquer ida ao banco."""
    if reference_month > ReferenceMonth.containing(today):
        raise FutureReferenceMonthError()

    return reference_month


def ensure_finished(reference_month: ReferenceMonth, today: date) -> ReferenceMonth:
    """Fechar é possível apenas depois do último dia da competência, no fuso do processo."""
    ensure_started(reference_month=reference_month, today=today)

    if reference_month == ReferenceMonth.containing(today):
        raise OpenReferenceMonthError()

    return reference_month
