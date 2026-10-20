import asyncio
from uuid import UUID
from typing import Dict
from pathlib import Path

from app.config.logging_setup import logger
from app.application.interfaces import IReceiptStorage


class LocalReceiptStorage(IReceiptStorage):

    def __init__(self, storage_root: str) -> None:
        self._storage_root = Path(storage_root)
        self._extension_by_mime: Dict[str, str] = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "application/pdf": "pdf"
        }

    async def save(self, partner_id: UUID, user_id: UUID, receipt_id: UUID, file_type: str, content: bytes) -> str:
        extension = self._extension_by_mime.get(file_type, "bin")
        relative_path = f"{partner_id}/{user_id}/{receipt_id}.{extension}"
        absolute_path = self._storage_root / relative_path

        await asyncio.to_thread(self._write, absolute_path, content)

        logger.info("receipt_file_stored", file_path=relative_path, file_size_bytes=len(content))

        return relative_path

    async def read(self, file_path: str) -> bytes:
        absolute_path = self._resolve(file_path=file_path)

        return await asyncio.to_thread(absolute_path.read_bytes)

    async def delete(self, file_path: str) -> bool:
        absolute_path = self._resolve(file_path=file_path)

        if not absolute_path.exists():
            return False

        await asyncio.to_thread(absolute_path.unlink)

        return True

    def _resolve(self, file_path: str) -> Path:
        """Impede que um caminho vindo do banco escape da raiz do volume."""
        absolute_path = (self._storage_root / file_path).resolve()

        if not absolute_path.is_relative_to(self._storage_root.resolve()):
            raise ValueError("Caminho de comprovante fora da raiz de armazenamento.")

        return absolute_path

    @staticmethod
    def _write(absolute_path: Path, content: bytes) -> None:
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content)
