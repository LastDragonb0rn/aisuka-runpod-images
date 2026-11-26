"""Load every voice model the pod serves once, so its files land in HF_HOME.

Loading (rather than only downloading) also fetches what a model pulls in by
itself, such as TeraTTS's remote code. Runs on the CPU at build time; the
pod loads the same files on its GPU.
"""

import os

from companion.serve.engines import TeraSynthesizer, WavLMVoiceprinter, WhisperTranscriber

WHISPER = os.environ.get("WHISPER_MODEL", "Systran/faster-whisper-small")
IDENTITY = os.environ.get("IDENTITY_MODEL", "microsoft/wavlm-base-plus-sv")

WhisperTranscriber(model=WHISPER, device="cpu", compute_type="int8")
TeraSynthesizer(threads=1)
WavLMVoiceprinter(model=IDENTITY)
print("voice models cached in", os.environ.get("HF_HOME"))
