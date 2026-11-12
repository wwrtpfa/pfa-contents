#!/usr/bin/env python3
"""Synthesize MP3 speech with Breeze and a local Keychain credential."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def get_api_key():
    key = os.getenv("BREEZE_API_KEY")
    if key:
        return key
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "codex-breeze-tts", "-a", "BreezeBlue", "-w"],
            check=True, capture_output=True, text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("BREEZE_API_KEY is unset and the Breeze Keychain entry is unavailable") from exc
    if not result.stdout.strip():
        raise RuntimeError("The Breeze Keychain entry is empty")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--voice", default=os.getenv("BREEZE_VOICE_ID", "voc_tkx6wc2cm8br"))
    parser.add_argument("--model", default="breeze-tts-2")
    args = parser.parse_args()
    if not args.text.strip():
        parser.error("--text must not be empty")
    try:
        key = get_api_key()
        from breeze_blue import BreezeBlue, save
        audio = BreezeBlue(api_key=key).text_to_speech.convert(
            voice_id=args.voice, text=args.text, model_id=args.model, output_format="mp3"
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        save(audio, args.output)
        if not args.output.is_file() or args.output.stat().st_size == 0:
            raise RuntimeError("TTS returned an empty audio file")
    except Exception as exc:
        message = str(exc)
        if "key" in locals():
            message = message.replace(key, "[REDACTED]")
        print(f"Synthesis failed: {message}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output.stat().st_size} bytes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
