"""Paths, model IDs and prices. Preview model names change: update them here only."""
from __future__ import annotations

import os
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
ENTRY = PLUGIN_ROOT / "scripts" / "lesson-videos.py"
ENGINE_JS = PLUGIN_ROOT / "engine" / "engine.js"
FONTS_DIR = PLUGIN_ROOT / "fonts"
FONT_FILES = ("PatrickHand-Regular.ttf", "Nunito.ttf")


def home() -> Path:
    """Per-user folder for keys, sound effects and caches."""
    return Path(os.environ.get("LESSON_VIDEOS_HOME") or Path.home() / ".lesson-videos")


ELEVEN_ROOT = "https://api.elevenlabs.io/v1"
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_FORMAT = "mp3_44100_128"            # 192 kbps needs a paid plan
VOICE_SETTINGS = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True}
DEFAULT_VOICE = "cgSgspJ2msm6clMCkdW9"     # Jessica: playful, bright, warm (premade voice)
NARRATION_WORKERS = 2                      # the ElevenLabs free plan allows 2 concurrent requests
EDGE_VOICE = "en-US-AvaMultilingualNeural"  # free Microsoft voice used when there is no ElevenLabs key

GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta"
VEO_MODEL = "veo-3.1-lite-generate-preview"
VEO_SECONDS = 8
VEO_PRICE_PER_SECOND = 0.05                # USD at 720p
LYRIA_MODEL = "lyria-3.5"
LYRIA_PRICE = 0.08                         # USD per track

CHARS_PER_MINUTE = 900                     # narration characters per video minute (~150 wpm)
FPS = 30
W, H = 1920, 1080
USER_AGENT = "lesson-videos/0.2 (+https://github.com/DanielLandi/plugins)"
