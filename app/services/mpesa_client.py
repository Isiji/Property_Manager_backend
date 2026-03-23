from __future__ import annotations

import base64
import datetime as dt
from typing import Dict, Any

import requests
from fastapi import HTTPException

from app.core.config import settings


class MpesaClient:
    """
    Production-ready M-Pesa STK Push client using Safaricom Daraja API.
    """

    def __init__(self):
        if not settings.DARAJA_BASE_URL:
            raise RuntimeError("DARAJA_BASE_URL not set")

        if not settings.DARAJA_CONSUMER_KEY or not settings.DARAJA_CONSUMER_SECRET:
            raise RuntimeError("Daraja consumer credentials missing")

        if not settings.DARAJA_LNM_SHORTCODE or not settings.DARAJA_LNM_PASSKEY:
            raise RuntimeError("Daraja shortcode/passkey missing")

        if not settings.DARAJA_CALLBACK_URL:
            raise RuntimeError("Callback URL not set")

        self.base_url = settings.DARAJA_BASE_URL.rstrip("/")
        self.consumer_key = settings.DARAJA_CONSUMER_KEY
        self.consumer_secret = settings.DARAJA_CONSUMER_SECRET
        self.shortcode = settings.DARAJA_LNM_SHORTCODE
        self.passkey = settings.DARAJA_LNM_PASSKEY
        self.callback_url = settings.DARAJA_CALLBACK_URL

    # =============================
    # AUTH
    # =============================
    def _get_access_token(self) -> str:
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"

        response = requests.get(
            url,
            auth=(self.consumer_key, self.consumer_secret),
            timeout=20,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Daraja OAuth failed: {response.text}"
            )

        data = response.json()
        token = data.get("access_token")

        if not token:
            raise HTTPException(status_code=502, detail="No access token returned")

        return token

    # =============================
    # HELPERS
    # =============================
    @staticmethod
    def _timestamp() -> str:
        return dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")

    def _password(self, timestamp: str) -> str:
        raw = f"{self.shortcode}{self.passkey}{timestamp}".encode("utf-8")
        return base64.b64encode(raw).decode("utf-8")

    # =============================
    # STK PUSH
    # =============================
    def initiate_stk_push(
        self,
        *,
        phone: str,
        amount: float,
        account_reference: str,
        description: str,
    ) -> Dict[str, Any]:
        """
        Initiates STK Push

        Returns:
        {
            MerchantRequestID,
            CheckoutRequestID,
            ResponseCode,
            ResponseDescription,
            CustomerMessage
        }
        """

        timestamp = self._timestamp()
        password = self._password(timestamp)
        access_token = self._get_access_token()

        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"

        payload = {
            "BusinessShortCode": int(self.shortcode),
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": int(phone),
            "PartyB": int(self.shortcode),
            "PhoneNumber": int(phone),
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference[:12],
            "TransactionDesc": description[:60],
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        data = response.json() if response.content else {}

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail={"daraja_error": data}
            )

        return data


# Singleton instance
mpesa_client = MpesaClient()