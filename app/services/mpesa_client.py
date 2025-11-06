import httpx
from typing import Optional, Dict, Any
from datetime import datetime
import base64
import hashlib
import hmac

class MpesaClient:
    """
    Minimal M-Pesa STK push client.
    Replace stubs with real credentials and OAuth token retrieval.
    """
    def __init__(self, base_url: str, shortcode: str, passkey: str, callback_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.shortcode = shortcode
        self.passkey = passkey
        self.callback_url = callback_url
        self.timeout = timeout

    @staticmethod
    def _timestamp() -> str:
        return datetime.utcnow().strftime("%Y%m%d%H%M%S")

    def _password(self, timestamp: str) -> str:
        raw = f"{self.shortcode}{self.passkey}{timestamp}".encode()
        return base64.b64encode(raw).decode()

    async def initiate_stk(self, phone: str, amount: float, account_ref: str, description: str) -> Dict[str, Any]:
        """
        STUB for demo. Replace with real Daraja:
        POST /mpesa/stkpush/v1/processrequest
        """
        ts = self._timestamp()
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": self._password(ts),
            "Timestamp": ts,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": account_ref,
            "TransactionDesc": description,
        }
        # In dev, just fake success:
        return {
            "ok": True,
            "MerchantRequestID": f"MR-{ts}",
            "CheckoutRequestID": f"CR-{ts}",
            "payload": payload,
        }
