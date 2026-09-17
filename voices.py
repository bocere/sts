"""
Per-Justice voice profiles for sts.

Segments an opinion's cleaned text by authoring Justice (majority opinion,
concurrences, dissents), and synthesizes each segment in a distinct voice:
a Kokoro base voice (for gender/prosody) reshaped by OpenVoice's
ToneColorConverter toward a regional-accent reference clip from the Speech
Accent Archive (see voices/profiles.json and LICENSE.md for sourcing and
licensing). These are accent approximations from anonymous SAA volunteers,
not recordings or clones of the Justices themselves.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import torch

SCRIPT_DIR = Path(__file__).parent
VOICES_DIR = SCRIPT_DIR / "voices"
BASE_SE_DIR = VOICES_DIR / "_base_se"
PROCESSED_DIR = VOICES_DIR / "_processed"
BIN_DIR = SCRIPT_DIR / "bin"
CONVERTER_CONFIG = SCRIPT_DIR / "models" / "openvoice" / "config.json"
CONVERTER_CKPT = SCRIPT_DIR / "models" / "openvoice" / "checkpoint.pth"
KOKORO_BIN = SCRIPT_DIR / "venv" / "bin" / "kokoro"

# Bundled static ffmpeg (openvoice/pydub shell out to it for audio I/O).
os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

with open(SCRIPT_DIR / "voices" / "profiles.json") as f:
    _PROFILES = json.load(f)["justices"]

SURNAME_TO_KEY = {
    surname: key
    for key, profile in _PROFILES.items()
    for surname in profile["surnames"]
}

# Voice used for text with no identified Justice author: the case syllabus
# (written by the Reporter of Decisions, not a Justice), per curiam opinions,
# and unsigned orders. Deliberately distinct from every assigned Justice voice.
NEUTRAL_VOICE = "af_nova"

_CALIBRATION_TEXT = (
    "The following is a synthetic reading of a Supreme Court opinion, "
    "generated for accessibility purposes. Voices are computer generated "
    "approximations based on public regional speech samples and are not "
    "recordings of the Justices. The judgment of the Court of Appeals for "
    "the relevant circuit is affirmed in part and reversed in part, and "
    "the case is remanded for further proceedings consistent with this "
    "opinion."
)

DISCLAIMER_TEXT = (
    "The following is a synthetic reading. Voices are A I generated "
    "approximations based on public regional speech samples, not "
    "recordings of the Justices."
)

AUTHOR_BYLINE_RE = re.compile(
    r"(?m)^(?:CHIEF\s+JUSTICE|JUSTICE)\s+([A-Z]+)\s*,?\s*"
    r"(?:with\s+whom\s+(?:CHIEF\s+JUSTICE|JUSTICE)\s+[A-Z]+"
    r"(?:,\s*(?:CHIEF\s+JUSTICE|JUSTICE)\s+[A-Z]+)*"
    r"(?:,?\s*and\s+(?:CHIEF\s+JUSTICE|JUSTICE)\s+[A-Z]+)?"
    r"\s+joins?,?\s*)?"
    # A short qualifier can precede the keyword, e.g. "..., with whom
    # JUSTICE SOTOMAYOR joins as to the introduction and Part I, concurring."
    r"(?:[a-zA-Z][^,\n]{0,60},\s*)?"
    r"(delivered\s+the\s+opinion\s+of\s+the\s+Court"
    r"|concurring\s+in\s+the\s+judgment\s+and\s+dissenting\s+in\s+part"
    r"|concurring\s+in\s+part\s+and\s+dissenting\s+in\s+part"
    r"|concurring\s+in\s+the\s+judgment"
    r"|concurring"
    r"|dissenting)\b"
)


def detect_author_segments(text: str) -> list[dict]:
    """
    Split cleaned/paragraph-joined opinion text into per-author segments.

    Returns a list of {"key": justice_key_or_None, "text": segment_text}.
    Text before the first byline (the syllabus) and documents with no
    byline at all (per curiam, orders) get key=None (NEUTRAL_VOICE).
    Each segment's text includes its own byline sentence, so it's read
    aloud in that Justice's own voice ("Justice Thomas, concurring...").
    """
    matches = list(AUTHOR_BYLINE_RE.finditer(text))
    if not matches:
        return [{"key": None, "text": text.strip()}] if text.strip() else []

    segments = []
    lead = text[: matches[0].start()].strip()
    if lead:
        segments.append({"key": None, "text": lead})

    for i, m in enumerate(matches):
        surname = m.group(1)
        key = SURNAME_TO_KEY.get(surname)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment_text = text[m.start() : end].strip()
        if segment_text:
            segments.append({"key": key, "text": segment_text})

    return segments


# ── OpenVoice ToneColorConverter (lazy singleton) ──────────────────────────────
_converter = None


def _get_converter():
    global _converter
    if _converter is None:
        from openvoice.api import ToneColorConverter

        _converter = ToneColorConverter(str(CONVERTER_CONFIG), device="cpu")
        _converter.load_ckpt(str(CONVERTER_CKPT))
    return _converter


def _extract_se(wav_path: Path, cache_path: Path) -> torch.Tensor:
    if cache_path.exists():
        return torch.load(cache_path, map_location="cpu")
    from openvoice import se_extractor

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    se, _ = se_extractor.get_se(
        str(wav_path), _get_converter(), target_dir=str(PROCESSED_DIR), vad=True
    )
    torch.save(se, cache_path)
    return se


def _get_base_se(kokoro_voice: str) -> torch.Tensor:
    """Speaker embedding for a Kokoro stock voice, cached after first use.

    Extracted once from a fixed calibration clip (long enough for OpenVoice's
    VAD-based splitter) rather than per-segment audio, since the embedding
    characterizes the base voice's timbre in general, not one utterance.
    """
    cache_path = BASE_SE_DIR / f"{kokoro_voice}.pth"
    calib_wav = BASE_SE_DIR / f"{kokoro_voice}.wav"
    if not calib_wav.exists():
        calib_wav.parent.mkdir(parents=True, exist_ok=True)
        _run_kokoro(_CALIBRATION_TEXT, kokoro_voice, calib_wav)
    return _extract_se(calib_wav, cache_path)


def _get_target_se(justice_key: str) -> torch.Tensor:
    """Speaker embedding for a Justice's accent target. Most profiles use
    a single SAA reference clip; some use a "saa_speakers" blend (a list
    of 2+ SAA speakers found empirically to land closer, together, to the
    Justice's real measured voice than any single available clip does —
    see distance/saa_search.py). A blend's embedding is the elementwise
    mean of each member's individually-extracted SE, matching how
    saa_search.py scored the blend option in the first place."""
    profile = _PROFILES[justice_key]
    justice_dir = VOICES_DIR / justice_key
    blend = profile.get("saa_speakers")
    if not blend:
        return _extract_se(justice_dir / "reference.wav", justice_dir / "se.pth")

    cache_path = justice_dir / "se.pth"
    if cache_path.exists():
        return torch.load(cache_path, map_location="cpu")

    member_ses = [
        _extract_se(
            justice_dir / f"reference_{speaker['label']}.wav",
            justice_dir / f"se_{speaker['label']}.pth",
        )
        for speaker in blend
    ]
    blended = torch.mean(torch.stack(member_ses), dim=0)
    justice_dir.mkdir(parents=True, exist_ok=True)
    torch.save(blended, cache_path)
    return blended


# ── Kokoro base synthesis ───────────────────────────────────────────────────────
def _run_kokoro(text: str, voice: str, out_path: Path, speed: float = 1.0) -> None:
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(text)
        tmp_txt = tf.name
    # Write to a .tmp path and rename into place at the end, so a killed
    # process never leaves a half-written file that looks "done" on resume.
    tmp_wav = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)
    try:
        subprocess.run(
            [str(KOKORO_BIN), "-m", voice, "-i", tmp_txt, "-o", str(tmp_wav),
             "-s", str(speed)],
            check=True,
        )
        os.replace(tmp_wav, out_path)
    finally:
        os.unlink(tmp_txt)
        tmp_wav.unlink(missing_ok=True)


# ToneColorConverter.convert() runs the whole clip through a normalizing-flow
# model in a single forward pass — no internal chunking. A long majority
# opinion can be an hour or more of base audio, and converting that in one
# shot is what OOM-killed this process twice on the same segment. Cutting to
# clips no longer than this keeps peak memory bounded regardless of how long
# the opinion is.
CONVERT_CHUNK_MS = 120_000


def _split_at_silence(audio, target_ms: int) -> list[int]:
    """Cut points (ms) spaced roughly `target_ms` apart, snapped to the
    nearest detected silence so conversion chunks never split mid-word."""
    from pydub.silence import detect_silence

    duration_ms = len(audio)
    if duration_ms <= target_ms * 1.5:
        return [0, duration_ms]

    silences = detect_silence(audio, min_silence_len=150, silence_thresh=audio.dBFS - 16)
    cuts = [0]
    next_target = target_ms
    for start, end in silences:
        mid = (start + end) // 2
        if mid >= next_target:
            cuts.append(mid)
            next_target = mid + target_ms
    if cuts[-1] != duration_ms:
        cuts.append(duration_ms)
    return cuts


def _apply_dsp_corrections(
    wav_path: Path, pitch_semitones: float, tilt_db_per_oct: float
) -> None:
    """In-place post-processing on a converted chunk: a small pitch-shift
    (closing residual median-F0 gap) and a spectral-tilt correction
    (closing residual brightness/darkness gap), each measured against a
    Justice's real "prepared remarks" register, not oral argument -- see
    distance/lecture_voice_profiles.json. The tilt correction is a
    frequency-domain gain curve anchored at 1kHz (0 dB there) so it
    reshapes brightness without materially changing overall loudness.
    A no-op when both corrections are negligible, so untouched profiles
    pay no extra encoding cost."""
    if abs(pitch_semitones) < 0.05 and abs(tilt_db_per_oct) < 0.1:
        return

    import numpy as np
    import librosa
    import soundfile as sf

    y, sr = librosa.load(str(wav_path), sr=None, mono=True)

    if abs(pitch_semitones) >= 0.05:
        y = librosa.effects.pitch_shift(y, sr=sr, n_steps=pitch_semitones)

    if abs(tilt_db_per_oct) >= 0.1:
        n_fft = 2048
        S = librosa.stft(y, n_fft=n_fft)
        freqs = np.maximum(librosa.fft_frequencies(sr=sr, n_fft=n_fft), 20.0)
        gain_db = tilt_db_per_oct * np.log2(freqs / 1000.0)
        gain = (10.0 ** (gain_db / 20.0))[:, None]
        y = librosa.istft(S * gain, length=len(y))

    sf.write(str(wav_path), y, sr)


def synthesize_segment(text: str, justice_key: str | None, out_path: Path) -> Path:
    """Synthesize one author segment, applying accent conversion if attributed."""
    if justice_key is None:
        _run_kokoro(text, NEUTRAL_VOICE, out_path)
        return out_path

    from pydub import AudioSegment

    profile = _PROFILES[justice_key]
    base_voice = profile["kokoro_base_voice"]
    speed = profile.get("kokoro_speed", 1.0)
    pitch_nudge = profile.get("pitch_nudge_semitones", 0.0)
    tilt_correction = profile.get("tilt_correction_db_per_oct", 0.0)
    base_path = out_path.with_suffix(".base.wav")
    if not base_path.exists():
        _run_kokoro(text, base_voice, base_path, speed=speed)

    src_se = _get_base_se(base_voice)
    tgt_se = _get_target_se(justice_key)
    converter = _get_converter()

    base_audio = AudioSegment.from_wav(base_path)
    cuts = _split_at_silence(base_audio, CONVERT_CHUNK_MS)

    # Per-chunk checkpointing, same philosophy as the segment-level one in
    # synthesize_opinion: only regenerate chunks missing after a kill.
    # DSP corrections run per-chunk too (not on the full combined segment)
    # to keep peak memory bounded regardless of opinion length, same
    # reasoning as chunking the OpenVoice conversion itself.
    chunks_dir = out_path.parent / f".{out_path.stem}_convert_chunks"
    chunks_dir.mkdir(exist_ok=True)
    chunk_paths = []
    for i in range(len(cuts) - 1):
        chunk_out = chunks_dir / f"{i:04d}.wav"
        if not chunk_out.exists():
            chunk_src = chunks_dir / f"{i:04d}.src.wav"
            base_audio[cuts[i]:cuts[i + 1]].export(chunk_src, format="wav")
            tmp_chunk = chunks_dir / f"{i:04d}.tmp.wav"
            converter.convert(
                audio_src_path=str(chunk_src),
                src_se=src_se,
                tgt_se=tgt_se,
                output_path=str(tmp_chunk),
                message="@sts-scotus",
            )
            _apply_dsp_corrections(tmp_chunk, pitch_nudge, tilt_correction)
            os.replace(tmp_chunk, chunk_out)
            chunk_src.unlink(missing_ok=True)
        chunk_paths.append(chunk_out)

    combined = AudioSegment.silent(duration=0)
    for p in chunk_paths:
        combined += AudioSegment.from_wav(p)
    tmp_out = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)
    combined.export(tmp_out, format="wav")
    os.replace(tmp_out, out_path)

    base_path.unlink(missing_ok=True)
    for p in chunk_paths:
        p.unlink()
    chunks_dir.rmdir()
    return out_path


def synthesize_opinion(text: str, output_path: Path) -> None:
    """Segment `text` by author and synthesize the full multi-voice opinion,
    with a spoken disclaimer prepended, to `output_path`.

    Resumable: each segment is written under a checkpoint directory next to
    `output_path` and only regenerated if missing, so re-running after an
    interruption (e.g. a killed background job) picks up where it left off
    instead of starting over. The checkpoint directory is only removed after
    the final file is successfully exported.
    """
    from pydub import AudioSegment

    segments = detect_author_segments(text)
    if not segments:
        raise ValueError("No text to synthesize")

    tmp_dir = output_path.parent / f".{output_path.stem}_segments"
    tmp_dir.mkdir(exist_ok=True)

    disclaimer_path = tmp_dir / "000_disclaimer.wav"
    if not disclaimer_path.exists():
        _run_kokoro(DISCLAIMER_TEXT, NEUTRAL_VOICE, disclaimer_path)

    seg_paths = [disclaimer_path]
    for i, seg in enumerate(segments):
        seg_path = tmp_dir / f"{i + 1:03d}_{seg['key'] or 'neutral'}.wav"
        if not seg_path.exists():
            synthesize_segment(seg["text"], seg["key"], seg_path)
        seg_paths.append(seg_path)

    combined = AudioSegment.silent(duration=0)
    for i, p in enumerate(seg_paths):
        combined += AudioSegment.from_wav(p)
        if i < len(seg_paths) - 1:
            combined += AudioSegment.silent(duration=700 if i == 0 else 500)

    combined.export(output_path, format="wav")

    for f in tmp_dir.glob("*.wav"):
        f.unlink()
    tmp_dir.rmdir()
