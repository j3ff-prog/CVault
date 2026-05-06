"""
services/paystack_service.py
Verifies Paystack transactions and webhook signatures.
"""
import os
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")


def verify_transaction(reference: str) -> dict:
    if not PAYSTACK_SECRET_KEY:
        raise RuntimeError("PAYSTACK_SECRET_KEY not set in environment.")
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Paystack API request failed: {e}")
    data = resp.json()
    if not data.get("status"):
        raise ValueError(f"Paystack error: {data.get('message', 'Unknown')}")
    tx = data.get("data", {})
    if tx.get("status") != "success":
        raise ValueError(f"Payment not successful. Status: {tx.get('status')}")
    return tx


def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    if not PAYSTACK_SECRET_KEY:
        return False
    expected = hmac.new(
        PAYSTACK_SECRET_KEY.encode("utf-8"),
        payload_bytes,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def get_plan_from_amount(amount_kobo: int) -> str:
    amount_kes = amount_kobo // 100
    if amount_kes == 49:
        return "single"
    elif amount_kes == 99:
        return "triple"
    elif amount_kes == 199:
        return "unlimited"
    return "unknown"
