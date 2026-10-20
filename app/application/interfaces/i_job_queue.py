from typing import Any, Protocol


class IJobQueue(Protocol):

    async def enqueue(self, task_name: str, *args: Any) -> str:
        """Publica o job e devolve seu identificador."""
        ...
