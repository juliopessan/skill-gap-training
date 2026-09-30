import argparse
from pathlib import Path

import json

from skillgap.api import course_out
from skillgap.bootstrap import build_service
from skillgap.catalog_store import CatalogStore, validate_courses
from skillgap.config import Settings, load_settings
from skillgap.recommender import load_catalog
from skillgap.service import CandidateService
from skillgap.taxonomy import load_taxonomy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skillgap")
    sub = parser.add_subparsers(dest="command", required=True)
    process = sub.add_parser("process", help="Processa todos os PDFs de uma pasta")
    process.add_argument("folder", help="Pasta com os mini CVs (.pdf)")
    process.add_argument("--out", default="out", help="Pasta de saída dos JSONs")
    catalog = sub.add_parser("catalog", help="Gerencia o catálogo de treinamentos (SQLite)")
    csub = catalog.add_subparsers(dest="catalog_command", required=True)
    imp = csub.add_parser("import", help="Importa um CSV para o catálogo (upsert por id)")
    imp.add_argument("csv", help="Arquivo CSV do catálogo")
    imp.add_argument("--replace", action="store_true", help="Substitui todo o catálogo")
    lst = csub.add_parser("list", help="Lista cursos")
    lst.add_argument("--platform")
    lst.add_argument("--level", type=int, choices=[1, 2, 3])
    lst.add_argument("--kind")
    lst.add_argument("--skill")
    lst.add_argument("--q", help="Busca em título, foco e provedor")
    lst.add_argument("--limit", type=int)
    lst.add_argument("--json", action="store_true", help="Saída em JSON")
    csub.add_parser("stats", help="Estatísticas do catálogo")
    exp = csub.add_parser("export", help="Exporta o catálogo para CSV")
    exp.add_argument("csv", help="Arquivo CSV de saída")
    return parser


def assign_output_names(paths: list[Path]) -> dict[Path, str]:
    """
    Assign output JSON names for a list of PDF paths, avoiding collisions.

    Returns a dict mapping each Path to its output JSON filename (e.g., "file.json", "file-2.json").
    Ensures:
    - All output names are unique (case-insensitive)
    - Natural names (stem.json) are preserved where possible
    - Bumped names (stem-N.json) never equal another input's natural name
    """
    # Precompute natural names for all inputs (lowercase for collision detection)
    natural_names_lower = {p.stem.lower() + ".json": p for p in paths}

    used_names = set()  # Lowercase output names already assigned
    result = {}

    for path in paths:
        stem = path.stem
        stem_lower = stem.lower()

        # Try to use natural name first
        candidate = f"{stem}.json"
        candidate_lower = candidate.lower()

        if candidate_lower not in used_names:
            # Natural name is free
            result[path] = candidate
            used_names.add(candidate_lower)
        else:
            # Need to bump to stem-2.json, stem-3.json, etc.
            counter = 2
            while True:
                bumped = f"{stem}-{counter}.json"
                bumped_lower = bumped.lower()

                # Check if this bumped name collides with another input's natural name
                if bumped_lower not in natural_names_lower:
                    # Safe to use (doesn't equal any input's natural name)
                    if bumped_lower not in used_names:
                        result[path] = bumped
                        used_names.add(bumped_lower)
                        break

                counter += 1

    return result


def _table(courses) -> str:
    header = ["id", "plataforma", "nível", "tipo", "verificado", "horas", "título"]
    rows = [[c.id, c.platform, str(c.level), c.kind, "sim" if c.verified else "não",
             "—" if c.hours is None else str(c.hours), c.title] for c in courses]
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header) - 1)]
    lines = []
    for r in [header, *rows]:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(len(widths))) + "  " + r[-1])
    return "\n".join(lines)


def _catalog_main(args, settings: Settings) -> int:
    try:
        taxonomy = load_taxonomy(settings.taxonomy_path)
        store = CatalogStore(settings.db_path)
    except (OSError, ValueError) as exc:
        print(f"ERRO  {exc}")
        return 1
    try:
        cmd = args.catalog_command
        if cmd == "import":
            path = Path(args.csv)
            if not path.is_file():
                print(f"ERRO  Arquivo não encontrado: {path}")
                return 1
            courses = load_catalog(path)
            validate_courses(courses, taxonomy)
            if args.replace:
                removed = store.count()
                store.replace_all(courses)
                print(f"Catálogo substituído: {len(courses)} curso(s) importado(s), "
                      f"{removed} anterior(es) removido(s).")
            else:
                existing = {c.id for c in store.all_courses()}
                updated = sum(1 for c in courses if c.id in existing)
                store.upsert(courses)
                print(f"Importação concluída: {len(courses) - updated} inserido(s), "
                      f"{updated} atualizado(s).")
            return 0
        # Demais comandos leem o catálogo; semeia a partir do CSV se estiver vazio.
        store.seed_from_csv_if_empty(settings.catalog_path, taxonomy)
        if cmd == "list":
            courses = store.list_courses(platform=args.platform, level=args.level, kind=args.kind,
                                         skill=args.skill, q=args.q, limit=args.limit)
            if args.json:
                print(json.dumps([course_out(c).model_dump() for c in courses],
                                 ensure_ascii=False, indent=2))
            elif not courses:
                print("Nenhum curso encontrado.")
            else:
                print(_table(courses))
        elif cmd == "stats":
            s = store.stats()
            print(f"Total de cursos: {s['total']}")
            for label, key in (("Por plataforma", "by_platform"), ("Por nível", "by_level"),
                               ("Por tipo", "by_kind")):
                print(f"{label}: " + ", ".join(f"{k}={v}" for k, v in s[key].items()))
            print(f"Verificados: {s['verified']}  Não verificados: {s['unverified']}")
            print(f"Horas desconhecidas: {s['hours_unknown']}")
        elif cmd == "export":
            store.export_csv(args.csv)
            print(f"Catálogo exportado para {args.csv} ({store.count()} curso(s)).")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERRO  {exc}")
        return 1
    finally:
        store.close()


def main(argv: list[str] | None = None, service: CandidateService | None = None,
         settings: Settings | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "catalog":
        return _catalog_main(args, settings or load_settings())
    folder_path = Path(args.folder)

    # Check if path exists and is a directory
    if not folder_path.exists():
        print(f"Pasta não encontrada: {args.folder}")
        return 1

    if not folder_path.is_dir():
        print(f"O caminho não é uma pasta: {args.folder}")
        return 1

    # Collect PDFs (case-insensitive, only files)
    pdfs = sorted([p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])
    if not pdfs:
        print(f"Nenhum PDF encontrado em {args.folder}")
        return 1

    # Precompute output names for all PDFs to avoid collisions
    output_names = assign_output_names(pdfs)

    svc = service or build_service(load_settings())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    failed = 0

    for pdf in pdfs:
        # Read file with error handling
        try:
            data = pdf.read_bytes()
        except OSError as e:
            failed += 1
            print(f"ERRO  {pdf.name}: não foi possível ler o arquivo ({e.strerror})")
            continue

        result, is_new = svc.submit(data, pdf.name)
        if is_new:
            svc.run(result.id, data)
            result = svc.get(result.id)

        # Treat 'processing' status as failure (cache hit, still being processed elsewhere)
        if result.status == "processing":
            failed += 1
            print(f"ERRO  {pdf.name}: processamento ainda em andamento em outro processo; tente novamente depois")
            continue

        # Write JSON and log (only assign name after ensuring we'll write)
        output_name = output_names[pdf]
        (out / output_name).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        if result.status == "error":
            failed += 1
            print(f"ERRO  {pdf.name}: {result.error_message}")
        else:
            print(f"OK    {pdf.name}: {len(result.skills)} skills, "
                  f"{len(result.gaps)} gaps, {len(result.recommendations)} treinamentos")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
