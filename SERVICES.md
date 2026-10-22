# External services

| Service | Used by | Key | Who pays |
|---|---|---|---|
| ElevenLabs text-to-speech (`api.elevenlabs.io`) | `lv/narrate.py`, `lv/keys.py` | `ELEVENLABS_API_KEY`, supplied by each user in `~/.slide2video/keys.env` | the user |
| Microsoft Edge Read Aloud voices, unofficial, via the `edge-tts` package (`speech.platform.bing.com`) | `lv/voices.py` | none (free; default narrator when no ElevenLabs key) | free |
| Gemini API: Lyria 3.5; Veo 3.1 Lite until Google shut it down on 2026-10-22 (AI clips off, `CLIPS_ENABLED`) (`generativelanguage.googleapis.com`) | `lv/clips.py`, `lv/music.py`, `lv/keys.py` | `GEMINI_API_KEY`, optional, same file | the user |
| GitHub Actions | `.github/workflows/ci.yml` | none | free (public repo) |
| Downloads at first run: astral.sh (uv), PyPI, Playwright browser CDN, github.com (static-ffmpeg binaries) | `skills/setup`, `lv/tools.py` | none | free |
| slide2video.com (decks come down; videos, captions, stills and timing go up) | `lv/site.py`, `lv/worker.py` (`pair`, `worker`) | a per-Mac device token in the macOS Keychain (service `slide2video`), created by pairing | free (invite-only site run by the maintainer) |

The repo itself holds no keys.
