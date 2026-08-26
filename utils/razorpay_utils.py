# -*- coding: utf-8 -*-
"""Razorpay REST integration -- one-time Orders (paid signup, seat top-ups)
and recurring Subscriptions (monthly per-employee auto-debit).

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
# Signs incoming webhook payloads (blueprints/auto_debit.py's /webhooks/razorpay)
# -- configured separately from _KEY_ID/_KEY_SECRET in the Razorpay dashboard's
# Webhooks section, since it authenticates Razorpay -> us, not us -> Razorpay.
_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

_API_BASE = "https://api.razorpay.com/v1"
_TIMEOUT_SECONDS = 15


def razorpay_configured() -> bool:
    return bool(_KEY_ID and _KEY_SECRET)


def webhook_configured() -> bool:
    return bool(_WEBHOOK_SECRET)


def key_id() -> str:
    """Public key ID -- safe to hand to the frontend (Checkout needs it),
    unlike _KEY_SECRET which never leaves this module."""
    return _KEY_ID


def _auth_header() -> str:
    token = base64.b64encode(f"{_KEY_ID}:{_KEY_SECRET}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _request(path: str, body: dict = None, method: str = "POST"):
    """Shared REST call against the Razorpay API. Returns (data, error) --
    exactly one is None, same convention as utils/ai_assistant.py's
    _call_claude(). Every Orders/Plans/Customers/Subscriptions call below
    goes through this so the HTTPError/URLError handling only lives once."""
    if not razorpay_configured():
        return None, "Payments are not configured yet. Contact support."
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Authorization": _auth_header()}
    req = urllib.request.Request(f"{_API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("error", {}).get("description", str(e))
        except Exception:
            msg = str(e)
        return None, f"Razorpay request failed: {msg}"
    except urllib.error.URLError as e:
        return None, f"network error contacting Razorpay: {e.reason}"
    except Exception as e:
        return None, f"unexpected error calling Razorpay: {e}"


def create_order(amount_paise: int, receipt_id: str):
    """POST /v1/orders -- a one-time charge (paid signup, seat top-ups).
    Returns (order_id, error)."""
    data, error = _request("/orders", {
        "amount": amount_paise, "currency": "INR", "receipt": receipt_id, "payment_capture": 1,
    })
    if error:
        return None, error
    order_id = data.get("id")
    if not order_id:
        return None, "Razorpay did not return an order ID."
    return order_id, None


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """HMAC-SHA256 of "order_id|payment_id" with the key secret -- Razorpay's
    documented Checkout success-callback verification contract for BOTH a
    one-time Order and a Subscription (the subscription's id stands in for
    order_id in that case; Razorpay uses the identical HMAC scheme for
    both). Constant-time compare (hmac.compare_digest), never a plain ==
    on a MAC."""
    if not razorpay_configured() or not (order_id and payment_id and signature):
        return False
    expected = hmac.new(
        _KEY_SECRET.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_plan(amount_paise: int, item_name: str, period: str = "monthly", interval: int = 1):
    """POST /v1/plans -- a recurring-billing template (amount charged each
    cycle, before any per-subscription `quantity` multiplier). Returns
    (plan_id, error). Created once and cached (blueprints/auto_debit.py
    stores the id in att_master.billing_config) rather than re-created per
    tenant -- one Plan ("₹99/employee/month") is shared by every tenant's
    own Subscription, which is what actually carries that tenant's
    `quantity` (= their employee count)."""
    data, error = _request("/plans", {
        "period": period, "interval": interval,
        "item": {"name": item_name, "amount": amount_paise, "currency": "INR"},
    })
    if error:
        return None, error
    plan_id = data.get("id")
    if not plan_id:
        return None, "Razorpay did not return a plan ID."
    return plan_id, None


def create_customer(name: str, email: str, fail_if_exists: bool = False):
    """POST /v1/customers. Returns (customer_id, error). fail_if_exists=False
    (default) lets Razorpay return the existing customer for a duplicate
    email instead of erroring -- fine here since we key our own
    auto_debit_mandates row by tenant_schema, not by trusting this id to be
    unique across tenants."""
    data, error = _request("/customers", {
        "name": name, "email": email, "fail_existing": "1" if fail_if_exists else "0",
    })
    if error:
        return None, error
    customer_id = data.get("id")
    if not customer_id:
        return None, "Razorpay did not return a customer ID."
    return customer_id, None


def create_subscription(plan_id: str, customer_id: str, quantity: int, total_count: int = 1200):
    """POST /v1/subscriptions. `quantity` is the seat-based-billing lever
    Razorpay documents for exactly this case (variable per-unit recurring
    charge): total billed each cycle = plan.item.amount * quantity.
    total_count=1200 (100 years of monthly cycles) stands in for
    "indefinite" -- Razorpay requires a finite cycle count, and
    cancel_subscription() below is the real way this ever stops. Returns
    (subscription_id, error)."""
    data, error = _request("/subscriptions", {
        "plan_id": plan_id, "customer_id": customer_id, "quantity": max(1, quantity),
        "total_count": total_count, "customer_notify": 1,
    })
    if error:
        return None, error
    subscription_id = data.get("id")
    if not subscription_id:
        return None, "Razorpay did not return a subscription ID."
    return subscription_id, None


def update_subscription_quantity(subscription_id: str, quantity: int):
    """PATCH /v1/subscriptions/{id} -- resyncs the billed quantity to a
    tenant's current headcount (blueprints/auto_debit.py's daily sync job).
    schedule_change_at="now" applies immediately with proration, matching
    Razorpay's documented seat-based-billing guidance (an employee added
    mid-cycle should start being billed for right away, not silently free
    until the next renewal). Returns (ok, error)."""
    data, error = _request(f"/subscriptions/{subscription_id}", {
        "quantity": max(1, quantity), "schedule_change_at": "now",
    }, method="PATCH")
    if error:
        return False, error
    return True, None


def cancel_subscription(subscription_id: str, cancel_at_cycle_end: bool = False):
    """POST /v1/subscriptions/{id}/cancel. Returns (ok, error)."""
    data, error = _request(f"/subscriptions/{subscription_id}/cancel", {
        "cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0,
    })
    if error:
        return False, error
    return True, None


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256 of the raw request body with RAZORPAY_WEBHOOK_SECRET --
    Razorpay's documented webhook authenticity check (X-Razorpay-Signature
    header). Deliberately independent of _KEY_SECRET: the webhook secret is
    configured separately in the Razorpay dashboard's Webhooks section.
    Constant-time compare, same as verify_payment_signature above."""
    if not _WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
