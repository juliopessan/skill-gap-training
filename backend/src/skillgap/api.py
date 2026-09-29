from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from skillgap.bootstrap import build_service
from skillgap.config import load_settings
from skillgap.exports import to_csv, to_xlsx
from skillgap.service import CandidateService

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_REQUEST = 20
FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(service: CandidateService | None = None) -> FastAPI:
    svc = service or build_service(load_settings())
    app = FastAPI(title="Skill Gap Training")
    app.add_middleware(
        CORSMiddleware, allow_origins=FRONTEND_ORIGINS,
        allow_methods=["*"], allow_headers=["*"])

    @app.post("/candidates", status_code=202)
    async def upload(files: list[UploadFile], background: BackgroundTasks):
        if len(files) > MAX_FILES_PER_REQUEST:
            raise HTTPException(400, f"Máximo de {MAX_FILES_PER_REQUEST} arquivos por envio")
        # Fase 1: validar tudo, sem efeitos colaterais
        payloads = []
        for file in files:
            name = file.filename or "cv.pdf"
            data = await file.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"{name}: arquivo maior que o limite de 10 MB")
            payloads.append((data, name))
        # Fase 2: persistir e agendar o processamento
        accepted = []
        for data, name in payloads:
            result, is_new = svc.submit(data, name)
            if is_new:
                background.add_task(svc.run, result.id, data)
            accepted.append(result.model_dump())
        return accepted

    @app.get("/candidates")
    def list_candidates():
        return [r.model_dump() for r in svc.list()]

    @app.get("/candidates/{candidate_id}")
    def get_candidate(candidate_id: str):
        result = svc.get(candidate_id)
        if result is None:
            raise HTTPException(404, "Candidato não encontrado")
        return result.model_dump()

    @app.get("/candidates/{candidate_id}/export")
    def export(candidate_id: str, format: Literal["csv", "xlsx"] = "csv"):
        result = svc.get(candidate_id)
        if result is None:
            raise HTTPException(404, "Candidato não encontrado")
        if result.status != "done":
            raise HTTPException(409, "O processamento deste CV ainda não terminou com sucesso")
        filename = f"candidato-{candidate_id}.{format}"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        if format == "csv":
            return Response(to_csv(result), media_type="text/csv; charset=utf-8", headers=headers)
        return Response(
            to_xlsx(result), headers=headers,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.get("/taxonomy")
    def taxonomy():
        return {"tracks": svc.tracks()}

    return app
