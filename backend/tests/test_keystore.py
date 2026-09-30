import threading

import pytest

from skillgap.keystore import KeyStore

FAKE = "sk-ant-test-0000000000000000"


@pytest.fixture(autouse=True)
def _no_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_set_get_clear():
    store = KeyStore()
    assert store.get() is None
    store.set(FAKE)
    assert store.get() == FAKE
    store.clear()
    assert store.get() is None


def test_session_key_wins_over_env_and_env_is_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-0000000000000000")
    store = KeyStore()
    assert store.get() == "env-key-0000000000000000"
    assert store.status() == {"configured": True, "source": "environment"}
    store.set(FAKE)
    assert store.get() == FAKE
    assert store.status() == {"configured": True, "source": "session"}
    store.clear()
    assert store.get() == "env-key-0000000000000000"
    assert store.status()["source"] == "environment"


def test_empty_env_var_is_ignored(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    store = KeyStore()
    assert store.get() is None
    assert store.status() == {"configured": False, "source": None}


def test_status_and_repr_never_leak_the_key():
    store = KeyStore()
    store.set(FAKE)
    status = store.status()
    assert set(status) == {"configured", "source"}
    for text in (str(status), repr(store), str(store)):
        assert FAKE not in text
        assert "0000" not in text
    assert repr(store) == "KeyStore(configured=True, source='session')"


def test_whitespace_is_stripped():
    store = KeyStore()
    store.set(f"  {FAKE}\n")
    assert store.get() == FAKE


@pytest.mark.parametrize("bad", [
    "",
    "     ",
    "sk-ant-short",
    "x" * 301,
    "sk-ant-test-0000 000000000000",
    "sk-ant-test-0000\n000000000000",
    "sk-ant-test-0000\t000000000000",
    "sk-ant-test-0000\x00000000000",
    "sk-ant-test-chave-inválida-000000",
])
def test_invalid_keys_are_rejected_without_echoing_them(bad):
    store = KeyStore()
    with pytest.raises(ValueError) as info:
        store.set(bad)
    message = str(info.value)
    if bad.strip():
        assert bad.strip() not in message
    assert message  # Portuguese message present
    assert store.get() is None


def test_rejected_key_keeps_previous_key():
    store = KeyStore()
    store.set(FAKE)
    with pytest.raises(ValueError):
        store.set("curta")
    assert store.get() == FAKE


def test_thread_safety_smoke():
    store = KeyStore()
    errors = []

    def worker(i):
        try:
            for _ in range(200):
                store.set(f"sk-ant-test-{i:016d}")
                store.get()
                store.status()
                store.clear()
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == []
