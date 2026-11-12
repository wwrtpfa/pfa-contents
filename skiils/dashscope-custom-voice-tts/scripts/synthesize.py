#!/usr/bin/env python3
"""Synthesize an MP3 with a DashScope custom voice asset."""

import argparse
import os
import sys
from pathlib import Path

from voices import VoiceError, resolve

DEFAULT_WS_URL = (
    "wss://llm-qol41lfxij0bums6.cn-beijing.maas.aliyuncs.com/"
    "api-ws/v1/inference"
)
DEFAULT_VOICE_ID = (
    "qwen-audio-3.1-tts-flash-bailian-"
    "a993b5d5395045d1ace4a7a327bff760"
)
DEFAULT_MODEL = "qwen-audio-3.1-tts-flash"


def _preset(name: str, parser: argparse.ArgumentParser) -> dict:
    """Resolve --voice to a registered voice, or return {} for a raw voice ID."""
    try:
        key, spec = resolve(name)
    except VoiceError:
        return {}
    engine = spec.get("engine")
    if engine != "bailian":
        parser.error(
            f"{spec.get('label') or key} 是 {engine} 音色，"
            "请用 scripts/synthesize_local.py（本地克隆），不要走百炼"
        )
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="Text to speak")
    parser.add_argument("--output", type=Path, required=True, help="Output MP3 path")
    parser.add_argument(
        "--voice",
        default=os.getenv("DASHSCOPE_VOICE_ID") or DEFAULT_VOICE_ID,
        help="Registered voice name (e.g. pfa) or a raw custom voice ID",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--ws-url", default=None, help="DashScope WebSocket endpoint")
    args = parser.parse_args()

    if not args.text.strip():
        parser.error("--text must not be empty")

    spec = _preset(args.voice, parser)
    voice_id = str(spec.get("voice_id") or args.voice)
    model = args.model or str(spec.get("model") or DEFAULT_MODEL)
    ws_url = args.ws_url or str(spec.get("ws_url") or DEFAULT_WS_URL)

    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        parser.error("DASHSCOPE_API_KEY is required")

    try:
        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer
    except ImportError:
        parser.error("需要先安装 dashscope>=2.0.1")

    dashscope.api_key = key
    dashscope.base_websocket_api_url = ws_url
    try:
        audio = SpeechSynthesizer(model=model, voice=voice_id).call(args.text)
        if not isinstance(audio, bytes) or not audio:
            raise RuntimeError("TTS returned no audio bytes")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(audio)
    except Exception as exc:
        message = str(exc).replace(key, "[REDACTED]")
        print(f"Synthesis failed: {message}", file=sys.stderr)
        return 1

    print(f"Wrote {len(audio)} bytes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
