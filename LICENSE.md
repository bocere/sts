# Licenses and attribution

`sts` (SCOTUS to Speech) combines several third-party tools, models, and audio
sources. This file records the license terms and attribution for each,
particularly for the per-Justice voice profiles feature (`voices.py`,
`voices/`), which uses audio from a third-party archive.

## Voice profile source audio

**[Speech Accent Archive](https://accent.gmu.edu)** (SAA), George Mason University.
License: **CC BY-NC-SA 2.0** (https://creativecommons.org/licenses/by-nc-sa/2.0/).

Fourteen short reference clips (anonymous volunteer speakers reading a
standard elicitation paragraph) were downloaded and trimmed to build
regional-accent reference embeddings for the OpenVoice tone conversion step
described below — one clip each for most Justices, and a 3-clip blend for
Alito, Sotomayor, and Kavanaugh (see `voices/profiles.json`'s `saa_speakers`
entries; a blend's embedding is the average of its members' embeddings).
**These are recordings of anonymous SAA volunteers, not the Justices** — used
only to approximate the general regional accent of each Justice's formative
years. See `voices/profiles.json` for the full rationale and caveats per
Justice, several of which are acknowledged imperfect proxies (nearest
available region/gender, not an exact hometown match).

Per-clip attribution (Speech Accent Archive, George Mason University, CC
BY-NC-SA 2.0):

| Justice | SAA sample | Source |
|---|---|---|
| Roberts | english524 (Downers Grove, IL) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=1890 |
| Thomas | english451 (Hazlehurst, GA) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=1546 |
| Alito | english325 (Reading, PA)<br>english379 (Summit, NJ)<br>english223 (Erie, PA) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=1176<br>https://accent.gmu.edu/browse_language.php?function=detail&speakerid=1321<br>https://accent.gmu.edu/browse_language.php?function=detail&speakerid=767 |
| Sotomayor | english6 (Brooklyn, NY)<br>english556 (Brooklyn, NY)<br>english525 (Albion, NY) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=121<br>https://accent.gmu.edu/browse_language.php?function=detail&speakerid=2050<br>https://accent.gmu.edu/browse_language.php?function=detail&speakerid=1893 |
| Kagan | english556 (Brooklyn, NY) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=2050 |
| Gorsuch | english342 (Kansas City, MO) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=1225 |
| Kavanaugh | english340 (Charleston, WV)<br>english137 (Charleston, WV)<br>english657 (Alexandria, VA) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=1222<br>https://accent.gmu.edu/browse_language.php?function=detail&speakerid=509<br>https://accent.gmu.edu/browse_language.php?function=detail&speakerid=3035 |
| Barrett | english83 (Winnfield, LA) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=147 |
| Jackson | english568 (Quincy, FL) | https://accent.gmu.edu/browse_language.php?function=detail&speakerid=2103 |

**Compliance note (NonCommercial / ShareAlike):** this project's use of these
clips is personal and non-commercial, and the derived audio (opinion
recordings) is kept locally, not publicly redistributed. If this project's
output is ever published or distributed beyond personal use, the NC and
ShareAlike terms of CC BY-NC-SA 2.0 would need to be revisited.

### IDEA (International Dialects of English Archive) — deliberately NOT used

[dialectsarchive.com](https://www.dialectsarchive.com) was evaluated as an
alternative/additional accent source and rejected. Per its
[copyright/credit page](https://www.dialectsarchive.com/copyright-credit-information),
reuse of sound files beyond simple in-browser playback ("you may not ...
distribute any sound files, or portion thereof, without the express written
consent of IDEA and the payment of a fee appropriate to the intended use")
requires permission that was not obtained. An earlier, separate local
prototype (`/home/ben/ai/voice_profile/`) had downloaded IDEA New Jersey
clips for offline voice cloning; those files were deleted for this reason.

## Software

| Component | License | Notes |
|---|---|---|
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Apache 2.0 | Base TTS engine — generates the underlying speech before accent conversion. |
| [OpenVoice V2](https://github.com/myshell-ai/OpenVoice) (code + `converter` checkpoint) | MIT | Provides `ToneColorConverter`, used to reshape Kokoro output toward each Justice's SAA reference accent. Converted audio carries OpenVoice's default inaudible watermark (`enable_watermark=True`), left on as a responsible-use signal that the audio is AI-generated. |
| pdfminer.six | MIT | PDF → text extraction. |
| beautifulsoup4 | MIT | HTML parsing of the SCOTUS opinions listing. |
| requests | Apache 2.0 | HTTP client. |
| lxml | BSD | HTML/XML parser backend for BeautifulSoup. |
| librosa, pydub, wavmark, faster-whisper, torch/torchaudio, and other OpenVoice runtime dependencies | Various OSS (BSD/MIT/Apache) | Installed as needed by OpenVoice's `se_extractor`; see each package's own license for details. |

## Static binaries

`bin/ffmpeg`, `bin/ffprobe` — static builds from
[johnvansickle.com/ffmpeg](https://johnvansickle.com/ffmpeg/) (FFmpeg,
LGPL/GPL depending on build configuration), used only locally for audio
format conversion during accent-embedding extraction.
