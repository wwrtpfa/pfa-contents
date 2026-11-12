#!/usr/bin/env python3
"""Clone an authorized voice locally with MLX Qwen3-TTS."""

import argparse
import os
import sys
from pathlib import Path

from voices import VoiceError, check_reference, ref_audio, resolve

DEFAULT_MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit"
DEFAULT_PYTHON = "~/tools/qwen-tts/.venv/bin/python"


def _ensure_mlx_env() -> None:
    """Re-exec under the MLX interpreter when the current one lacks mlx-audio."""
    try:
        import mlx_audio.tts.utils  # noqa: F401
        return
    except ImportError:
        pass
    candidate = Path(os.getenv("QWEN_TTS_PYTHON") or DEFAULT_PYTHON).expanduser()
    if candidate.is_file() and Path(sys.executable).resolve() != candidate.resolve():
        os.execv(str(candidate), [str(candidate), *sys.argv])
    raise SystemExit(
        "缺 mlx-audio：安装到独立解释器后，用 QWEN_TTS_PYTHON 指向它，"
        f"或直接 {DEFAULT_PYTHON} scripts/synthesize_local.py ..."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice", help="Registered voice name, e.g. nahida / 纳西妲")
    parser.add_argument("--reference-audio", type=Path, help="Ad-hoc reference clip (6-15 s, clean speech)")
    parser.add_argument("--reference-text", default=None, help="Verbatim transcript of the reference clip")
    parser.add_argument("--model", default=None)
    parser.add_argument("--lang", default=None)
    parser.add_argument("--offline", action="store_true", help="Use only cached/local model files")
    args = parser.parse_args()

    model = args.model or DEFAULT_MODEL
    lang = args.lang or "Chinese"
    reference_audio = args.reference_audio
    reference_text = args.reference_text

    if args.voice:
        try:
            key, spec = resolve(args.voice)
        except VoiceError as exc:
            parser.error(str(exc))
        if spec.get("engine") != "local":
            parser.error(
                f"{spec.get('label') or key} 是 {spec.get('engine')} 音色，"
                "请用 scripts/synthesize.py（百炼）或 synthesize_breeze.py，不要走本地克隆"
            )
        preset_audio = ref_audio(spec)
        if not preset_audio.is_file():
            parser.error(f"音色 {key} 的参考音频不存在：{preset_audio}")
        # Locked voices (pfa / nahida) must match the fingerprint pinned in manifest.json.
        # An explicit --reference-audio is an intentional one-off override, so allow it.
        if args.reference_audio is None and spec.get("locked"):
            problem = check_reference(spec)
            if problem:
                parser.error(f"音色 {key} 已锁定，{problem}")
        reference_audio = reference_audio or preset_audio
        if reference_text is None:
            reference_text = str(spec.get("ref_text") or "")
        model = args.model or str(spec.get("model") or DEFAULT_MODEL)
        lang = args.lang or str(spec.get("lang") or lang)

    if reference_audio is None:
        parser.error("需要 --voice 或 --reference-audio")
    if not args.text.strip():
        parser.error("Text must be nonempty")
    if not Path(reference_audio).is_file():
        parser.error(f"Reference audio does not exist: {reference_audio}")
    if args.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"

    _ensure_mlx_env()

    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model

    model_obj = load_model(model)
    ref_info = sf.info(str(reference_audio))
    if ref_info.duration > 15.0:
        print(
            f"警告：参考音频 {ref_info.duration:.1f}s 超过 Qwen3 推荐的 3–15s，"
            "零样本克隆容易在句中/句末跑飞或反复生成",
            file=sys.stderr,
        )
    chunks = []
    sample_rate = 24000
    for result in model_obj.generate(
        text=args.text,
        ref_audio=str(reference_audio),
        ref_text=(reference_text or None),
        lang_code=lang,
        max_tokens=900,
        verbose=False,
    ):
        chunks.append(np.asarray(result.audio, dtype=np.float32))
        sample_rate = result.sample_rate
    if not chunks:
        raise RuntimeError("Model returned no audio")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    audio = np.concatenate(chunks)
    peak = float(np.abs(audio).max())
    if peak > 0.95:
        audio = (audio * (0.95 / peak)).astype(np.float32)
        print(f"已把峰值 {peak:.3f} 压到 0.95，避免削波失真", file=sys.stderr)
        peak = 0.95
    sf.write(args.output, audio, sample_rate)
    info = sf.info(args.output)
    rms = float(np.sqrt((audio.astype(np.float64) ** 2).mean()))
    print(
        f"Wrote {args.output} ({info.duration:.2f}s, {info.samplerate} Hz, "
        f"rms={rms:.3f}, peak={peak:.3f})"
    )

    expected = max(2.0, len(args.text.strip()) / 4.0)
    limit = max(20.0, expected * 2.5)
    if info.duration > limit:
        print(
            f"跑飞告警：文案 {len(args.text.strip())} 字预期约 {expected:.0f}s，"
            f"实际 {info.duration:.1f}s（上限 {limit:.0f}s）。这段别当成品，"
            "换 8–15s 干净参考音频或把长文案拆句重试。",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
