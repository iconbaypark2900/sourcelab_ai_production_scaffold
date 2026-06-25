"""CLI handlers for the SourceLab library command group."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sourcelab.library.collectors.arxiv import collect_arxiv
from sourcelab.library.collectors.local_docs import collect_local_docs
from sourcelab.library.collectors.nvd import collect_nvd
from sourcelab.library.collectors.pubmed import collect_pubmed
from sourcelab.library.dedupe import dedupe_library
from sourcelab.library.normalize import normalize_library
from sourcelab.library.promote import promote_library
from sourcelab.library.quality import quality_library
from sourcelab.library.stats import library_stats


def _json(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def _project_root(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "project_root", None) or Path.cwd())


def cmd_library_collect_local(args: argparse.Namespace) -> None:
    root = _project_root(args)
    report = collect_local_docs(root, Path(args.path), domain=args.domain)
    normalize_report = normalize_library(root)
    _json(
        {
            "collect": report.model_dump(mode="json"),
            "normalize": normalize_report.model_dump(mode="json"),
        }
    )


def cmd_library_collect_arxiv(args: argparse.Namespace) -> None:
    root = _project_root(args)
    report = collect_arxiv(
        root,
        query=args.query,
        domain=args.domain,
        max_results=args.max_results,
    )
    _json(report.model_dump(mode="json"))


def cmd_library_collect_pubmed(args: argparse.Namespace) -> None:
    root = _project_root(args)
    report = collect_pubmed(
        root,
        query=args.query,
        domain=args.domain,
        max_results=args.max_results,
    )
    _json(report.model_dump(mode="json"))


def cmd_library_collect_nvd(args: argparse.Namespace) -> None:
    root = _project_root(args)
    report = collect_nvd(
        root,
        domain=args.domain,
        keyword=args.keyword,
        modified_since=args.modified_since,
        max_results=args.max_results,
    )
    _json(report.model_dump(mode="json"))


def cmd_library_normalize(args: argparse.Namespace) -> None:
    report = normalize_library(_project_root(args))
    _json(report.model_dump(mode="json"))


def cmd_library_dedupe(args: argparse.Namespace) -> None:
    report = dedupe_library(_project_root(args))
    _json(report.model_dump(mode="json"))


def cmd_library_quality(args: argparse.Namespace) -> None:
    report = quality_library(_project_root(args))
    _json(report.model_dump(mode="json"))


def cmd_library_promote(args: argparse.Namespace) -> None:
    dry_run = args.dry_run and not args.force
    report = promote_library(
        _project_root(args),
        domain=args.domain,
        target_pack=args.target_pack,
        min_quality=args.min_quality,
        dry_run=dry_run,
        force=args.force,
    )
    _json(report.model_dump(mode="json"))


def cmd_library_stats(args: argparse.Namespace) -> None:
    _json(library_stats(_project_root(args)))


def register_library_subparser(sub: argparse._SubParsersAction) -> None:
    """Register `sourcelab library ...` commands on the root parser."""
    library = sub.add_parser("library", help="SourceLab Library Builder commands.")
    library_sub = library.add_subparsers(required=True)

    collect_local = library_sub.add_parser("collect-local", help="Collect local markdown docs.")
    collect_local.add_argument("--path", default=".", help="Project path to scan")
    collect_local.add_argument("--domain", default="user_project_library", help="Domain tag")
    collect_local.set_defaults(func=cmd_library_collect_local)

    collect_arxiv_cmd = library_sub.add_parser("collect-arxiv", help="Collect arXiv metadata.")
    collect_arxiv_cmd.add_argument("--query", required=True, help="arXiv search query")
    collect_arxiv_cmd.add_argument("--domain", default="research", help="Domain tag")
    collect_arxiv_cmd.add_argument("--max-results", type=int, default=5)
    collect_arxiv_cmd.set_defaults(func=cmd_library_collect_arxiv)

    collect_pubmed_cmd = library_sub.add_parser("collect-pubmed", help="Collect PubMed metadata.")
    collect_pubmed_cmd.add_argument("--query", required=True, help="PubMed search query")
    collect_pubmed_cmd.add_argument("--domain", default="research", help="Domain tag")
    collect_pubmed_cmd.add_argument("--max-results", type=int, default=5)
    collect_pubmed_cmd.set_defaults(func=cmd_library_collect_pubmed)

    collect_nvd_cmd = library_sub.add_parser("collect-nvd", help="Collect NVD CVE metadata.")
    collect_nvd_cmd.add_argument("--keyword", default=None, help="Keyword search")
    collect_nvd_cmd.add_argument("--modified-since", default=None, help="Modified since ISO timestamp")
    collect_nvd_cmd.add_argument("--domain", default="security", help="Domain tag")
    collect_nvd_cmd.add_argument("--max-results", type=int, default=5)
    collect_nvd_cmd.set_defaults(func=cmd_library_collect_nvd)

    normalize_cmd = library_sub.add_parser("normalize", help="Normalize bronze raw records to silver cards.")
    normalize_cmd.set_defaults(func=cmd_library_normalize)

    dedupe_cmd = library_sub.add_parser("dedupe", help="Deduplicate silver source cards.")
    dedupe_cmd.set_defaults(func=cmd_library_dedupe)

    quality_cmd = library_sub.add_parser("quality", help="Score silver source cards.")
    quality_cmd.set_defaults(func=cmd_library_quality)

    promote_cmd = library_sub.add_parser("promote", help="Promote silver cards to source pack candidates.")
    promote_cmd.add_argument("--domain", required=True, help="Domain tag filter")
    promote_cmd.add_argument("--target-pack", required=True, help="Target source pack name")
    promote_cmd.add_argument("--min-quality", type=float, default=0.55)
    promote_cmd.add_argument("--dry-run", action="store_true", default=True, help="Proposal only (default)")
    promote_cmd.add_argument("--force", action="store_true", default=False, help="Write into target pack sources/")
    promote_cmd.set_defaults(func=cmd_library_promote)

    stats_cmd = library_sub.add_parser("stats", help="Show library pipeline statistics.")
    stats_cmd.set_defaults(func=cmd_library_stats)
