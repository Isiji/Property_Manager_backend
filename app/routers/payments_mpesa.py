# payments_mpesa.py
from fastapi import APIRouter

# This file is intentionally kept as a placeholder to avoid
# duplicate/conflicting M-Pesa routes.
#
# Active payment routes now live in:
#   payment_router.py
#
# Keep this file only if your app imports these routers somewhere.
# It now exposes no endpoints.

router = APIRouter(prefix="/payments/mpesa", tags=["Payments: M-Pesa (Deprecated)"])
webhook_router = APIRouter(prefix="/payments/webhooks", tags=["Payments: Webhooks (Deprecated)"])