# -*- coding: utf-8 -*-
"""Razorpay Orders API + payment-signature verification for the paid
self-service signup flow (blueprints/billing.py).

Calls the REST API directly over urllib.request (stdlib) rather than the
`razorpay` SDK -- same no-heavy-SDK pattern already used for the Anthropic
API in utils/ai_assistant.py and webhook delivery in utils/alerts.py, so
this needs no new pip dependency.
"""
import os
import json
import base64
import hmac
import hashlib
import urllib.request
import urllib.error

_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
_ORDERS_URL = "https://api.razorpay.com/v1/orders"
_TIMEOUT_SECONDS = 15


def razorpay_configured() -> bool:
    return bool(_KEY_ID and _KEY_SECRET)


def key_id() -> str:
    """Public key ID -- safe to hand to the frontend (Checkout needs it),
    unlike _KEY_SECRET which never leaves this module."""
    return _KEY_ID


def _auth_header() -> str:
    token = base64.b64encode(f"{_KEY_ID}:{_KEY_SECRET}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def create_order(amount_paise: int, receipt_id: str):
    """POST /v1/orders. Returns (order_id, error) -- exactly one is None,
    same convention as utils/ai_assistant.py's _call_claude()."""
    if not razorpay_configured():
        return None, "Payments are not configured yet. Contact support."
    body = json.dumps({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt_id,
        "payment_capture": 1,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": _auth_header()}
    req = urllib.request.Request(_ORDERS_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("error", {}).get("description", str(e))
        except Exception:
            msg = str(e)
        return None, f"Razorpay order creation failed: {msg}"
    except urllib.error.URLError as e:
        return None, f"network error contacting Razorpay: {e.reason}"
    except Exception as e:
        return None, f"unexpected error creating order: {e}"

    order_id = data.get("id")
    if not order_id:
        return None, "Razorpay did not return an order ID."
    return order_id, None


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """HMAC-SHA256 of "order_id|payment_id" with the key secret, per
    Razorpay's documented Checkout success-callback verification contract
    -- mirrors utils/alerts.py's _sign() HMAC pattern. Constant-time
    compare (hmac.compare_digest), never a plain == on a MAC."""
    if not razorpay_configured() or not (order_id and payment_id and signature):
        return False
    expected = hmac.new(
        _KEY_SECRET.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
