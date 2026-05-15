#!/usr/bin/env python3
"""Remove article documents in Firestore whose feed_url matches a removed RSS feed.

Uses Application Default Credentials (e.g. ``gcloud auth application-default login``).

Project ID: ``-p``, ``GOOGLE_CLOUD_PROJECT``, ``--tfvars`` (例: ``infra/terraform.stg.tfvars``),
または gcloud のアクティブプロジェクト。

Dry-run の最後に、そのままコピペできる ``uv run ... --execute`` 1行を表示する。

コピペ例（リポジトリルートで実行。行末の ``\\`` はシェル用の継続）::

    uv run --with google-cloud-firestore python \\
        scripts/delete_articles_by_feed_url.py \\
        --tfvars infra/terraform.stg.tfvars --feed-url-contains wor.jp

    uv run --with google-cloud-firestore python \\
        scripts/delete_articles_by_feed_url.py \\
        -p my-project-id --feed-url-exact 'https://example.com/rss.xml' --execute

"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPT_REL = "scripts/delete_articles_by_feed_url.py"
_UV_PREFIX = (
    "uv run --with google-cloud-firestore python "
    + _SCRIPT_REL
).split()


def _project_id_from_tfvars(path: Path) -> str | None:
    """Parse ``project_id = \"...\"`` from a terraform.tfvars-style file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r'^project_id\s*=\s*"([^"]+)"\s*$', line) or re.match(
            r"^project_id\s*=\s*'([^']+)'\s*$",
            line,
        )
        if m:
            return m.group(1).strip()
    return None


def _project_id_from_gcloud() -> str | None:
    try:
        completed = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = (completed.stdout or "").strip()
    return value if value and value != "(unset)" else None


def resolve_gcp_project_id(
    explicit: str | None,
    tfvars_path: Path | None,
) -> tuple[str | None, str]:
    """Return (project_id_or_none, human-readable source)."""
    if explicit and explicit.strip():
        return explicit.strip(), "--project-id / -p"

    for env_name in ("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT_ID"):
        raw = os.getenv(env_name)
        if raw and raw.strip():
            return raw.strip(), env_name

    if tfvars_path is not None:
        pid = _project_id_from_tfvars(tfvars_path)
        if pid:
            return pid, f"--tfvars ({tfvars_path})"

    gc = _project_id_from_gcloud()
    if gc:
        return gc, "gcloud config get-value project"

    return None, ""


def build_copy_paste_command(
    project_id: str,
    args: argparse.Namespace,
    *,
    with_execute: bool,
) -> str:
    """Single shell line (quoted) to reproduce this run from repo root."""
    parts: list[str] = list(_UV_PREFIX)
    parts.extend(["-p", project_id])
    if args.collection != "articles":
        parts.extend(["-c", args.collection])
    if args.feed_url_exact is not None:
        parts.extend(["--feed-url-exact", args.feed_url_exact])
    else:
        parts.extend(["--feed-url-contains", args.feed_url_contains])
    if args.limit:
        parts.extend(["--limit", str(args.limit)])
    if with_execute:
        parts.append("--execute")
    return " ".join(shlex.quote(p) for p in parts)


def _field_filter(field: str, op: str, value: Any) -> Any:
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return FieldFilter(field, op, value)
    except ImportError:
        return (field, op, value)


def _iter_matching_docs(
    collection: Any,
    *,
    feed_url_exact: str | None,
    feed_url_contains: str | None,
) -> Any:
    if feed_url_exact is not None:
        q = collection.where(filter=_field_filter("feed_url", "==", feed_url_exact))
        return q.stream()
    if feed_url_contains is not None:
        needle = feed_url_contains

        def gen() -> Any:
            for snapshot in collection.stream():
                data = snapshot.to_dict() or {}
                url = data.get("feed_url") or ""
                if needle in url:
                    yield snapshot

        return gen()
    raise AssertionError("exact or contains required")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete Firestore article docs by feed_url (dry-run unless --execute).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples (repo root — copy all lines including \\\\ continuations):\n"
            "  uv run --with google-cloud-firestore python \\\n"
            "    scripts/delete_articles_by_feed_url.py \\\n"
            "    --tfvars infra/terraform.stg.tfvars --feed-url-contains wor.jp\n"
            "  uv run --with google-cloud-firestore python \\\n"
            "    scripts/delete_articles_by_feed_url.py \\\n"
            "    -p YOUR_PROJECT_ID --feed-url-exact https://example.com/rss.xml --execute"
        ),
    )
    parser.add_argument(
        "--project-id",
        "-p",
        default=None,
        metavar="ID",
        help="GCP project id (omit if env / --tfvars / gcloud is set).",
    )
    parser.add_argument(
        "--tfvars",
        type=Path,
        default=None,
        metavar="PATH",
        help="e.g. infra/terraform.stg.tfvars — read project_id for this run.",
    )
    parser.add_argument(
        "--collection",
        "-c",
        default=os.getenv("FIRESTORE_COLLECTION", "articles"),
        help="Firestore collection name (default: articles, or FIRESTORE_COLLECTION).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--feed-url-exact",
        metavar="URL",
        help="Delete docs where feed_url equals this string exactly.",
    )
    group.add_argument(
        "--feed-url-contains",
        metavar="SUBSTRING",
        help="Delete docs where feed_url contains this substring.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform deletes (default is dry-run only).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max documents to process (0 = no limit).",
    )
    args = parser.parse_args()

    project_id, source = resolve_gcp_project_id(args.project_id, args.tfvars)
    if not project_id:
        print(
            "error: could not determine GCP project id.\n"
            "  Use: -p PROJECT_ID  OR  export GOOGLE_CLOUD_PROJECT  OR  "
            "--tfvars infra/terraform.stg.tfvars  OR  gcloud config set project ...",
            file=sys.stderr,
        )
        return 1

    print(f"Using GCP project: {project_id} ({source})", file=sys.stderr)

    from google.cloud import firestore

    client = firestore.Client(project=project_id)
    collection = client.collection(args.collection)

    stream = _iter_matching_docs(
        collection,
        feed_url_exact=args.feed_url_exact,
        feed_url_contains=args.feed_url_contains,
    )

    batch_size = 450  # under Firestore 500 write limit
    batch = client.batch()
    pending = 0
    total = 0

    for snapshot in stream:
        total += 1
        doc_id = snapshot.id
        data = snapshot.to_dict() or {}
        title = (data.get("title") or "")[:80]
        if not args.execute:
            print(f"would delete {doc_id}\t{title}")
        else:
            batch.delete(collection.document(doc_id))
            pending += 1
            if pending >= batch_size:
                batch.commit()
                batch = client.batch()
                pending = 0
        if args.limit and total >= args.limit:
            break

    if args.execute and pending:
        batch.commit()

    action = "deleted" if args.execute else "matched (dry-run)"
    print(
        f"{action}: {total} document(s) in project={project_id!r} collection={args.collection!r}",
        file=sys.stderr,
    )
    if not args.execute:
        print("", file=sys.stderr)
        print("--- copy-paste (repo root): same flags + resolved project ---", file=sys.stderr)
        print("dry-run:", file=sys.stderr)
        print(build_copy_paste_command(project_id, args, with_execute=False), file=sys.stderr)
        if total > 0:
            print("delete:", file=sys.stderr)
            print(build_copy_paste_command(project_id, args, with_execute=True), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
