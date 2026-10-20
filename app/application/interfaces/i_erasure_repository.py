from typing import Optional, Protocol

from app.application.dto import ErasedAccountDTO, EraseAccountRequestDTO


class IErasureRepository(Protocol):

    async def erase(self, erase_account_request: EraseAccountRequestDTO) -> Optional[ErasedAccountDTO]:
        """Apaga o titular e, por cascata, tudo que dele deriva, na mesma transação."""
        ...
