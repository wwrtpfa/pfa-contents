#!/usr/bin/env python3
"""Register a new cloning voice: cut a clean clip and record it in the manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES_DIR = ROOT / "voices"
MANIFEST = VOICES_DIR / "manifest.json"
TARGET_RATE = 24000


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise SystemExit("需要 ffmpeg：brew install ffmpeg")
    return found


def cut(source: Path, target: Path, start: float | None, duration: float | None) -> None:
    cmd = [_ffmpeg(), "-y", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.2f}"]
    cmd += ["-i", str(source)]
    if duration:
        cmd += ["-t", f"{duration:.2f}"]
    cmd += [
        "-af", "loudnorm=I=-18:TP=-2:LRA=11",
        "-ac", "1", "-ar", str(TARGET_RATE), "-c:a", "pcm_s16le",
        str(target),
    ]
    subprocess.run(cmd, check=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(target)],
        check=True, capture_output=True, text=True,
    )
    seconds = float(probe.stdout.strip() or 0)
    if not 4.0 <= seconds <= 20.0:
        print(f"警告：片长 {seconds:.2f}s，克隆推荐 6–15s 干净人声")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Voice key, e.g. furina")
    parser.add_argument("--label", required=True, help="显示名，如 芙宁娜")
    parser.add_argument("--from", dest="source", type=Path, required=True, help="原始音频/视频")
    parser.add_argument("--start", type=float, help="从第几秒开始")
    parser.add_argument("--duration", type=float, help="取多长（越大越慢，6–15s 最稳）")
    parser.add_argument("--text", default="", help="这段音频的逐字稿，必须逐字一致")
    parser.add_argument("--aliases", default="", help="逗号分隔的别名")
    parser.add_argument("--authorization", default="", help="授权说明")
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error(f"源文件不存在：{args.source}")
    if not args.name.replace("_", "").replace("-", "").isalnum():
        parser.error("--name 只用字母、数字、下划线或连字符")

    target = VOICES_DIR / f"{args.name}.wav"
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    cut(args.source, target, args.start, args.duration)

    data = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"version": 1, "voices": {}}
    voices = data.setdefault("voices", {})
    entry = voices.get(args.name) or {}
    entry.update(
        {
            "label": args.label,
            "kind": "第三方角色" if not args.authorization else "已登记",
            "engine": "local",
            "model": "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit",
            "lang": "Chinese",
            "ref_audio": f"voices/{args.name}.wav",
            "ref_text": args.text,
            "aliases": [item.strip() for item in args.aliases.split(",") if item.strip()],
            "source": f"{args.source}（start={args.start or 0}s, duration={args.duration or '全段'}）",
            "authorization": args.authorization or "未登记：公开使用前需确认授权并标注 AI 合成。",
        }
    )
    voices[args.name] = entry
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"已登记 {args.name} → {target}")
    if not args.text.strip():
        print("提示：ref_text 为空时靠说话人编码器提音色，音色更像但节奏更飘；补上逐字稿更稳。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
