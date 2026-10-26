"""Paths, model IDs and prices. Preview model names change: update them here only."""
from __future__ import annotations

import os
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
ENTRY = PLUGIN_ROOT / "scripts" / "slide2video.py"
ENGINE_JS = PLUGIN_ROOT / "engine" / "engine.js"
FONTS_DIR = PLUGIN_ROOT / "fonts"
FONT_FILES = ("PatrickHand-Regular.ttf", "Nunito.ttf")


def home() -> Path:
    """Per-user folder for keys, sound effects and caches."""
    return Path(os.environ.get("LESSON_VIDEOS_HOME") or Path.home() / ".slide2video")


def _copy_once(old: Path, new: Path) -> None:
    """Copy old to new if new doesn't exist yet: into a temporary sibling first, then one rename, so an interrupted or
    concurrent copy never leaves a half-filled `new`. Symlinks stay symlinks; file modes are kept."""
    import shutil
    import tempfile
    import time
    if new.exists() or not old.exists():
        return
    new.parent.mkdir(parents=True, exist_ok=True)
    for stale in new.parent.glob(new.name + ".partial-*"):     # only old ones: a fresh one may be another run's live copy
        try:
            if time.time() - stale.stat().st_mtime > 3600:
                shutil.rmtree(stale, ignore_errors=True) if stale.is_dir() else stale.unlink(missing_ok=True)
        except OSError:
            pass
    tmp = Path(tempfile.mkdtemp(prefix=new.name + ".partial-", dir=new.parent))
    try:
        if old.is_dir():
            shutil.copytree(old, tmp / "x", symlinks=True)
        else:
            shutil.copy2(old, tmp / "x")
        try:
            (tmp / "x").rename(new)
        except OSError:
            if not new.exists():            # someone else finished first: fine; anything else is a real error
                raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def migrate_home() -> None:
    """First run after the lesson-videos -> slide2video rename: copy ~/.lesson-videos and the old settings file to their
    new names, leaving the old ones as they are. Folders that hold work are not copied (see project and worker)."""
    from . import project
    if not os.environ.get("LESSON_VIDEOS_HOME"):
        _copy_once(Path.home() / ".lesson-videos", home())
    if not os.environ.get("LESSON_VIDEOS_SETTINGS"):
        _copy_once(project.old_settings_file(), project.settings_file())


ELEVEN_ROOT = "https://api.elevenlabs.io/v1"
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_FORMAT = "mp3_44100_128"            # 192 kbps needs a paid plan
VOICE_SETTINGS = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True}
# The ElevenLabs voices offered by name (premade voices, usable on every plan); script.json "voice" takes a name
# or any voice ID.
ELEVEN_VOICES = {
    "jessica": "cgSgspJ2msm6clMCkdW9",     # young American woman: playful, bright, warm
    "daniel": "onwK4e9ZLuTAKqWW03F9",      # British man: steady, news-presenter tone
}
DEFAULT_VOICE = ELEVEN_VOICES["jessica"]
NARRATION_WORKERS = 2                      # the ElevenLabs free plan allows 2 concurrent requests
EDGE_VOICE = "en-US-AvaMultilingualNeural"  # free Microsoft voice used when there is no ElevenLabs key
EDGE_HOST = "speech.platform.bing.com"     # the free Microsoft voice's server
SITE_URL = "https://slide2video.com"      # the website; LV_SITE_URL overrides it (tests, previews)
# The model every website job runs on, as a Claude Code alias so it follows the newest Opus without a release.
# Without it a job gets whatever default the account has that day (one lesson ran half on Fable, ~2.5x the cost).
# LV_CLAUDE_MODEL overrides it (comparisons).
CLAUDE_MODEL = "opus"

GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def _root(env: str, default: str) -> str:
    return (os.environ.get(env) or "").strip().rstrip("/") or default


def eleven_root() -> str:
    """The ElevenLabs address: LV_ELEVEN_ROOT if set and not blank, else the vendor's."""
    return _root("LV_ELEVEN_ROOT", ELEVEN_ROOT)


def gemini_root() -> str:
    """The Gemini address: LV_GEMINI_ROOT if set and not blank, else the vendor's."""
    return _root("LV_GEMINI_ROOT", GEMINI_ROOT)

# Gemini Omni Flash (image to video), Veo's successor on the Gemini API since Google shut Veo there on 2026-10-22
CLIP_MODEL = "gemini-omni-1.1-flash"
CLIP_SECONDS = 10                          # one generation; there is no length setting
# USD for one 720p clip: about 58,000 video tokens at $17.50 per 1M, plus about 1,200 input tokens at $1.50 per 1M
CLIP_PRICE = 1.02
LYRIA_MODEL = "lyria-3.5"
LYRIA_PRICE = 0.08                         # USD per track

CHARS_PER_MINUTE = 900                     # narration characters per video minute (~150 wpm)
FPS = 30
W, H = 1920, 1080
USER_AGENT = "slide2video/1.1 (+https://github.com/slide2video/slide2video-plugin)"
