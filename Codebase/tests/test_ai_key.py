"""Tests for turning the AI on from the Settings screen.

The key is a secret on exactly the same terms as the GitHub access token, and
the thing most worth guarding is the same: it must never come back out of the
app, in any response, ever. Everything else here exists so that "AI is on"
means the model actually answered, not merely that a key was typed somewhere.

Three providers now, and ONE box. Which company issued a key is worked out from
the key itself rather than asked for, because asking is one more thing to get
wrong -- and because a key silently sent to the wrong provider fails in a way
that reads as "your key is bad".

No test touches the network -- the two calls Ripple would make are stubbed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ripple import ai                                           # noqa: E402
from ripple import api as rapi                                  # noqa: E402
from ripple import providers                                    # noqa: E402
from ripple.api import app                                      # noqa: E402
from ripple.config import Settings, settings                    # noqa: E402

SECRET = "gsk_thisisnotarealgroqkey000000000000"
OPENAI_SECRET = "sk-proj-thisisnotarealopenaikey0000000000"
GEMINI_SECRET = "AIzaSyThisIsNotARealGoogleKey00000000000"

GROQ_MODELS = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "whisper-large-v3"]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_key_left_behind():
    """No test may leak a key into the next one."""
    yield
    rapi._state.update({"aiKey": "", "aiModel": "", "aiModels": []})


@pytest.fixture
def model_answers(monkeypatch):
    """The provider lists its models and the model replies, both recorded."""
    seen: dict = {}

    def fake_chat(messages, cfg, max_tokens=1400):
        seen["key"] = cfg.ai_key
        seen["model"] = cfg.ai_model
        seen["endpoint"] = cfg.ai_endpoint()
        return '{"ok": true}'

    def fake_models(cfg):
        seen["listedFor"] = cfg.ai_key
        return list(GROQ_MODELS)

    monkeypatch.setattr(ai, "_chat", fake_chat)
    monkeypatch.setattr(ai, "list_models", fake_models)
    return seen


@pytest.fixture
def model_refuses(monkeypatch):
    def boom(*_a, **_kw):
        raise ai.AIUnavailable("the model returned 401: invalid api key")

    monkeypatch.setattr(ai, "_chat", boom)
    monkeypatch.setattr(ai, "list_models", boom)


# ── the secret ─────────────────────────────────────────────────────────────
def test_the_key_never_comes_back_out(client, model_answers):
    r = client.post("/api/ai/connect", json={"key": SECRET})
    assert r.status_code == 200, r.text
    assert SECRET not in r.text

    # ...nor from anywhere else that reports on the AI.
    for path, method in (("/api/health", "get"), ("/api/ai/check", "post")):
        body = getattr(client, method)(path).text
        assert SECRET not in body, path
        assert "gsk_thisisnot" not in body, path


def test_health_says_a_key_is_set_without_saying_what(client, model_answers):
    client.post("/api/ai/connect", json={"key": SECRET})
    h = client.get("/api/health").json()["ai"]
    assert h["available"] is True
    assert h["keyFrom"] == "entered"
    assert "key" not in h and "apiKey" not in h


# ── one box, three providers ───────────────────────────────────────────────
@pytest.mark.parametrize("key,expect", [
    ("gsk_abc", "groq"),
    ("sk-abc", "openai"),
    ("sk-proj-abc", "openai"),
    ("sk-svcacct-abc", "openai"),
    ("AIzaSyAbc", "gemini"),
])
def test_a_key_names_its_own_provider(key, expect):
    """Nobody should have to tell Ripple who issued a key. It is in the key."""
    found = providers.detect(key)
    assert found and found["id"] == expect, key


@pytest.mark.parametrize("key,maker", [
    ("sk-ant-api03-abc", "Anthropic"),
    ("hf_abc", "Hugging Face"),
    ("sk-or-v1-abc", "OpenRouter"),
    ("ghp_abc", "GitHub"),
])
def test_a_key_ripple_cannot_use_is_named_rather_than_guessed_at(key, maker):
    """An Anthropic key begins "sk-" exactly as an OpenAI one does. Read as
    OpenAI it would be sent to the wrong company and come back rejected, and
    somebody would spend the afternoon checking a key that is perfectly good."""
    assert providers.detect(key) is None, key
    assert providers.name_of_unsupported(key) == maker


def test_the_screen_is_given_the_prefixes_so_it_can_say_who_issued_a_key(client):
    """The screen names the provider as the key is typed, before anything is
    sent anywhere. It reads the prefixes from here so there is one list."""
    h = client.get("/api/health").json()["ai"]
    ids = {p["id"] for p in h["providers"]}
    assert ids == {"openai", "gemini", "groq"}
    assert all(p["prefixes"] and p["label"] and p["where"] for p in h["providers"])
    assert any(u["label"] == "Anthropic" for u in h["unsupported"])


def test_a_key_from_nobody_we_know_is_refused_with_the_reason(client, model_answers):
    r = client.post("/api/ai/connect", json={"key": "not-a-key-at-all"})
    assert r.status_code == 400
    assert "does not recognise" in r.json()["detail"]
    assert client.get("/api/health").json()["ai"]["available"] is False


def test_an_anthropic_key_is_refused_by_name(client, model_answers):
    r = client.post("/api/ai/connect", json={"key": "sk-ant-api03-whatever"})
    assert r.status_code == 400
    assert "Anthropic" in r.json()["detail"]


@pytest.mark.parametrize("key,host", [
    (SECRET, "api.groq.com"),
    (OPENAI_SECRET, "api.openai.com"),
    (GEMINI_SECRET, "generativelanguage.googleapis.com"),
])
def test_the_key_decides_where_the_request_goes(key, host):
    cfg = Settings()
    cfg.ai_key = key
    cfg.ai_base_url = ""
    assert host in cfg.ai_endpoint()


# ── turning it on ──────────────────────────────────────────────────────────
def test_a_key_that_works_turns_the_ai_on(client, model_answers):
    assert client.get("/api/health").json()["ai"]["available"] is False
    out = client.post("/api/ai/connect", json={"key": SECRET}).json()
    assert out["ai"]["available"] is True
    assert model_answers["key"] == SECRET, "the entered key must be the one used"
    assert out["ai"]["provider"] == "groq"


def test_a_key_that_does_not_work_is_refused_and_not_kept(client, model_refuses):
    r = client.post("/api/ai/connect", json={"key": SECRET})
    assert r.status_code == 502
    assert "401" in r.json()["detail"]
    assert client.get("/api/health").json()["ai"]["available"] is False, \
        "a rejected key must not be left switched on"


def test_connecting_with_no_key_at_all_is_refused(client):
    r = client.post("/api/ai/connect", json={"key": ""})
    assert r.status_code == 400


def test_forgetting_the_key_turns_the_ai_off(client, model_answers):
    client.post("/api/ai/connect", json={"key": SECRET})
    out = client.post("/api/ai/forget").json()
    assert out["ai"]["available"] is False
    assert out["ai"]["keyFrom"] == ""
    assert out["ai"]["models"] == []


# ── the model list is the provider's own answer ────────────────────────────
def test_the_model_list_comes_from_the_provider_not_from_ripple(client, model_answers):
    """A list of model names written into the code is wrong within months, and
    then it offers a model that no longer exists to somebody in the middle of
    reading an email. Asking the provider proves the key at the same time."""
    assert client.get("/api/health").json()["ai"]["models"] == [], \
        "nothing to show before a key has been accepted"
    out = client.post("/api/ai/connect", json={"key": SECRET}).json()
    assert model_answers["listedFor"] == SECRET
    assert out["ai"]["models"], "the provider's list should be on the screen now"


def test_a_model_that_cannot_hold_a_conversation_is_not_offered(client, model_answers):
    """A provider's list is mostly audio, images and embeddings. Offering one
    produces a baffling failure at the worst moment."""
    out = client.post("/api/ai/connect", json={"key": SECRET}).json()
    assert "whisper-large-v3" not in out["ai"]["models"]
    assert "openai/gpt-oss-120b" in out["ai"]["models"]


def test_the_model_ripple_picks_is_the_preferred_one_that_actually_exists(client, model_answers):
    out = client.post("/api/ai/connect", json={"key": SECRET}).json()
    assert out["ai"]["model"] == "openai/gpt-oss-120b"
    assert out["ai"]["models"][0] == "openai/gpt-oss-120b"


def test_an_unknown_model_is_kept_rather_than_hidden():
    """Ripple has no business hiding a model somebody is paying for because it
    has not heard of it. It goes to the bottom of the list, not off it."""
    ranked = providers.rank_models(providers.by_id("openai"),
                                   ["something-brand-new", "gpt-4o", "text-embedding-3"])
    assert "something-brand-new" in ranked
    assert ranked[0] == "gpt-4o", "a preferred one still comes first"
    assert "text-embedding-3" not in ranked, "but an embedding model is not a chat model"


def test_the_chosen_model_is_the_one_called(client, model_answers):
    client.post("/api/ai/connect", json={"key": SECRET})
    client.post("/api/ai/connect", json={"model": "llama-3.3-70b-versatile"})
    client.post("/api/ai/check")
    assert model_answers["model"] == "llama-3.3-70b-versatile"


def test_a_model_the_key_cannot_use_is_refused(client, model_answers):
    client.post("/api/ai/connect", json={"key": SECRET})
    r = client.post("/api/ai/connect", json={"model": "gpt-9-ultra"})
    assert r.status_code == 400
    assert "gpt-9-ultra" in r.json()["detail"]
    assert client.get("/api/health").json()["ai"]["model"] == "openai/gpt-oss-120b", \
        "the working model must survive a refused change"


# ── it must still work with no key at all ──────────────────────────────────
def test_everything_still_runs_with_no_key(client):
    """Manual mode with no AI is the path that must never depend on any of this."""
    scan = client.post("/api/scan", json={
        "upstream": [{"table": "customer_demographics", "attrs": ["market_code"]}],
        "changeKind": "value_change"}).json()
    assert scan["groups"]
    out = client.post("/api/summary", json={"scan": scan, "vals": {}, "useAI": True}).json()
    assert out["summary"] and out["reply"]


def test_a_key_in_the_environment_is_reported_as_such(client, monkeypatch, model_answers):
    monkeypatch.setattr(settings, "ai_key", "gsk_from_the_environment", raising=False)
    h = client.get("/api/health").json()["ai"]
    assert h["available"] is True
    assert h["keyFrom"] == "environment"
    assert "gsk_from_the_environment" not in client.get("/api/health").text


# ── what a person reads when it goes wrong ─────────────────────────────────
@pytest.mark.parametrize("status,body,expect", [
    (401, '{"error":{"message":"Invalid API Key"}}', "mistyped, expired or revoked"),
    # Google answers 400, not 401. Read as a bad request this sends somebody to
    # check their prompt rather than their key. Measured against the real
    # endpoint with a deliberately wrong key.
    (400, '{"error":{"code":400,"message":"Please pass a valid API key","status":'
          '"INVALID_ARGUMENT"}}', "mistyped, expired or revoked"),
    (403, '{"error":{"message":"forbidden"}}', "mistyped, expired or revoked"),
    (429, '{"error":{"message":"rate limit"}}', "allowance on this key is used up"),
    (404, '{"error":{"message":"The model does not exist"}}', "no longer offers"),
    (503, "upstream unavailable", "trouble at its end"),
])
def test_a_failure_is_explained_in_words_not_json(status, body, expect):
    """A blob of provider JSON on screen helps nobody standing in front of it."""
    msg = ai._explain(status, body, settings)
    assert expect in msg
    assert "{" not in msg


def test_the_advice_points_at_the_website_that_issued_the_key():
    """"Create a new one at console.groq.com" is wrong advice for an OpenAI
    key, and following it wastes an afternoon."""
    for key, where in ((SECRET, "console.groq.com"),
                       (OPENAI_SECRET, "platform.openai.com"),
                       (GEMINI_SECRET, "aistudio.google.com")):
        cfg = Settings()
        cfg.ai_key = key
        assert where in ai._explain(401, "{}", cfg)


def test_a_provider_that_dislikes_json_mode_is_asked_again_without_it():
    """All three take an OpenAI-shaped request; not all take every optional
    field of one. Losing the whole call over a field that only makes the answer
    tidier would switch the AI off for a reason nobody could see."""
    assert ai._refused_json_mode(400, '{"error":"Unknown field response_format"}')
    assert ai._refused_json_mode(400, '{"error":"json_object is not supported"}')
    assert not ai._refused_json_mode(400, '{"error":"Please pass a valid API key"}')
    assert not ai._refused_json_mode(500, "response_format")
