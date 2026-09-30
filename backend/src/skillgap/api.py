from typing import Literal

from pydantic import BaseModel

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from skillgap.bootstrap import build_service
from skillgap.config import load_settings
from skillgap.exports import to_csv, to_xlsx
from skillgap.recommender import Course
from skillgap.service import CandidateService
from skillgap.settings_api import GuardMiddleware, build_settings_router, settings_validation_handler

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_REQUEST = 20
FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
CATALOG_DEFAULT_LIMIT = 100
CATALOG_MAX_LIMIT = 200


class CourseOut(BaseModel):
    id: str
    platform: str
    title: str
    focus: str
    level: int
    provider: str
    kind: str
    hours: int | None
    link: str
    source: str
    verified: bool
    skills: list[str]


def course_out(c: Course) -> CourseOut:
    return CourseOut(id=c.id, platform=c.platform, title=c.title, focus=c.focus, level=c.level,
                     provider=c.provider, kind=c.kind, hours=c.hours, link=c.link,
                     source=c.source, verified=c.verified, skills=list(c.skills))


def create_app(service: CandidateService | None = None, client_factory=None,
               allowed_hosts: list[str] | None = None) -> FastAPI:
    svc = service or build_service(load_settings())
    app = FastAPI(title="Skill Gap Training", redirect_slashes=False)
    app.add_middleware(
        CORSMiddleware, allow_origins=FRONTEND_ORIGINS,
        allow_methods=["*"], allow_headers=["*"])
    # Adicionado por último = mais externo: Host/Origin são checados antes de tudo.
    app.add_middleware(GuardMiddleware, allowed_origins=FRONTEND_ORIGINS,
                       allowed_hosts=allowed_hosts)
    app.add_exception_handler(RequestValidationError, settings_validation_handler)
    app.include_router(build_settings_router(svc.keystore, client_factory))

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

    catalog = getattr(svc, "catalog", None)
    if catalog is not None:
        _add_catalog_routes(app, catalog)

    return app


def _add_catalog_routes(app: FastAPI, catalog) -> None:
    def invalid(message: str) -> HTTPException:
        return HTTPException(422, message)

    @app.get("/catalog")
    def list_catalog(platform: str | None = None, level: str | None = None,
                     kind: str | None = None, skill: str | None = None,
                     q: str | None = None, limit: str | None = None):
        level_value = None
        if level not in (None, ""):
            if level not in ("1", "2", "3"):
                raise invalid("Nível inválido: use 1, 2 ou 3.")
            level_value = int(level)
        limit_value = CATALOG_DEFAULT_LIMIT
        if limit not in (None, ""):
            try:
                limit_value = int(limit)
            except ValueError:
                raise invalid(f"Limite inválido: use um inteiro entre 1 e {CATALOG_MAX_LIMIT}.") from None
            if not 1 <= limit_value <= CATALOG_MAX_LIMIT:
                raise invalid(f"Limite inválido: use um inteiro entre 1 e {CATALOG_MAX_LIMIT}.")
        matching = catalog.list_courses(platform=platform, level=level_value, kind=kind,
                                        skill=skill, q=q)
        return {"total": len(matching),
                "items": [course_out(c).model_dump() for c in matching[:limit_value]]}

    # /catalog/stats precisa vir antes de /catalog/{course_id}
    @app.get("/catalog/stats")
    def catalog_stats():
        return catalog.stats()

    @app.get("/catalog/{course_id}")
    def get_course(course_id: str):
        course = catalog.get(course_id)
        if course is None:
            raise HTTPException(404, "Curso não encontrado")
        return course_out(course).model_dump()
