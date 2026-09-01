# -*- coding: utf-8 -*-
"""Tests for the generic POST /webhooks/<provider> receiver
(blueprints/webhooks.py) -- signature verification and dispatch to
registered handlers. blueprints/auto_debit.py's own webhook-driven
_handle_* functions are unit-tested directly in tests/test_auto_debit.py;
this file stays focused on receive_webhook() itself: unknown providers,
signature verification (mocked at utils.razorpay_utils.verify_webhook_signature,
the boundary blueprints/webhooks.py calls through), and correct dispatch
via register_webhook_handler()'s _HANDLERS table.

Run with:
    python -m pytest tests/test_webhooks.py -v
"""
import blueprints.webhooks as webhooks_module


class TestReceiveWebhook:
    def test_unknown_provider_returns_404_without_checking_signature(self, client, monkeypatch):
        def _boom(*a, **k):
            raise AssertionError("verify_webhook_signature must not be called for an unrecognized provider")
        monkeypatch.setattr("blueprints.webhooks.verify_webhook_signature", _boom)

        resp = client.post("/webhooks/stripe", json={"event": "whatever"})
        assert resp.status_code == 404

    def test_invalid_signature_rejected(self, client, monkeypatch):
        monkeypatch.setattr("blueprints.webhooks.verify_webhook_signature", lambda *a, **k: False)
        resp = client.post("/webhooks/razorpay", json={"event": "subscription.charged"})
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_valid_signature_dispatches_to_registered_handler(self, client, monkeypatch):
        monkeypatch.setattr("blueprints.webhooks.verify_webhook_signature", lambda *a, **k: True)
        received = []
        monkeypatch.setitem(webhooks_module._HANDLERS, ("razorpay", "test.custom_event"),
                             lambda payload: received.append(payload))

        payload = {"event": "test.custom_event", "payload": {"foo": "bar"}}
        resp = client.post("/webhooks/razorpay", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        assert received == [payload]

    def test_valid_signature_unhandled_event_still_returns_200(self, client, monkeypatch):
        # An authentic event with no registered handler is not a delivery
        # failure Razorpay should retry -- still a 200.
        monkeypatch.setattr("blueprints.webhooks.verify_webhook_signature", lambda *a, **k: True)
        resp = client.post("/webhooks/razorpay", json={"event": "some.event.nobody.handles"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_valid_signature_dispatches_only_to_matching_event(self, client, monkeypatch):
        monkeypatch.setattr("blueprints.webhooks.verify_webhook_signature", lambda *a, **k: True)
        calls_a, calls_b = [], []
        monkeypatch.setitem(webhooks_module._HANDLERS, ("razorpay", "test.event.a"), lambda p: calls_a.append(p))
        monkeypatch.setitem(webhooks_module._HANDLERS, ("razorpay", "test.event.b"), lambda p: calls_b.append(p))

        resp = client.post("/webhooks/razorpay", json={"event": "test.event.a"})
        assert resp.status_code == 200
        assert len(calls_a) == 1
        assert len(calls_b) == 0
