#!/usr/bin/env python3
"""Create an immutable Douyin publishing package for a finished video."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path


DEFAULT_ROOT = Path("/Users/pengfanao/Desktop/剪辑素材-视频/自媒体")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_slug(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "视频")
    value = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-_")
    return value[:80] or "视频"


def write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"file not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_caption(title: str, body: str, tags: list[str]) -> str:
    lines = [f"# {title.strip() or '未命名视频'}", "", body.strip(), ""]
    if tags:
        lines.extend(["## 标签", "", " ".join(tag if tag.startswith("#") else f"#{tag}" for tag in tags), ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--cover", required=True, type=Path)
    parser.add_argument("--title", default="未命名视频")
    parser.add_argument("--caption")
    parser.add_argument("--caption-file", type=Path)
    parser.add_argument("--tags", nargs="*", default=[])
    parser.add_argument("--slug")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--extra", action="append", type=Path, default=[], help="Auxiliary file to copy into extras/")
    parser.add_argument("--source", action="append", type=Path, default=[], help="Alias for --extra")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.caption and args.caption_file:
        raise SystemExit("use only one of --caption and --caption-file")
    body = args.caption
    if args.caption_file:
        body = args.caption_file.read_text(encoding="utf-8")
    body = (body or "").strip()
    if not body:
        raise SystemExit("caption is required: use --caption or --caption-file")

    root = args.root.expanduser().resolve()
    timestamp = datetime.now().astimezone()
    slug = safe_slug(args.slug or args.title)
    base = root / f"{timestamp:%Y%m%d-%H%M%S}-{slug}"
    archive = base
    suffix = 2
    while archive.exists():
        archive = root / f"{base.name}-{suffix}"
        suffix += 1

    video_suffix = args.video.suffix.lower() or ".mp4"
    cover_suffix = args.cover.suffix.lower() or ".png"
    planned = {
        "archive_dir": str(archive),
        "video": str(archive / f"video{video_suffix}"),
        "cover": str(archive / f"cover{cover_suffix}"),
        "caption": str(archive / "caption.md"),
    }
    if args.dry_run:
        print(json.dumps(planned, ensure_ascii=False, indent=2))
        return 0

    archive.mkdir(parents=True)
    video_target = archive / f"video{video_suffix}"
    cover_target = archive / f"cover{cover_suffix}"
    copy_file(args.video.expanduser().resolve(), video_target)
    copy_file(args.cover.expanduser().resolve(), cover_target)
    caption_path = archive / "caption.md"
    caption_path.write_text(build_caption(args.title, body, args.tags), encoding="utf-8")

    extras = args.extra + args.source
    copied_extras: list[str] = []
    for extra in extras:
        extra_source = extra.expanduser().resolve()
        extra_target = archive / "extras" / extra_source.name
        copy_file(extra_source, extra_target)
        copied_extras.append(str(extra_target.relative_to(archive)))

    metadata = {
        "schema_version": 1,
        "created_at": timestamp.isoformat(),
        "title": args.title,
        "caption": body,
        "tags": args.tags,
        "video": video_target.name,
        "cover": cover_target.name,
        "extras": copied_extras,
        "upload": {"status": "pending"},
    }
    write_json(archive / "metadata.json", metadata)
    write_json(
        archive / "upload-state.json",
        {
            "status": "pending",
            "mode": None,
            "page_url": None,
            "作品链接": None,
            "started_at": None,
            "finished_at": None,
            "error": None,
        },
    )

    file_entries = []
    for path in sorted(p for p in archive.rglob("*") if p.is_file()):
        if path.name in {"archive-manifest.json", "upload-state.json"}:
            continue
        file_entries.append(
            {
                "path": str(path.relative_to(archive)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    write_json(
        archive / "archive-manifest.json",
        {
            "schema_version": 1,
            "created_at": timestamp.isoformat(),
            "archive_dir": str(archive),
            "files": file_entries,
            "mutable_files": ["upload-state.json"],
            "upload_state": "upload-state.json",
        },
    )
    print(archive)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"archive failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
