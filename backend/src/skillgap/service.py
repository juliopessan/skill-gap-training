from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from pathlib import Path

from skillgap.errors import MESSAGES, PipelineError
from skillgap.models import CandidateResult
from skillgap.pipeline import Deps, run_pipeline
from skillgap.store import Store

log = logging.getLogger(__name__)

STALE_MESSAGE = "Processamento interrompido (o servidor foi reiniciado). Envie o CV novamente."


class CandidateService:
    def __init__(self, store: Store, deps: Deps):
        self.store = store
        self.deps = deps
        self._submit_lock = threading.Lock()
        # Premissa: um único processo do servidor é dono do banco. Logo, qualquer
        # registro 'processing' ao iniciar ficou órfão de uma execução interrompida.
        store.fail_stale_processing(STALE_MESSAGE)

    def submit(self, data: bytes, filename: str = "cv.pdf") -> tuple[CandidateResult, bool]:
        sha256 = hashlib.sha256(data).hexdigest()
        with self._submit_lock:
            existing = self.store.find_reusable_by_hash(sha256)
            if existing:
                return existing, False
            result = CandidateResult(id=str(uuid.uuid4()), candidate=Path(filename).stem)
            self.store.save(result, sha256)
            return result, True

    def run(self, candidate_id: str, data: bytes) -> None:
        result = self.store.get(candidate_id)
        if result is None:
            log.warning("Candidato %s não encontrado; nada a processar", candidate_id)
            return

        def on_stage(stage: str) -> None:
            result.stage = stage
            self.store.save(result)

        try:
            fields = run_pipeline(data, self.deps, on_stage)
            fields["candidate"] = (fields["candidate"] or "").strip() or result.candidate
            result = result.model_copy(update={**fields, "status": "done", "stage": "done"})
        except PipelineError as exc:
            result = result.model_copy(update={
                "status": "error", "stage": "error",
                "error": exc.code, "error_message": exc.message})
        except Exception:
            log.exception("Falha inesperada ao processar %s", candidate_id)
            result = result.model_copy(update={
                "status": "error", "stage": "error",
                "error": "INTERNAL", "error_message": MESSAGES["INTERNAL"]})
        self.store.save(result)

    def get(self, candidate_id: str) -> CandidateResult | None:
        return self.store.get(candidate_id)

    def list(self) -> list[CandidateResult]:
        return self.store.list()

    def tracks(self) -> list[dict]:
        return [{"id": id, "name": name} for id, name in self.deps.taxonomy.tracks.items()]
