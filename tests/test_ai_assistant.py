"""Tests for utils/ai_assistant.py (the employee chat assistant's context
builder + Claude call) and the /api/employee/chat route in
blueprints/employee_portal.py.

The real Anthropic API is never called here — `_call_claude` (the raw
urllib.request layer) is monkeypatched in `ask_assistant` tests, and the
route tests monkeypatch `ask_assistant` itself, matching the existing
convention of not mocking the code under test but isolating the
third-party network call (see tests/test_face_utils.py)."""
import utils.ai_assistant as ai_assistant
import blueprints.employee_portal as employee_portal_module
from utils.ai_assistant import (
    build_employee_context, ask_assistant, _sanitize_history, MAX_MESSAGE_LEN,
)


class TestBuildEmployeeContext:
    def test_includes_basic_profile_fields(self, db_engine, seed_employee):
        cur = db_engine.cursor()
        context = build_employee_context(cur, seed_employee["employee_id"])
        cur.close()
        assert seed_employee["employee_id"] in context
        assert seed_employee["name"] in context

    def test_unknown_employee_returns_not_found_message(self, db_engine):
        cur = db_engine.cursor()
        context = build_employee_context(cur, "NO_SUCH_EMP")
        cur.close()
        assert "No employee record found" in context

    def test_does_not_crash_with_no_leave_or_attendance_history(self, db_engine, seed_employee):
        cur = db_engine.cursor()
        context = build_employee_context(cur, seed_employee["employee_id"])
        cur.close()
        assert isinstance(context, str) and len(context) > 0


class TestSanitizeHistory:
    def test_keeps_well_formed_turns(self):
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        assert _sanitize_history(history) == history

    def test_drops_malformed_entries(self):
        history = [
            {"role": "user", "content": "ok"},
            {"role": "system", "content": "should be dropped"},
            {"role": "user", "content": 12345},
            "not-a-dict",
            {"content": "missing role"},
        ]
        result = _sanitize_history(history)
        assert result == [{"role": "user", "content": "ok"}]

    def test_truncates_long_content(self):
        long_text = "x" * (MAX_MESSAGE_LEN + 500)
        result = _sanitize_history([{"role": "user", "content": long_text}])
        assert len(result[0]["content"]) == MAX_MESSAGE_LEN

    def test_caps_to_max_history_turns(self):
        history = [{"role": "user", "content": str(i)} for i in range(20)]
        result = _sanitize_history(history)
        assert len(result) == ai_assistant.MAX_HISTORY_TURNS
        assert result[-1]["content"] == "19"

    def test_none_history_returns_empty(self):
        assert _sanitize_history(None) == []


class TestAskAssistant:
    def test_empty_message_rejected(self):
        ok, reply = ask_assistant("some context", "   ")
        assert ok is False
        assert "type a question" in reply.lower()

    def test_overlong_message_rejected(self):
        ok, reply = ask_assistant("ctx", "x" * (MAX_MESSAGE_LEN + 1))
        assert ok is False
        assert "too long" in reply.lower()

    def test_missing_api_key_returns_friendly_error(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
        ok, reply = ask_assistant("ctx", "How many leave days do I have?")
        assert ok is False
        assert "isn't configured" in reply.lower()

    def test_successful_call_returns_model_text(self, monkeypatch):
        def _fake_call(system_prompt, messages):
            assert system_prompt.startswith("You are the HR assistant")
            assert messages[-1] == {"role": "user", "content": "How many leave days do I have?"}
            return "You have 5 leave days remaining.", None

        monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(ai_assistant, "_call_claude", _fake_call)
        ok, reply = ask_assistant("Leave balance: 5 days", "How many leave days do I have?")
        assert ok is True
        assert reply == "You have 5 leave days remaining."

    def test_api_failure_returns_friendly_error_not_exception(self, monkeypatch):
        monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(ai_assistant, "_call_claude", lambda s, m: (None, "network error: simulated outage"))
        ok, reply = ask_assistant("ctx", "hello")
        assert ok is False
        assert "couldn't reach" in reply.lower()

    def test_history_passed_through_to_messages(self, monkeypatch):
        captured = {}

        def _fake_call(system_prompt, messages):
            captured["messages"] = messages
            return "ok", None

        monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(ai_assistant, "_call_claude", _fake_call)
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello there"}]
        ask_assistant("ctx", "follow-up question", history)
        assert captured["messages"][0] == {"role": "user", "content": "hi"}
        assert captured["messages"][-1] == {"role": "user", "content": "follow-up question"}

    def test_real_http_call_hits_urlopen_with_expected_request(self, monkeypatch):
        """One test exercises _call_claude itself (not ask_assistant), mocking
        only urllib.request.urlopen — the actual network boundary — to prove
        the request is built correctly (headers, model, message shape)."""
        import json as _json

        captured = {}

        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False

            def read(self):
                return _json.dumps({"content": [{"type": "text", "text": "Hi there!"}]}).encode()

        def _fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
            captured["body"] = _json.loads(req.data.decode())
            return _FakeResp()

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.setattr(ai_assistant.urllib.request, "urlopen", _fake_urlopen)
        text, err = ai_assistant._call_claude("system prompt", [{"role": "user", "content": "hi"}])
        assert err is None
        assert text == "Hi there!"
        assert captured["url"] == "https://api.anthropic.com/v1/messages"
        assert captured["headers"]["x-api-key"] == "sk-test-123"
        assert captured["body"]["model"] == "claude-sonnet-5"
        assert captured["body"]["messages"] == [{"role": "user", "content": "hi"}]


class TestN8nBackend:
    """n8n is tried first (when N8N_WEBHOOK_URL is set), falling back to
    Claude on any failure -- see utils/ai_assistant.py's module docstring
    for the request/response contract."""

    def test_n8n_not_configured_falls_straight_through_to_claude(self, monkeypatch):
        monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(ai_assistant, "_call_claude", lambda s, m: ("claude reply", None))
        ok, reply = ask_assistant("ctx", "hi")
        assert ok is True
        assert reply == "claude reply"

    def test_neither_backend_configured_returns_friendly_error(self, monkeypatch):
        monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        ok, reply = ask_assistant("ctx", "hi")
        assert ok is False
        assert "isn't configured" in reply.lower()

    def test_successful_n8n_call_is_used_and_claude_is_not_called(self, monkeypatch):
        monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example.com/webhook/chat")
        monkeypatch.setattr(ai_assistant, "_call_n8n", lambda url, emp_id, ctx, msg, turns: ("n8n reply", None))
        monkeypatch.setattr(ai_assistant, "_call_claude", lambda s, m: (_ for _ in ()).throw(AssertionError("Claude should not be called")))
        ok, reply = ask_assistant("ctx", "hi", emp_id="EMP001")
        assert ok is True
        assert reply == "n8n reply"

    def test_n8n_failure_falls_back_to_claude_when_configured(self, monkeypatch):
        monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example.com/webhook/chat")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(ai_assistant, "_call_n8n", lambda url, emp_id, ctx, msg, turns: (None, "network error: simulated outage"))
        monkeypatch.setattr(ai_assistant, "_call_claude", lambda s, m: ("claude fallback reply", None))
        ok, reply = ask_assistant("ctx", "hi")
        assert ok is True
        assert reply == "claude fallback reply"

    def test_n8n_failure_with_no_claude_configured_returns_friendly_error(self, monkeypatch):
        monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example.com/webhook/chat")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(ai_assistant, "_call_n8n", lambda url, emp_id, ctx, msg, turns: (None, "HTTP 500"))
        ok, reply = ask_assistant("ctx", "hi")
        assert ok is False
        assert "couldn't reach" in reply.lower()

    def test_n8n_payload_shape(self, monkeypatch):
        captured = {}

        def _fake_call(url, emp_id, ctx, msg, turns):
            captured.update(url=url, emp_id=emp_id, ctx=ctx, msg=msg, turns=turns)
            return "ok", None

        monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example.com/webhook/chat")
        monkeypatch.setattr(ai_assistant, "_call_n8n", _fake_call)
        ask_assistant("employee context here", "What's my leave balance?", emp_id="EMP007")
        assert captured["url"] == "https://n8n.example.com/webhook/chat"
        assert captured["emp_id"] == "EMP007"
        assert captured["ctx"] == "employee context here"
        assert captured["msg"] == "What's my leave balance?"
        assert captured["turns"][-1] == {"role": "user", "content": "What's my leave balance?"}

    def test_call_n8n_builds_expected_request_and_parses_reply(self, monkeypatch):
        import json as _json

        captured = {}

        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return _json.dumps({"reply": "Here's your answer"}).encode()

        def _fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
            captured["body"] = _json.loads(req.data.decode())
            captured["timeout"] = timeout
            return _FakeResp()

        monkeypatch.setenv("N8N_WEBHOOK_SECRET", "shh-secret")
        monkeypatch.setattr(ai_assistant.urllib.request, "urlopen", _fake_urlopen)
        text, err = ai_assistant._call_n8n(
            "https://n8n.example.com/webhook/chat", "EMP001", "ctx text",
            "hello", [{"role": "user", "content": "hello"}],
        )
        assert err is None
        assert text == "Here's your answer"
        assert captured["url"] == "https://n8n.example.com/webhook/chat"
        assert captured["headers"]["x-webhook-secret"] == "shh-secret"
        assert captured["body"] == {
            "employee_id": "EMP001", "message": "hello",
            "history": [{"role": "user", "content": "hello"}], "context": "ctx text",
        }

    def test_call_n8n_no_secret_header_when_unset(self, monkeypatch):
        import json as _json

        captured = {}

        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return _json.dumps({"reply": "ok"}).encode()

        def _fake_urlopen(req, timeout=None):
            captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
            return _FakeResp()

        monkeypatch.delenv("N8N_WEBHOOK_SECRET", raising=False)
        monkeypatch.setattr(ai_assistant.urllib.request, "urlopen", _fake_urlopen)
        ai_assistant._call_n8n("https://n8n.example.com/webhook/chat", "EMP001", "ctx", "hi", [])
        assert "x-webhook-secret" not in captured["headers"]

    def test_call_n8n_missing_reply_field_is_treated_as_failure(self, monkeypatch):
        import json as _json

        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return _json.dumps({"ok": True}).encode()

        monkeypatch.setattr(ai_assistant.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp())
        text, err = ai_assistant._call_n8n("https://n8n.example.com/webhook/chat", "EMP001", "ctx", "hi", [])
        assert text is None
        assert "reply" in err

    def test_call_n8n_malformed_json_is_treated_as_failure(self, monkeypatch):
        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return b"not json"

        monkeypatch.setattr(ai_assistant.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp())
        text, err = ai_assistant._call_n8n("https://n8n.example.com/webhook/chat", "EMP001", "ctx", "hi", [])
        assert text is None
        assert err is not None


class TestChatRoute:
    def test_requires_employee_login(self, client):
        resp = client.post("/api/employee/chat", json={"message": "hi"}, follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_returns_assistant_reply_when_logged_in(self, client, seed_employee, monkeypatch):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]

        monkeypatch.setattr(employee_portal_module, "ask_assistant", lambda context, message, history, emp_id=None: (True, "Mocked reply"))

        resp = client.post("/api/employee/chat", json={"message": "How much leave do I have?"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["reply"] == "Mocked reply"

    def test_invalid_message_type_rejected(self, client, seed_employee):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]
        resp = client.post("/api/employee/chat", json={"message": ["not", "a", "string"]})
        assert resp.status_code == 400

    def test_non_list_history_is_ignored_not_crashed(self, client, seed_employee, monkeypatch):
        with client.session_transaction() as sess:
            sess["employee_id"] = seed_employee["employee_id"]

        captured = {}

        def _fake_ask(context, message, history, emp_id=None):
            captured["history"] = history
            return True, "ok"

        monkeypatch.setattr(employee_portal_module, "ask_assistant", _fake_ask)
        resp = client.post("/api/employee/chat", json={"message": "hi", "history": "not-a-list"})
        assert resp.status_code == 200
        assert captured["history"] == []
