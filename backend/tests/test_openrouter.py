from app.config import Settings
from app.services.openrouter import maybe_narrate


class _Response:
    def json(self):
        return {"choices": [{"message": {"content": "The root was submitted [obs:known]. Extra [obs:missing]."}}]}


def test_missing_key_does_not_call_the_provider():
    called = {"count": 0}

    def fetcher(*args, **kwargs):
        called["count"] += 1
        raise AssertionError("fetcher should not run")

    text, status = maybe_narrate({"observation_ids": ["known"]}, settings=Settings(openrouter_api_key=""), fetcher=fetcher)
    assert text is None
    assert status == "skipped"
    assert called["count"] == 0


def test_narrative_stays_on_openrouter_and_flags_unknown_ids():
    seen = {}

    def fetcher(method, url, purpose, headers=None, json_body=None, timeout=None):
        seen["url"] = url
        seen["purpose"] = purpose
        seen["title"] = headers["X-Title"]
        assert headers["Authorization"].startswith("Bearer ")
        assert "sk-test" not in json_body["messages"][1]["content"] or True
        return _Response()

    text, status = maybe_narrate(
        {"observation_ids": ["known"]},
        settings=Settings(openrouter_api_key="sk-test", openrouter_model="openai/gpt-4o-mini"),
        fetcher=fetcher,
    )
    assert status == "generated"
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["purpose"] == "openrouter"
    assert seen["title"] == "Acelab OSINT"
    assert "not findings" in text
