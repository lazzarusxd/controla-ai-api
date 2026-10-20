from uuid import uuid4
from pathlib import Path

import pytest

from app.infra.storage.local_receipt_storage import LocalReceiptStorage


USER_ID = uuid4()
PARTNER_ID = uuid4()


async def test_file_is_stored_under_the_tenant_layout(tmp_path: Path) -> None:
    storage = LocalReceiptStorage(storage_root=str(tmp_path))
    receipt_id = uuid4()

    file_path = await storage.save(
        content=b"bytes",
        user_id=USER_ID,
        receipt_id=receipt_id,
        partner_id=PARTNER_ID,
        file_type="image/jpeg"
    )

    assert file_path == f"{PARTNER_ID}/{USER_ID}/{receipt_id}.jpg"
    assert (tmp_path / file_path).read_bytes() == b"bytes"


async def test_pdf_keeps_its_extension(tmp_path: Path) -> None:
    storage = LocalReceiptStorage(storage_root=str(tmp_path))

    file_path = await storage.save(
        user_id=USER_ID,
        receipt_id=uuid4(),
        content=b"%PDF-1.7",
        partner_id=PARTNER_ID,
        file_type="application/pdf"
    )

    assert file_path.endswith(".pdf")


async def test_stored_content_round_trips(tmp_path: Path) -> None:
    storage = LocalReceiptStorage(storage_root=str(tmp_path))

    file_path = await storage.save(
        user_id=USER_ID,
        receipt_id=uuid4(),
        partner_id=PARTNER_ID,
        file_type="image/png",
        content=b"conteudo-original"
    )

    assert await storage.read(file_path=file_path) == b"conteudo-original"


async def test_traversal_path_cannot_escape_the_storage_root(tmp_path: Path) -> None:
    storage = LocalReceiptStorage(storage_root=str(tmp_path))

    with pytest.raises(ValueError):
        await storage.read(file_path="../../etc/passwd")


async def test_delete_reports_missing_file(tmp_path: Path) -> None:
    storage = LocalReceiptStorage(storage_root=str(tmp_path))

    assert await storage.delete(file_path=f"{PARTNER_ID}/{USER_ID}/inexistente.jpg") is False
