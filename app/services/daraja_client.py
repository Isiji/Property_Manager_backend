# app/services/daraja_client.py
from __future__ import annotations

import base64
import datetime as dt
from typing import Any, Dict

import requests
from fastapi import HTTPException

from app.core.config import settings


class DarajaClient:
    def __init__(self) -> None:
        if not settings.DARAJA_BASE_URL:
            raise RuntimeError("DARAJA_BASE_URL not set")
        if not settings.DARAJA_CONSUMER_KEY or not settings.DARAJA_CONSUMER_SECRET:
            raise RuntimeError("Daraja consumer key/secret not set")
        if not settings.DARAJA_LNM_SHORTCODE or not settings.DARAJA_LNM_PASSKEY:
            raise RuntimeError("LNM shortcode/passkey not set")
        if not settings.DARAJA_CALLBACK_URL:
            raise RuntimeError("DARAJA_CALLBACK_URL not set")

        self.base = settings.DARAJA_BASE_URL.rstrip("/")
        self.ck = settings.DARAJA_CONSUMER_KEY
        self.cs = settings.DARAJA_CONSUMER_SECRET
        self.shortcode = settings.DARAJA_LNM_SHORTCODE
        self.passkey = settings.DARAJA_LNM_PASSKEY
        self.callback_url = settings.DARAJA_CALLBACK_URL

    def _access_token(self) -> str:
        url = f"{self.base}/oauth/v1/generate?grant_type=client_credentials"
        resp = requests.get(url, auth=(self.ck, self.cs), timeout=20)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Daraja OAuth failed: {resp.text}")
        token = (resp.json() or {}).get("access_token")
        if not token:
            raise HTTPException(status_code=502, detail="Daraja OAuth: missing access_token")
        return token

    @staticmethod
    def _timestamp() -> str:
        return dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")

    def _password(self, timestamp: str) -> str:
        raw = f"{self.shortcode}{self.passkey}{timestamp}".encode("utf-8")
        return base64.b64encode(raw).decode("utf-8")

    def initiate_stk_push(self, *, phone: str, amount: int | float, account_ref: str, description: str) -> Dict[str, Any]:
        timestamp = self._timestamp()
        password = self._password(timestamp)
        token = self._access_token()

        url = f"{self.base}/mpesa/stkpush/v1/processrequest"
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
            "AccountReference": account_ref[:12],
            "TransactionDesc": description[:60],
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        data = resp.json() if resp.content else {}
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail={"daraja_error": data})
        return data


daraja_client = DarajaClient()
