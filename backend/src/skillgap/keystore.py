"""Guarda a chave da API Anthropic apenas na memória do processo."""
import os
import threading

MIN_LENGTH = 20
MAX_LENGTH = 300


def _validate(key: str) -> str:
    key = key.strip()
    if not key:
        raise ValueError("A chave não pode ser vazia.")
    if len(key) < MIN_LENGTH:
        raise ValueError("A chave é curta demais para ser válida.")
    if len(key) > MAX_LENGTH:
        raise ValueError("A chave é longa demais para ser válida.")
    if any(not (33 <= ord(ch) <= 126) for ch in key):
        raise ValueError(
            "A chave contém espaços ou caracteres inválidos; use apenas ASCII imprimível.")
    return key


class KeyStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session_key: str | None = None

    def get(self) -> str | None:
        with self._lock:
            if self._session_key:
                return self._session_key
        return os.environ.get("ANTHROPIC_API_KEY") or None

    def set(self, key: str) -> None:
        clean = _validate(key)
        with self._lock:
            self._session_key = clean

    def clear(self) -> None:
        with self._lock:
            self._session_key = None

    def status(self) -> dict:
        with self._lock:
            if self._session_key:
                return {"configured": True, "source": "session"}
        if os.environ.get("ANTHROPIC_API_KEY"):
            return {"configured": True, "source": "environment"}
        return {"configured": False, "source": None}

    def __repr__(self) -> str:
        status = self.status()
        return f"KeyStore(configured={status['configured']}, source={status['source']!r})"

    __str__ = __repr__
