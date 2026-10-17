from types import SimpleNamespace

import pytest

from app.services import llm


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls += 1
        content = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "test-key")
    llm.clear_cache()
    yield
    llm.clear_cache()


def test_identical_requests_are_cached(monkeypatch):
    client = FakeClient(['{"a": 1}'])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    assert llm.complete_json("sys", {"x": 1}) == {"a": 1}
    assert llm.complete_json("sys", {"x": 1}) == {"a": 1}
    assert client.calls == 1


def test_malformed_json_gets_one_corrective_retry(monkeypatch):
    client = FakeClient(["not json", '{"ok": true}'])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    assert llm.complete_json("sys", {}) == {"ok": True}
    assert client.calls == 2


def test_repeated_malformed_json_raises(monkeypatch):
    client = FakeClient(["nope", "[1]"])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    with pytest.raises(ValueError):
        llm.complete_json("sys", {})
