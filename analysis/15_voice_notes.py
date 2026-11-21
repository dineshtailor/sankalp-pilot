"""Transcribe and translate the six voice notes locally (OpenAI Whisper, CPU). No audio leaves the machine.
Audio decoded with PyAV (no ffmpeg needed). Output: ../docs/voice/<file>.json and ../docs/voice/voice_transcripts.md
Usage: python -m analysis.15_voice_notes [model=medium]"""
import json
import sys
import time
from pathlib import Path

import av
import numpy as np
import whisper

SRC = Path(__file__).resolve().parents[2] / "pfizer-channel-engagement_learner-pack" / "data-pack" / "voice-notes"
OUT = Path(__file__).resolve().parents[2] / "docs" / "voice"
OUT.mkdir(parents=True, exist_ok=True)


def load_audio(path: Path, sr: int = 16000) -> np.ndarray:
    c = av.open(str(path))
    rs = av.AudioResampler(format="s16", layout="mono", rate=sr)
    chunks = []
    for frame in c.decode(audio=0):
        for f in rs.resample(frame):
            chunks.append(f.to_ndarray().reshape(-1))
    for f in rs.resample(None):
        chunks.append(f.to_ndarray().reshape(-1))
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def main(size="medium"):
    model = whisper.load_model(size, device="cpu")
    md = ["# Voice notes: transcripts and translations", "",
          f"Model: OpenAI Whisper `{size}`, run locally on CPU. Machine transcription of Indian languages is imperfect: "
          "every claim below is treated as a lead and tested against the data before use.", ""]
    for f in sorted(SRC.glob("*")):
        if f.suffix.lower() not in (".ogg", ".m4a"):
            continue
        t = time.time()
        audio = load_audio(f)
        tr = model.transcribe(audio, task="transcribe", fp16=False, condition_on_previous_text=False)
        en = model.transcribe(audio, task="translate", fp16=False, language=tr["language"], condition_on_previous_text=False)
        rec = {"file": f.name, "language": tr["language"], "seconds_audio": round(len(audio) / 16000, 1),
               "transcript": tr["text"].strip(), "translation_en": en["text"].strip(),
               "segments_en": [{"start": round(s["start"], 1), "text": s["text"].strip()} for s in en["segments"]]}
        (OUT / f"{f.stem}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        md += [f"## {f.name}", f"Detected language: **{rec['language']}** · {rec['seconds_audio']} s audio", "",
               "**Transcript (as heard):**", "", rec["transcript"], "", "**English translation:**", "", rec["translation_en"], ""]
        print(f.name, rec["language"], rec["seconds_audio"], f"{time.time() - t:.0f}s", flush=True)
    (OUT / "voice_transcripts.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "medium")
