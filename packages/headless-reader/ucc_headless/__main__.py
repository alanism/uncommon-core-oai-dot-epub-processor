"""File-only command line interface. Outputs refuse to overwrite existing files."""
import argparse
import json
import sys
from pathlib import Path
from .epub import ingest_epub, ReaderError
from .workflow import analysis_jobs, import_result, derived_job, image_job, image_revision_job, coverage, markdown, ContractError


def read(path):
    p = Path(path)
    if p.stat().st_size > 128 * 1024 * 1024:
        raise ContractError("JSON input exceeds 128 MiB")
    return json.loads(p.read_text(encoding="utf-8"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as out:
        out.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline EPUB ledger and trusted-host jobs; no API keys")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("ingest"); p.add_argument("epub"); p.add_argument("output"); p.add_argument("--max-chars", type=int, default=6000)
    p = sub.add_parser("jobs"); p.add_argument("ledger"); p.add_argument("output"); p.add_argument("--lens", default="philosopher"); p.add_argument("--focus", default="Expert"); p.add_argument("--depth", default="MBA"); p.add_argument("--job-chars", type=int, default=6000); p.add_argument("--model-preference", default="Luna")
    p = sub.add_parser("import"); p.add_argument("job"); p.add_argument("response"); p.add_argument("output")
    for command in ("outline", "synthesis"):
        p = sub.add_parser(command); p.add_argument("records"); p.add_argument("output"); p.add_argument("--ledgers", nargs="+", required=True); p.add_argument("--source-ids", nargs="+"); p.add_argument("--model-preference", default="Luna")
        if command == "synthesis": p.add_argument("--question", required=True)
    p = sub.add_parser("image"); p.add_argument("outline_record"); p.add_argument("output")
    p = sub.add_parser("image-revision"); p.add_argument("image_record"); p.add_argument("edit_prompt"); p.add_argument("output")
    for command in ("coverage", "markdown"):
        p = sub.add_parser(command); p.add_argument("ledger"); p.add_argument("records"); p.add_argument("output")
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest": result = ingest_epub(args.epub, max_chars=args.max_chars)
        elif args.command == "jobs": result = analysis_jobs(read(args.ledger), {"lens": args.lens, "focus": args.focus, "depth": args.depth}, max_input_chars=args.job_chars, model_preference=args.model_preference)
        elif args.command == "import": result = import_result(read(args.job), read(args.response))
        elif args.command in {"outline", "synthesis"}: result = derived_job(args.command, [read(p) for p in args.ledgers], read(args.records), question=getattr(args, "question", None), source_ids=args.source_ids, model_preference=args.model_preference)
        elif args.command == "image": result = image_job(read(args.outline_record))
        elif args.command == "image-revision": result = image_revision_job(read(args.image_record), Path(args.edit_prompt).read_text(encoding="utf-8"))
        elif args.command == "coverage": result = coverage(read(args.ledger), read(args.records))
        else: result = markdown(read(args.ledger), read(args.records))
        write(args.output, result)
    except (ReaderError, ContractError, OSError, ValueError, KeyError, TypeError) as error:
        print("error: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
