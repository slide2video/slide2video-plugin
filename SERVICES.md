# External services

| Service | Used by | Key | Who pays |
|---|---|---|---|
| ElevenLabs text-to-speech (`api.elevenlabs.io`) | `lv/narrate.py`, `lv/keys.py` | `ELEVENLABS_API_KEY`, supplied by each user in `~/.lesson-videos/keys.env` | the user |
| Microsoft Edge Read Aloud voices, unofficial, via the `edge-tts` package (`speech.platform.bing.com`) | `lv/voices.py` | none (free; default narrator when no ElevenLabs key) | free |
| Gemini API: Veo 3.1 Lite, Lyria 3.5 (`generativelanguage.googleapis.com`) | `lv/clips.py`, `lv/music.py`, `lv/keys.py` | `GEMINI_API_KEY`, optional, same file | the user |
| GitHub Actions | `.github/workflows/ci.yml` | none | free (public repo) |
| Downloads at first run: astral.sh (uv), PyPI, Playwright browser CDN, github.com (static-ffmpeg binaries) | `skills/setup`, `lv/tools.py` | none | free |

The repo itself holds no keys.
