from typing import List, Union
from datetime import datetime, timezone

from app.config.logging_setup import logger
from app.domain.value_objects import ErasureManifest
from app.application.dto import AccountErasureResultDTO, EraseAccountRequestDTO
from app.domain.exceptions.erasure_exceptions import AccountNotFoundError, ErasureNotConfirmedError
from app.application.interfaces import IErasureRepository, IExportPurger, IExportStorage, IReceiptStorage


class EraseAccountUseCase:

    def __init__(
            self,
            export_purger: IExportPurger,
            export_storage: IExportStorage,
            receipt_storage: IReceiptStorage,
            erasure_repository: IErasureRepository
    ) -> None:
        self._export_purger = export_purger
        self._export_storage = export_storage
        self._receipt_storage = receipt_storage
        self._erasure_repository = erasure_repository

    async def execute(self, erase_account_request: EraseAccountRequestDTO) -> AccountErasureResultDTO:
        if not erase_account_request.is_confirmed:
            raise ErasureNotConfirmedError()

        erased = await self._erasure_repository.erase(erase_account_request=erase_account_request)

        if erased is None:
            raise AccountNotFoundError()

        export_file_paths = await self._export_purger.purge_user(
            user_id=erase_account_request.user_id,
            partner_id=erase_account_request.partner_id
        )

        purged: List[str] = []
        retained: List[str] = []

        await self._purge(
            purged=purged,
            retained=retained,
            storage=self._receipt_storage,
            file_paths=erased.receipt_file_paths
        )

        await self._purge(
            purged=purged,
            retained=retained,
            file_paths=export_file_paths,
            storage=self._export_storage
        )

        manifest = ErasureManifest.build(
            purged_files=purged,
            totals=erased.totals,
            retained_files=retained
        )

        result = AccountErasureResultDTO(
            manifest=manifest,
            erased_at=datetime.now(timezone.utc),
            user_id=erase_account_request.user_id,
            partner_id=erase_account_request.partner_id
        )

        self._audit(account_erasure_result=result)

        return result

    @staticmethod
    async def _purge(
            purged: List[str],
            retained: List[str],
            file_paths: List[str],
            storage: Union[IExportStorage, IReceiptStorage]
    ) -> None:
        for file_path in file_paths:
            try:
                await storage.delete(file_path=file_path)
            except (OSError, ValueError) as exc:
                retained.append(file_path)
                logger.warning("account_erasure_file_retained", file_path=file_path, error=type(exc).__name__)

                continue

            purged.append(file_path)

    @staticmethod
    def _audit(account_erasure_result: AccountErasureResultDTO) -> None:
        manifest = account_erasure_result.manifest

        logger.info(
            "account_erasure_audit",
            operation="erase",
            resources=manifest.label,
            outcome=manifest.outcome,
            total_records=manifest.total_records,
            purged_files=manifest.total_purged_files,
            retained_files=list(manifest.retained_files),
            subject_user_id=str(account_erasure_result.user_id),
            actor_partner_id=str(account_erasure_result.partner_id),
            occurred_at=account_erasure_result.erased_at.isoformat()
        )
