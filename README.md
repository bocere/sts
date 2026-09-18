# SCOTUS to Speech

Do you love listening to oral arguments at the Supreme Court?
Are you sad there's no recordings of each Justice reading their own writing?
Me too!

If we can't clone their voices, we can at least *approximate* their voices.

This program monitors the Supreme Court's opinions page for newly released opinions,
downloads each PDF, and converts each opinion segment to a Justice-approximate voice.

## How it works

1. `sts` scrapes the current SCOTUS term's slip-opinion listing and diffs it
   against `downloaded.json` (a record of already-processed PDF URLs).
2. New opinions are downloaded and converted from PDF to text 
   with headers and footers stripped and soft-wrapped lines
   rejoined into paragraphs.
3. `voices.py` splits the text by authoring Justice (majority, concurrences,
   dissents — unsigned text like the syllabus gets a neutral voice), and
   synthesizes each segment with [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M)
   (base TTS) reshaped by [OpenVoice V2](https://github.com/myshell-ai/OpenVoice)'s
   `ToneColorConverter` toward a regional-accent reference clip for that
   Justice, plus small measured pitch/tone corrections. See
   `voices/profiles.json` for the per-Justice parameters and
   `LICENSE.md` for what the reference clips are and how they're licensed. 
4. The finished WAV is written to `wav/`.

**These are accent approximations built from anonymous public speech
samples, not recordings or clones of the Justices.**

## Prerequisites

- Linux or macOS
- Python 3.10+
- `ffmpeg` on your `PATH` (`sudo apt install ffmpeg`)
- [Git LFS](https://git-lfs.github.com) (`sudo apt install git-lfs`)

## Setup

`models/openvoice/checkpoint.pth` (125 MB) is tracked with
[Git LFS](https://git-lfs.github.com) (`.gitattributes` in this repo), since
it's over GitHub's 100 MB plain-file limit. Install it once before cloning:

```bash
git lfs install
git clone https://github.com/bocere/sts
cd sts
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install --no-deps "MyShell-OpenVoice @ git+https://github.com/myshell-ai/OpenVoice.git@74a1d147b17a8c3092dd5430504bd83ef6c7eb23"
```

## Convert SCOTUS to Speech

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

## Convert a Single Opinion

Use the `--file` option to convert one opinion PDF you already have on disk
without checking the SCOTUS site or touching `downloaded.json`.

```bash
./sts --file path/to/opinion.pdf
```

The case name is taken from the PDF's filename (so `Loper Bright v.
Raimondo.pdf` produces `text/Loper Bright v. Raimondo.txt` and
`wav/Loper Bright v. Raimondo.wav`); if a file with that name already
exists, a `[2]`, `[3]`, ... suffix is added rather than overwriting it.
This mode never reads or updates `downloaded.json`, so it won't affect
(and isn't affected by) the normal scheduled run.

## Troubleshooting

If you cloned without `git-lfs` installed, first install `git-lfs` and then:

```bash
git lfs pull
```
This will fetch the real file in place of the pointer.

## Licensing note

The `voices/*/reference*.wav` clips are from the Speech Accent Archive
(George Mason University, CC BY-NC-SA 2.0) — personal, non-commercial use
only. See `LICENSE.md` for full per-clip attribution and the licenses of
the software this project depends on (Kokoro, OpenVoice, etc.) before
redistributing anything built with this program.
