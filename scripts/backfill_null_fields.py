#!/usr/bin/env python3
"""Firestore ドキュメントの欠落フィールドに null を書き込む一回限りのマイグレーション。

collector の _article_to_dict が relevance_score / ai_comment を常時書くようになる前に
作成されたドキュメントにはこれらフィールドが存在しない。フィールドが欠落していると
Firestore の == null クエリにヒットせず、classifier / commentator のジョブがスキップする。

このスクリプトは欠落フィールドを null で補完し、== null クエリで拾えるようにする。

実行例（リポジトリルートで）:
    # dry-run（何件が対象か確認）
    uv run --with google-cloud-firestore python \\
        scripts/backfill_null_fields.py --tfvars infra/terraform.stg.tfvars

    # 実際に書き込む
    uv run --with google-cloud-firestore python \\
        scripts/backfill_null_fields.py --tfvars infra/terraform.stg.tfvars --execute
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

_SCRIPT_REL = "scripts/backfill_null_fields.py"
_UV_PREFIX = (
    "uv run --with google-cloud-firestore python " + _SCRIPT_REL
).split()

_FIELDS_TO_BACKFILL = ["relevance_score", "ai_comment"]


def _project_id_from_tfvars(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r'^project_id\s*=\s*"([^"]+)"\s*$', line) or re.match(
            r"^project_id\s*=\s*'([^']+)'\s*$", line
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
    parts: list[str] = list(_UV_PREFIX)
    parts.extend(["-p", project_id])
    if args.collection != "articles":
        parts.extend(["-c", args.collection])
    if with_execute:
        parts.append("--execute")
    return " ".join(shlex.quote(p) for p in parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill missing relevance_score / ai_comment fields with null "
            "so Firestore == null queries can find them (dry-run unless --execute)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples (repo root):\n"
            "  uv run --with google-cloud-firestore python \\\n"
            "    scripts/backfill_null_fields.py --tfvars infra/terraform.stg.tfvars\n"
            "  uv run --with google-cloud-firestore python \\\n"
            "    scripts/backfill_null_fields.py -p YOUR_PROJECT_ID --execute"
        ),
    )
    parser.add_argument("--project-id", "-p", default=None, metavar="ID")
    parser.add_argument("--tfvars", type=Path, default=None, metavar="PATH")
    parser.add_argument(
        "--collection",
        "-c",
        default=os.getenv("FIRESTORE_COLLECTION", "articles"),
        help="Firestore collection name (default: articles).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write updates (default is dry-run).",
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
    print(f"Fields to backfill: {_FIELDS_TO_BACKFILL}", file=sys.stderr)
    if not args.execute:
        print("DRY-RUN mode — pass --execute to write.", file=sys.stderr)

    from google.cloud import firestore

    client = firestore.Client(project=project_id)
    collection = client.collection(args.collection)

    _BATCH_SIZE = 450  # Firestore の 500 書き込み上限より安全に下げる
    batch = client.batch()
    pending = 0
    scanned = 0
    total_updated = 0  # --execute 時の実書き込み件数
    would_update = 0  # dry-run 時の対象件数

    for snapshot in collection.stream():
        scanned += 1
        data = snapshot.to_dict() or {}
        missing = [f for f in _FIELDS_TO_BACKFILL if f not in data]
        if not missing:
            continue

        title = (data.get("title") or "")[:60]
        if not args.execute:
            would_update += 1
            print(f"would update {snapshot.id}\t{missing}\t{title}")
        else:
            batch.update(
                collection.document(snapshot.id),
                {f: None for f in missing},
            )
            pending += 1
            total_updated += 1
            if pending >= _BATCH_SIZE:
                batch.commit()
                batch = client.batch()
                pending = 0
                print(f"  committed {total_updated} updates so far...", file=sys.stderr)

    if args.execute and pending:
        batch.commit()

    display_count = total_updated if args.execute else would_update
    action = "updated" if args.execute else "would update (dry-run)"
    print(
        f"\n{action}: {display_count} / {scanned} documents"
        f" in project={project_id!r} collection={args.collection!r}",
        file=sys.stderr,
    )
    if not args.execute and would_update > 0:
        print("", file=sys.stderr)
        print("--- copy-paste to execute ---", file=sys.stderr)
        print(build_copy_paste_command(project_id, args, with_execute=True), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
