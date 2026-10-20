from typing import Union

from .export import ExportEvent
from .receipt import ReceiptEvent
from .subscription import SubscriptionEvent


WebhookEvent = Union[ReceiptEvent, SubscriptionEvent, ExportEvent]
