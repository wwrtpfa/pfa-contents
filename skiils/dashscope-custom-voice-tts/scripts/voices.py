#!/usr/bin/env python3
"""Resolve a spoken voice name to its engine parameters."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "voices" / "manifest.json"


class VoiceError(RuntimeError):
    """Raised when a voice name cannot be resolved."""


def _norm(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "")


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def load_voices() -> dict[str, dict]:
    return dict(load_manifest().get("voices") or {})


def resolve(name: str) -> tuple[str, dict]:
    """Return (voice_id, spec) for an exact key, an alias, or a substring match."""
    wanted = _norm(name)
    voices = load_voices()
    if not wanted:
        raise VoiceError("Voice name is empty")
    for key, spec in voices.items():
        if _norm(key) == wanted:
            return key, spec
    for key, spec in voices.items():
        if any(_norm(alias) == wanted for alias in spec.get("aliases") or []):
            return key, spec
    for key, spec in voices.items():
        names = [key, *(spec.get("aliases") or [])]
        if any(_norm(item) and _norm(item) in wanted for item in names):
            return key, spec
    known = ", ".join(f"{key}({spec.get('label', '')})" for key, spec in voices.items())
    raise VoiceError(f"Unknown voice {name!r}; known voices: {known}")


def ref_audio(spec: dict) -> Path:
    raw = str(spec.get("ref_audio") or "").strip()
    if not raw:
        raise VoiceError(f"Voice {spec.get('label', '')} has no reference audio")
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_reference(spec: dict) -> str | None:
    """Return None when the reference clip matches the pinned fingerprint."""
    expected = str(spec.get("ref_sha256") or "").strip()
    if spec.get("engine") != "local" or not expected:
        return None
    path = ref_audio(spec)
    if not path.is_file():
        return f"参考音频不存在：{path}"
    actual = _sha256(path)
    if actual != expected:
        return (
            f"参考音频被换过：期望 {expected[:12]}…，实际 {actual[:12]}…（{path}）。"
            "若是有意替换，请先同步改 manifest.json 的 ref_sha256 / locked，别只覆盖 wav 文件"
        )
    return None


def verify_all() -> list[str]:
    """Collect fingerprint problems for every registered local voice."""
    problems = []
    for key, spec in load_voices().items():
        problem = check_reference(spec)
        if problem:
            problems.append(f"{key}: {problem}")
    return problems


def describe(key: str, spec: dict) -> str:
    engine = spec.get("engine", "?")
    if engine == "local":
        detail = f"ref_audio={ref_audio(spec)} | model={spec.get('model', '')}"
    elif engine == "bailian":
        detail = f"voice_id={spec.get('voice_id', '')} | model={spec.get('model', '')}"
    else:
        detail = str(spec)
    return f"{key}\t{spec.get('label', '')}\t{engine}\t{detail}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", help="Voice name, alias, or a fragment such as 纳西妲的声音")
    parser.add_argument("--list", action="store_true", help="List every registered voice")
    parser.add_argument("--json", action="store_true", help="Print the resolved spec as JSON")
    parser.add_argument("--default", action="store_true", help="Print the pinned default voice")
    parser.add_argument("--verify", action="store_true", help="Check every pinned reference fingerprint")
    args = parser.parse_args()

    if args.verify:
        problems = verify_all()
        locked = set(load_manifest().get("locked") or [])
        for key, spec in load_voices().items():
            if spec.get("engine") != "local" or not spec.get("ref_sha256"):
                continue
            mark = "LOCKED" if key in locked or spec.get("locked") else "对照"
            state = "OK" if not any(p.startswith(f"{key}:") for p in problems) else "已变更"
            print(f"{key:16s} {mark:7s} {state:7s} {ref_audio(spec).name:22s} {str(spec['ref_sha256'])[:12]}…")
        for problem in problems:
            print(problem, file=sys.stderr)
        print("全部指纹一致" if not problems else f"发现 {len(problems)} 处不一致", file=sys.stderr)
        return 1 if problems else 0

    if args.default:
        key = str(load_manifest().get("default_voice") or "pfa")
        print(describe(key, load_voices()[key]))
        return 0

    if args.list or not args.name:
        for key, spec in load_voices().items():
            print(describe(key, spec))
        return 0
    try:
        key, spec = resolve(args.name)
    except VoiceError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"id": key, **spec}, ensure_ascii=False, indent=2))
    else:
        print(describe(key, spec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
