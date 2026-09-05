"""Which AI provider a key belongs to, worked out from the key itself.

One box on the screen, not three. Somebody pasting a key should not have to
tell Ripple which company issued it: the key says so in its first few
characters, and asking is one more thing to get wrong on a screen whose whole
job is to be checkable.

All three providers speak the same OpenAI-shaped ``/chat/completions``, so
there is one code path and only the address, the key and the model change.
Google's is its own OpenAI-compatible endpoint, which was confirmed live rather
than taken from documentation.

The model list is NOT written down here. A hand-typed list of model names is
wrong within months and then tells somebody a model exists that does not. It is
fetched from the provider with the key they just pasted, which proves the key
and produces the real list in the same call. The names below are only an
ORDER OF PREFERENCE applied to whatever comes back -- if none of them is in the
list, the first usable model is used and the screen says which.
"""
from __future__ import annotations

PROVIDERS: tuple[dict, ...] = (
    {
        "id": "openai",
        "label": "OpenAI",
        # Longest first: a project key starts with the legacy prefix too.
        "prefixes": ("sk-proj-", "sk-svcacct-", "sk-admin-", "sk-"),
        "base_url": "https://api.openai.com/v1",
        "where": "platform.openai.com/api-keys",
        "prefer": ("gpt-5", "gpt-4.1", "gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"),
    },
    {
        "id": "gemini",
        "label": "Google Gemini",
        "prefixes": ("AIza",),
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "where": "aistudio.google.com/apikey",
        "prefer": ("gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash",
                   "gemini-1.5-pro", "gemini-1.5-flash"),
    },
    {
        "id": "groq",
        "label": "Groq",
        "prefixes": ("gsk_",),
        "base_url": "https://api.groq.com/openai/v1",
        "where": "console.groq.com",
        "prefer": ("openai/gpt-oss-120b", "llama-3.3-70b-versatile",
                   "openai/gpt-oss-20b", "llama-3.1-8b-instant"),
    },
)

# Keys Ripple can recognise but cannot use.
#
# Naming the company beats "that key was rejected", which sends somebody to
# check a key that is perfectly good. It also stops an Anthropic key being read
# as an OpenAI one: both begin "sk-", and without this the longer prefix would
# be tested against the shorter one and lose.
KNOWN_BUT_UNSUPPORTED: tuple[dict, ...] = (
    {"prefixes": ("sk-ant-",), "label": "Anthropic"},
    {"prefixes": ("hf_",), "label": "Hugging Face"},
    {"prefixes": ("xai-",), "label": "xAI"},
    {"prefixes": ("sk-or-",), "label": "OpenRouter"},
    {"prefixes": ("r8_",), "label": "Replicate"},
    {"prefixes": ("ghp_", "github_pat_"), "label": "GitHub"},
)

# Model ids that are not chat models. A provider's list is mostly these -- audio,
# images, embeddings, moderation - and offering one produces a baffling failure
# at the moment somebody is trying to read an email.
_NOT_CHAT = (
    "embed", "embedding", "whisper", "tts", "audio", "speech", "transcribe",
    "dall-e", "image", "imagen", "vision-only", "moderation", "rerank",
    "guard", "safety", "veo", "video", "clip", "distil-whisper", "playai",
    "aqa", "learnlm", "gemma",
)


def detect(key: str) -> dict | None:
    """The provider that issued this key, or None if it is not one we can use."""
    key = (key or "").strip()
    if not key:
        return None
    for unsupported in KNOWN_BUT_UNSUPPORTED:
        if key.startswith(unsupported["prefixes"]):
            return None
    best: dict | None = None
    longest = -1
    for provider in PROVIDERS:
        for prefix in provider["prefixes"]:
            if key.startswith(prefix) and len(prefix) > longest:
                best, longest = provider, len(prefix)
    return best


def name_of_unsupported(key: str) -> str:
    """The company whose key this is, when Ripple cannot use it. '' otherwise."""
    key = (key or "").strip()
    for unsupported in KNOWN_BUT_UNSUPPORTED:
        if key.startswith(unsupported["prefixes"]):
            return unsupported["label"]
    return ""


def by_id(provider_id: str) -> dict | None:
    for provider in PROVIDERS:
        if provider["id"] == provider_id:
            return provider
    return None


def is_chat_model(model_id: str) -> bool:
    """Could this model hold a conversation and return JSON?

    Deliberately a denylist rather than an allowlist. A new chat model appearing
    and being hidden is the worse mistake: it looks like the provider is broken.
    """
    low = (model_id or "").lower()
    if not low:
        return False
    return not any(word in low for word in _NOT_CHAT)


def rank_models(provider: dict | None, models: list[str]) -> list[str]:
    """The provider's own list, with the ones we would choose first at the top.

    Everything the provider returned is kept. Ripple has no business hiding a
    model somebody is paying for because it has not heard of it.
    """
    usable = [m for m in models if is_chat_model(m)]
    prefer = list((provider or {}).get("prefer", ()))

    def rank(model_id: str) -> tuple:
        low = model_id.lower()
        for i, wanted in enumerate(prefer):
            if low == wanted.lower():
                return (0, i, low)
        for i, wanted in enumerate(prefer):
            if low.startswith(wanted.lower()):
                return (1, i, low)
        return (2, 0, low)

    return sorted(usable, key=rank)
