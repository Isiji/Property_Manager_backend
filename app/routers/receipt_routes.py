from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.receipt_model import PaymentReceipt

router = APIRouter(prefix="/payments/receipt", tags=["Receipts"])


@router.get("/{payment_id}/pdf")
def download_receipt_by_payment(payment_id: int, db: Session = Depends(get_db)):
    receipt = (
        db.query(PaymentReceipt)
        .filter(PaymentReceipt.payment_id == payment_id)
        .order_by(PaymentReceipt.created_at.desc())
        .first()
    )

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found for this payment")

    if not receipt.pdf_path:
        raise HTTPException(status_code=404, detail="Receipt PDF path is missing")

    return FileResponse(
        path=receipt.pdf_path,
        media_type="application/pdf",
        filename=f"{receipt.receipt_number}.pdf",
    )