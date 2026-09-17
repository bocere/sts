# sts — SCOTUS to Speech

Monitors the Supreme Court's opinions page for newly released opinions,
downloads each PDF, converts it to clean text, and synthesizes it as audio —
with each opinion segmented by authoring Justice and read in a distinct,
accent-matched voice. Designed to run unattended on a cron schedule.

## How it works

1. `sts` scrapes the current SCOTUS term's slip-opinion listing and diffs it
   against `downloaded.json` (a record of already-processed PDF URLs).
2. New opinions are downloaded and converted PDF → text (`pdfminer.six`),
   with slip-opinion headers/footers stripped and soft-wrapped lines
   rejoined into paragraphs.
3. `voices.py` splits the text by authoring Justice (majority, concurrences,
   dissents — unsigned text like the syllabus gets a neutral voice), and
   synthesizes each segment with [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M)
   (base TTS) reshaped by [OpenVoice V2](https://github.com/myshell-ai/OpenVoice)'s
   `ToneColorConverter` toward a regional-accent reference clip for that
   Justice, plus small measured pitch/tone corrections. See
   `voices/profiles.json` for the per-Justice parameters and
   `LICENSE.md` for what the reference clips are and how they're licensed —
   **these are accent approximations built from anonymous public speech
   samples, not recordings or clones of the Justices.**
4. The finished WAV is written to `wav/`.

Everything is checkpointed: a killed/interrupted run picks back up from the
last completed segment/chunk instead of starting over.

## Prerequisites

- Linux or macOS, Python 3.10+
- `ffmpeg` on your `PATH` (`apt install ffmpeg`, `brew install ffmpeg`, etc.)
  — used by `pydub`/OpenVoice for audio I/O
- ~2 GB disk for Python dependencies (PyTorch, etc.) plus this repo's
  ~155 MB of voice reference clips and the OpenVoice checkpoint

A GPU is not required — the code runs OpenVoice's converter on CPU. If you
don't have a CUDA GPU, install the CPU build of PyTorch first to avoid a
multi-GB download (see step 3 below).

## Setup

```bash
cd sts
python3 -m venv venv
source venv/bin/activate

# CPU-only machines: install PyTorch's CPU wheel first (skip this line if
# you do have a CUDA GPU and want GPU acceleration).
pip install torch==2.12.1 --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
```

Make the entry point executable (it already is if you copied it with
permissions preserved):

```bash
chmod +x sts
```

## Running it

```bash
source venv/bin/activate
./sts
```

The first run for each Justice is slow: OpenVoice has to extract a speaker
embedding from that Justice's reference clip and from whichever Kokoro base
voice is paired with them (`voices/<justice>/se*.pth` and
`voices/_base_se/*.pth`), and these are cached to disk afterwards — later
runs reuse the cache instead of recomputing it.

`sts` creates `text/` (extracted opinion text), `wav/` (finished audio),
`action.log`, and `downloaded.json` on demand — none of these need to exist
beforehand.

### Running on cron

```cron
0 10 * * 1-5 cd /path/to/sts && ./venv/bin/python3 sts >> cron.log 2>&1
```

Runs weekday mornings; the SCOTUS opinions page updates on an irregular
schedule during the term, so a scheduled check simply finds nothing new
most days.

## Licensing note

The `voices/*/reference*.wav` clips are from the Speech Accent Archive
(George Mason University, CC BY-NC-SA 2.0) — personal, non-commercial use
only. See `LICENSE.md` for full per-clip attribution and the licenses of
the software this project depends on (Kokoro, OpenVoice, etc.) before
redistributing anything built with this program.
