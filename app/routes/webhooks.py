"""Webhook routes for third-party services (e.g., Razorpay)."""

import hmac
import hashlib
import razorpay
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.config import settings
from app.database import get_db
from app.models.fine import Fine
from app.models.student import Student
from app.utils.email import send_student_notification, get_html_template

router = APIRouter(tags=["Webhooks"])

@router.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Secure endpoint to receive payment confirmations directly from Razorpay.
    """
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook secret not configured")

    payload_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing signature")

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    try:
        # Verify the signature cryptographically to prevent spoofing
        client.utility.verify_webhook_signature(payload_body.decode('utf-8'), signature, webhook_secret)
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    payload = await request.json()
    
    # We only care about successful payment captures
    if payload.get("event") == "payment.captured":
        payment_entity = payload["payload"]["payment"]["entity"]
        notes = payment_entity.get("notes", {})
        
        fine_id = notes.get("fine_id")
        roll_no = notes.get("roll_no")
        transaction_id = payment_entity.get("id")

        if not fine_id or not roll_no:
            # Payment didn't have our expected metadata
            return {"status": "ignored", "reason": "missing metadata"}

        fine = db.query(Fine).filter(Fine.id == fine_id, Fine.roll_no == roll_no).first()
        student = db.query(Student).filter(Student.roll_no == roll_no).first()

        if fine and fine.status != "Paid":
            # Mark fine as paid
            fine.status = "Paid"
            fine.payment_date = datetime.now(timezone.utc)
            fine.transaction_id = transaction_id
            
            # Mark student cleared
            if student:
                student.status = "Cleared"

            db.commit()

            # Send email receipt
            if student and student.email:
                html_content = get_html_template(
                    "Payment Successful",
                    f"<p>Dear {student.name},</p>"
                    f"<p>We have successfully received your fine payment of <strong>Rs. {fine.amount}</strong> for Semester {student.semester} via Razorpay.</p>"
                    f"<p><strong>Transaction ID:</strong> {transaction_id}</p>"
                    f"<p>Your clearance status is now marked as <strong>Cleared</strong>. You can download the receipt from your dashboard.</p>"
                )
                send_student_notification(student.email, "GPH - Fine Payment Successful", html_content)

        return {"status": "ok"}
    
    return {"status": "ignored"}
