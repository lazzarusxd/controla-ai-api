import re
import unicodedata
from typing import Any, Dict, Tuple

from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError

from app.config.logging_setup import logger
from app.domain.types import OAuthErrorCode
from app.domain.exceptions.base import DomainError
from app.domain.exceptions.authentication_exceptions import AuthenticationError, InvalidClientError, InvalidTokenError
from app.domain.exceptions.transaction_exceptions import (
    TransactionError,
    UserNotFoundError,
    InvalidPeriodError,
    TransactionNotFoundError,
    TransactionNotEditableError,
    TransactionNotUnderReviewError
)
from app.domain.exceptions.goal_exceptions import (
    GoalError,
    GoalNotFoundError,
    GoalOwnerNotFoundError,
    InvalidGoalTargetError,
    InvalidGoalHorizonError
)
from app.domain.exceptions.asset_exceptions import (
    AssetError,
    AssetNotFoundError,
    AssetOwnerNotFoundError,
    InvalidAssetValuationError,
    InvalidAcquisitionDateError
)
from app.domain.exceptions.subscription_exceptions import (
    InvalidDueDayError,
    SubscriptionError,
    SubscriptionNotFoundError,
    SubscriptionOwnerNotFoundError
)
from app.domain.exceptions.assistant_exceptions import (
    AssistantError,
    EmptyQuestionError,
    AssistantUnavailableError
)
from app.domain.exceptions.receipt_exceptions import (
    ReceiptError,
    EmptyReceiptError,
    ReceiptNotFoundError,
    ReceiptTooLargeError,
    ReceiptExtractionError,
    WebhookNotRegisteredError,
    UnsupportedReceiptTypeError
)
from app.domain.exceptions.export_exceptions import (
    ExportError,
    ExportNotReadyError,
    EmptyExportScopeError,
    DataExportNotFoundError,
    InvalidExportPeriodError,
    ExportOwnerNotFoundError,
    ExportArtifactMissingError,
    ExportGenerationFailedError,
    UnsupportedExportFormatError
)
from app.domain.exceptions.erasure_exceptions import (
    ErasureError,
    AccountNotFoundError,
    ErasureNotConfirmedError,
    InvalidErasureManifestError
)
from app.domain.exceptions.tax_exceptions import (
    TaxError,
    TaxOwnerNotFoundError,
    InvalidFiscalYearError,
    TaxableIncomeUnavailableError
)
from app.domain.exceptions.billing_exceptions import (
    BillingError,
    OpenReferenceMonthError,
    FutureReferenceMonthError,
    InvalidReferenceMonthError
)
from app.domain.exceptions.simulation_exceptions import (
    SimulationError,
    InvalidCashDiscountError,
    InvalidPurchaseAmountError,
    InvalidOpportunityRateError,
    InvalidInstallmentTermsError
)


PROBLEM_JSON = "application/problem+json"

PROBLEM_TYPE_BASE_URI = "https://controla.ai/problems/"

_OAUTH_STATUS: Dict[OAuthErrorCode, int] = {
    OAuthErrorCode.INVALID_SCOPE: status.HTTP_400_BAD_REQUEST,
    OAuthErrorCode.INVALID_GRANT: status.HTTP_400_BAD_REQUEST,
    OAuthErrorCode.INVALID_TOKEN: status.HTTP_401_UNAUTHORIZED,
    OAuthErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    OAuthErrorCode.INVALID_CLIENT: status.HTTP_401_UNAUTHORIZED,
    OAuthErrorCode.UNAUTHORIZED_CLIENT: status.HTTP_401_UNAUTHORIZED,
    OAuthErrorCode.UNSUPPORTED_GRANT_TYPE: status.HTTP_400_BAD_REQUEST
}

_TRANSACTION_PROBLEM: Dict[type, Tuple[int, str]] = {
    UserNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado."),
    InvalidPeriodError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Período inválido."),
    TransactionNotFoundError: (status.HTTP_404_NOT_FOUND, "Lançamento não encontrado."),
    TransactionNotEditableError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Lançamento imutável."),
    TransactionNotUnderReviewError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Lançamento não pendente de revisão.")
}

_RECEIPT_PROBLEM: Dict[type, Tuple[int, str]] = {
    EmptyReceiptError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Arquivo vazio."),
    ReceiptNotFoundError: (status.HTTP_404_NOT_FOUND, "Comprovante não encontrado."),
    WebhookNotRegisteredError: (status.HTTP_404_NOT_FOUND, "Webhook não registrado."),
    ReceiptTooLargeError: (status.HTTP_413_CONTENT_TOO_LARGE, "Arquivo grande demais."),
    ReceiptExtractionError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Extração do comprovante inviável."),
    UnsupportedReceiptTypeError: (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Tipo de arquivo não suportado.")
}

_SUBSCRIPTION_PROBLEM: Dict[type, Tuple[int, str]] = {
    SubscriptionNotFoundError: (status.HTTP_404_NOT_FOUND, "Recorrência não encontrada."),
    SubscriptionOwnerNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado."),
    InvalidDueDayError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Dia de vencimento inválido."),
}

_ASSET_PROBLEM: Dict[type, Tuple[int, str]] = {
    AssetOwnerNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado."),
    AssetNotFoundError: (status.HTTP_404_NOT_FOUND, "Bem patrimonial não encontrado."),
    InvalidAssetValuationError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Valoração do bem inválida."),
    InvalidAcquisitionDateError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Data de aquisição inválida.")
}

_GOAL_PROBLEM: Dict[type, Tuple[int, str]] = {
    GoalOwnerNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado."),
    GoalNotFoundError: (status.HTTP_404_NOT_FOUND, "Meta financeira não encontrada."),
    InvalidGoalTargetError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Valor alvo inválido."),
    InvalidGoalHorizonError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Prazo da meta inválido.")
}

_ASSISTANT_PROBLEM: Dict[type, Tuple[int, str]] = {
    EmptyQuestionError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Pergunta vazia."),
    AssistantUnavailableError: (status.HTTP_503_SERVICE_UNAVAILABLE, "Assistente indisponível.")
}

_EXPORT_PROBLEM: Dict[type, Tuple[int, str]] = {
    ExportNotReadyError: (status.HTTP_409_CONFLICT, "Exportação em processamento."),
    ExportOwnerNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado."),
    DataExportNotFoundError: (status.HTTP_404_NOT_FOUND, "Exportação não encontrada."),
    InvalidExportPeriodError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Período inválido."),
    ExportArtifactMissingError: (status.HTTP_410_GONE, "Arquivo da exportação indisponível."),
    EmptyExportScopeError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Escopo de exportação vazio."),
    ExportGenerationFailedError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Geração da exportação falhou."),
    UnsupportedExportFormatError: (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Formato de exportação não suportado.")
}

_TAX_PROBLEM: Dict[type, Tuple[int, str]] = {
    TaxOwnerNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado."),
    InvalidFiscalYearError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Exercício fiscal inválido."),
    TaxableIncomeUnavailableError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Renda tributável indisponível.")
}

_SIMULATION_PROBLEM: Dict[type, Tuple[int, str]] = {
    InvalidPurchaseAmountError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Valor do bem inválido."),
    InvalidCashDiscountError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Desconto à vista inválido."),
    InvalidInstallmentTermsError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Condição de parcelamento inválida."),
    InvalidOpportunityRateError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Taxa de custo de oportunidade inválida.")
}

_BILLING_PROBLEM: Dict[type, Tuple[int, str]] = {
    OpenReferenceMonthError: (status.HTTP_409_CONFLICT, "Competência em aberto."),
    FutureReferenceMonthError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Competência futura."),
    InvalidReferenceMonthError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Competência inválida.")
}

_ERASURE_PROBLEM: Dict[type, Tuple[int, str]] = {
    AccountNotFoundError: (status.HTTP_404_NOT_FOUND, "Usuário não encontrado."),
    InvalidErasureManifestError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Erro interno do servidor."),
    ErasureNotConfirmedError: (status.HTTP_428_PRECONDITION_REQUIRED, "Confirmação de eliminação ausente.")
}


def _problem_slug(title: str) -> str:
    """Deriva um identificador ASCII estável para o 'type' (RFC 9457 §3.1.1, RFC 3986)."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")


def _used_basic_scheme(request: Request) -> bool:
    """Indica se o cliente se autenticou via cabeçalho Authorization com esquema Basic (RFC 7617)."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, _ = authorization.partition(" ")

    return scheme.lower() == "basic"


def _problem(request: Request, status_code: int, title: str, detail: str, **extra: Any) -> JSONResponse:
    """Monta um corpo application/problem+json conforme RFC 9457."""
    body: Dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_BASE_URI}{_problem_slug(title)}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
        **extra
    }

    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_JSON)


def register_exception_handlers(app: FastAPI) -> None:
    """Registra a tradução de exceções em respostas HTTP."""
    @app.exception_handler(AuthenticationError)
    async def _authentication_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        status_code = _OAUTH_STATUS.get(exc.oauth_error, status.HTTP_400_BAD_REQUEST)
        headers: Dict[str, str] = {"Cache-Control": "no-store", "Pragma": "no-cache"}

        # RFC 6749 §5.2: o desafio Basic só é obrigatório quando o cliente usou o cabeçalho
        # Authorization. Com credenciais no corpo, omiti-lo evita o prompt nativo do navegador.
        if isinstance(exc, InvalidClientError) and _used_basic_scheme(request):
            headers["WWW-Authenticate"] = 'Basic realm="controla-ai"'

        if isinstance(exc, InvalidTokenError):
            headers["WWW-Authenticate"] = (
                f'Bearer realm="controla-ai", error="{exc.oauth_error.value}", '
                f'error_description="{exc.message}"'
            )

        return JSONResponse(
            headers=headers,
            status_code=status_code,
            content={"error": exc.oauth_error.value, "error_description": exc.message}
        )

    @app.exception_handler(TransactionError)
    async def _transaction_error(request: Request, exc: TransactionError) -> JSONResponse:
        status_code, title = _TRANSACTION_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(ReceiptError)
    async def _receipt_error(request: Request, exc: ReceiptError) -> JSONResponse:
        status_code, title = _RECEIPT_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(SubscriptionError)
    async def _subscription_error(request: Request, exc: SubscriptionError) -> JSONResponse:
        status_code, title = _SUBSCRIPTION_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(AssetError)
    async def _asset_error(request: Request, exc: AssetError) -> JSONResponse:
        status_code, title = _ASSET_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(GoalError)
    async def _goal_error(request: Request, exc: GoalError) -> JSONResponse:
        status_code, title = _GOAL_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(AssistantError)
    async def _assistant_error(request: Request, exc: AssistantError) -> JSONResponse:
        status_code, title = _ASSISTANT_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(TaxError)
    async def _tax_error(request: Request, exc: TaxError) -> JSONResponse:
        status_code, title = _TAX_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(SimulationError)
    async def _simulation_error(request: Request, exc: SimulationError) -> JSONResponse:
        status_code, title = _SIMULATION_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(BillingError)
    async def _billing_error(request: Request, exc: BillingError) -> JSONResponse:
        status_code, title = _BILLING_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            request=request,
            detail=exc.message,
            title="Regra de negócio violada.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    @app.exception_handler(ExportError)
    async def _export_error(request: Request, exc: ExportError) -> JSONResponse:
        status_code, title = _EXPORT_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(ErasureError)
    async def _erasure_error(request: Request, exc: ErasureError) -> JSONResponse:
        status_code, title = _ERASURE_PROBLEM.get(
            type(exc),
            (status.HTTP_422_UNPROCESSABLE_CONTENT, "Regra de negócio violada.")
        )

        return _problem(request=request, title=title, detail=exc.message, status_code=status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            request=request,
            title="Corpo da requisição inválido.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A requisição não satisfaz o contrato do endpoint.",
            errors=[
                {"field": ".".join(str(part) for part in error.get("loc")), "message": error.get("msg")}
                for error in exc.errors()
            ]
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=request.url.path, error=type(exc).__name__)

        return _problem(
            request=request,
            title="Erro interno do servidor.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno no processamento da requisição."
        )
