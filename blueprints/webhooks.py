# -*- coding: utf-8 -*-
"""Generic /webhooks/<provider> endpoint -- the shared home for every
server-to-server callback this app receives (Razorpay today, whatever
comes next tomorrow).

Owning this here, once, means a consumer feature (blueprints/auto_debit.py
today) doesn't have to each re-solve: claiming a slice of the shared
/webhooks/ URL namespace (utils/tenant_routing.py's
RESERVED_PATH_SEGMENTS), the CSRF exemption for a route with no session
cookie to carry a token (app.py's _enforce_csrf()), or the
signature-verification boilerplate -- all of that lives here exactly once,
regardless of how many providers/features end up using it.

Features register a handler at *import time* (module level, not inside a
request) via register_webhook_handler(provider, event, handler) -- see
blueprints/auto_debit.py's module-level registration calls for the one
real consumer today. A handler receives the parsed JSON payload and
returns nothing; this module doesn't care what it does with it.
"""
from flask import Blueprint, request, jsonify
from extensions import limiter, log_security_event
from utils.razorpay_utils import verify_webhook_signature

webhooks_bp = Blueprint("webhooks", __name__)

# {(provider, event): handler(payload: dict)} -- populated by each feature
# blueprint at import time via register_webhook_handler() below.
_HANDLERS = {}

# provider -> callable(raw_body: bytes, request) -> bool. Each provider
# signs callbacks differently (Razorpay: HMAC of the raw body against a
# dashboard-configured webhook secret, in a fixed header) -- a second
# provider adds one more entry here, not a second route/blueprint.
_SIGNATURE_VERIFIERS = {
    "razorpay": lambda raw_body, req: verify_webhook_signature(
        raw_body, req.headers.get("X-Razorpay-Signature", "")
    ),
}


def register_webhook_handler(provider: str, event: str, handler):
    """Registers `handler(payload: dict)` to run when POST /webhooks/<provider>
    receives an `event`-named event, after signature verification passes.
    Call this at blueprint import time (module level) -- see
    blueprints/auto_debit.py."""
    _HANDLERS[(provider, event)] = handler


@webhooks_bp.route("/webhooks/<provider>", methods=["POST"])
@limiter.limit("120 per minute")
def receive_webhook(provider):
    """No @admin_required/@api_required -- the caller is a remote
    server with no session cookie or Bearer token, authenticated instead
    by the provider-specific signature check below. Deliberately never
    touches g.tenant_db (this route has no tenant-prefixed URL, same
    posture as blueprints/platform_admin.py's /super_admin/* per that
    module's own docstring) -- registered handlers are expected to work
    entirely off master-schema tables, the same way
    blueprints/auto_debit.py's do."""
    verifier = _SIGNATURE_VERIFIERS.get(provider)
    if not verifier:
        # Unknown provider -- 404 rather than 400, so this doesn't leak
        # which provider names ARE recognized to an unauthenticated caller.
        return jsonify({"ok": False}), 404

    raw_body = request.get_data()
    if not verifier(raw_body, request):
        log_security_event(
            f"webhooks.{provider}_signature_invalid",
            f"{provider} webhook signature verification failed", level="ERROR",
        )
        return jsonify({"ok": False}), 400

    payload = request.get_json(silent=True) or {}
    event = payload.get("event", "")
    handler = _HANDLERS.get((provider, event))
    if handler:
        handler(payload)
    # 200 regardless of whether an event had a registered handler --
    # an unhandled-but-authentic event (one we simply don't act on yet)
    # is not a delivery failure Razorpay should retry.
    return jsonify({"ok": True})
