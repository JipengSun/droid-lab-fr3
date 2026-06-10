#!/usr/bin/env python3
"""Record microphone audio and transcribe to a robot language command.

Run via the openpi env (has faster-whisper + CUDA):

  cd ~/Desktop/openpi
  uv run python ~/Desktop/DROID/scripts/demo/speech_command.py

Options:
  --duration 5        seconds to record after Enter
  --model base        whisper model (tiny/base/small/medium)
  --list-devices      show microphone devices
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


def list_input_devices() -> None:
    print(sd.query_devices())
    print("Default input:", sd.default.device[0])


def record_audio(duration_s: float, sample_rate: int = 16000, device=None) -> np.ndarray:
    print(f"Recording {duration_s:.1f}s — speak now...", file=sys.stderr, flush=True)
    if device is not None:
        print(f"Using input device {device}", file=sys.stderr, flush=True)
    audio = sd.rec(
        int(duration_s * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    print("Recording done.", file=sys.stderr, flush=True)
    return audio.squeeze()


def transcribe(wav_path: Path, model_name: str, device: str) -> str:
    from faster_whisper import WhisperModel

    compute_type = "float16" if device == "cuda" else "int8"
    print(f"Transcribing with Whisper '{model_name}'...", file=sys.stderr, flush=True)
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(str(wav_path), language="en", vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    print("Transcription done.", file=sys.stderr, flush=True)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Speech → robot language command")
    parser.add_argument("--duration", type=float, default=5.0, help="Recording length in seconds")
    parser.add_argument("--model", type=str, default="base", help="Whisper model size")
    parser.add_argument("--device", type=str, default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--input-device", type=int, default=None, help="ALSA/Pulse input index (see --list-devices)")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--auto-start", action="store_true", help="Start recording immediately (no Enter prompt)")
    parser.add_argument("--wav-out", type=str, default=None, help="Optional path to save recording")
    args = parser.parse_args()

    if args.list_devices:
        list_input_devices()
        return 0

    if not args.auto_start:
        input("Press Enter to start recording...")
    else:
        print("Starting recording...", file=sys.stderr, flush=True)
    audio = record_audio(args.duration, args.sample_rate, device=args.input_device)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    sf.write(wav_path, audio, args.sample_rate)
    if args.wav_out:
        sf.write(args.wav_out, audio, args.sample_rate)
        print(f"Saved recording to {args.wav_out}", file=sys.stderr, flush=True)

    try:
        text = transcribe(wav_path, args.model, args.device)
    finally:
        wav_path.unlink(missing_ok=True)

    if not text:
        print("ERROR: no speech detected", file=sys.stderr)
        return 1

    # Rollout script reads the last line as the command.
    print(text, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
