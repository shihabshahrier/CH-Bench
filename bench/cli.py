"""`bench` command-line entrypoint.

    bench run --system mock --suite contextheavy
    bench run --system ch   --suite contextheavy --k 10 --out results/
    bench list

Judge is auto-enabled when JUDGE_API_KEY is set (see core/judge.py); use
--no-judge to force retrieval-only scoring.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import adapters, suites
from .core.judge import Judge
from .core.runner import run
from .report import to_markdown, write_scorecard


def _load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE lines from ./.env into the environment (no override of
    already-set vars). Keeps secrets out of the shell history and out of git."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def _cmd_list(_: argparse.Namespace) -> int:
    print("systems:", ", ".join(adapters.names()))
    print("suites: ", ", ".join(suites.names()))
    print("\njudge: set JUDGE_BASE_URL / JUDGE_MODEL / JUDGE_API_KEY to enable correctness scoring")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    adapter = adapters.build(args.system)
    suite = suites.build(args.suite)
    judge = Judge()
    if args.no_judge:
        judge = Judge(base_url="", model="", api_key="")  # force-disabled

    card = run(
        adapter,
        suite,
        k=args.k,
        limit=args.limit,
        judge=judge,
        progress=not args.quiet,
        config={"system": args.system, "suite": args.suite, "k": args.k},
    )

    if not args.quiet:
        print("\n" + to_markdown(card), file=sys.stdout)

    if args.out:
        json_path, md_path = write_scorecard(card, args.out)
        print(f"\nwrote {json_path}\nwrote {md_path}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bench", description="Context-Heavy memory/RAG benchmark harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="ingest a suite into a system and score it")
    r.add_argument("--system", required=True, help=f"one of: {', '.join(adapters.names())}")
    r.add_argument("--suite", required=True, help=f"one of: {', '.join(suites.names())}")
    r.add_argument("--k", type=int, default=10, help="top-k for retrieval + metrics (default 10)")
    r.add_argument("--limit", type=int, default=None, help="cap number of questions (smoke runs)")
    r.add_argument("--no-judge", action="store_true", help="disable LLM-judge correctness scoring")
    r.add_argument("--out", default="results", help="output dir for scorecards (default results/; '' to skip)")
    r.add_argument("--quiet", action="store_true", help="suppress progress + stdout scorecard")
    r.set_defaults(func=_cmd_run)

    lst = sub.add_parser("list", help="list available systems and suites")
    lst.set_defaults(func=_cmd_list)

    return p


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "out", None) == "":
        args.out = None
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
