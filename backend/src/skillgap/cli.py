import argparse
from pathlib import Path

from skillgap.bootstrap import build_service
from skillgap.config import load_settings
from skillgap.service import CandidateService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skillgap")
    sub = parser.add_subparsers(dest="command", required=True)
    process = sub.add_parser("process", help="Processa todos os PDFs de uma pasta")
    process.add_argument("folder", help="Pasta com os mini CVs (.pdf)")
    process.add_argument("--out", default="out", help="Pasta de saída dos JSONs")
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


def main(argv: list[str] | None = None, service: CandidateService | None = None) -> int:
    args = _parser().parse_args(argv)
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
