from fastapi import APIRouter

from app.presentation.api.v1.tax.router import router as tax_router
from app.presentation.api.v1.goals.router import router as goals_router
from app.presentation.api.v1.health.router import router as health_router
from app.presentation.api.v1.assets.router import router as assets_router
from app.presentation.api.v1.billing.router import router as billing_router
from app.presentation.api.v1.exports.router import router as exports_router
from app.presentation.api.v1.accounts.router import router as accounts_router
from app.presentation.api.v1.partners.router import router as partners_router
from app.presentation.api.v1.receipts.router import router as receipts_router
from app.presentation.api.v1.assistant.router import router as assistant_router
from app.presentation.api.v1.analytics.router import router as analytics_router
from app.presentation.api.v1.simulations.router import router as simulations_router
from app.presentation.api.v1.transactions.router import router as transactions_router
from app.presentation.api.v1.subscriptions.router import router as subscriptions_router
from app.presentation.api.v1.authentication.router import router as authentication_router


router = APIRouter()

router.include_router(health_router)

router.include_router(authentication_router, prefix="/v1")

router.include_router(partners_router, prefix="/v1")

router.include_router(transactions_router, prefix="/v1")

router.include_router(receipts_router, prefix="/v1")

router.include_router(subscriptions_router, prefix="/v1")

router.include_router(assets_router, prefix="/v1")

router.include_router(assistant_router, prefix="/v1")

router.include_router(analytics_router, prefix="/v1")

router.include_router(goals_router, prefix="/v1")

router.include_router(exports_router, prefix="/v1")

router.include_router(accounts_router, prefix="/v1")

router.include_router(tax_router, prefix="/v1")

router.include_router(simulations_router, prefix="/v1")

router.include_router(billing_router, prefix="/v1")
