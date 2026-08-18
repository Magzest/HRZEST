"""Shared Anthropic Claude API client for the lightweight AI-assisted HR
features (resume parsing, interview evaluation, HR helpdesk). Each caller
wraps this in its own try/except and falls back to heuristic rules on
failure, so this raises rather than swallowing errors itself.

utils/ai_assistant.py's employee-chat client is intentionally separate: it
returns a (text, error) tuple, distinguishes HTTP/network/n8n failure modes,
and supports a system prompt — a different contract than the simple
prompt-in/text-out callers here.
"""
import json
import os
import urllib.request

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-sonnet-5"


def call_claude(prompt, max_tokens=450, timeout=10):
    """POST `prompt` to the Claude Messages API and return the model's text reply.

    Raises RuntimeError if ANTHROPIC_API_KEY isn't set, or propagates any
    request/parsing exception — callers catch and fall back to heuristics."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    payload = {
        "model": _MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        _API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]
