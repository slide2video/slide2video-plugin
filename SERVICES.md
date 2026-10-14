# External services

| Service | Used by | Key | Who pays |
|---|---|---|---|
| ElevenLabs text-to-speech (`api.elevenlabs.io`) | `lv/narrate.py`, `lv/keys.py` | `ELEVENLABS_API_KEY`, supplied by each user in `~/.lesson-videos/keys.env` | the user |
| Microsoft Edge Read Aloud voices, unofficial, via the `edge-tts` package (`speech.platform.bing.com`) | `lv/voices.py` | none (free; default narrator when no ElevenLabs key) | free |
| Gemini API: Veo 3.1 Lite, Lyria 3.5 (`generativelanguage.googleapis.com`) | `lv/clips.py`, `lv/music.py`, `lv/keys.py` | `GEMINI_API_KEY`, optional, same file | the user |
| GitHub Actions | `.github/workflows/ci.yml` | none | free (public repo) |
| Downloads at first run: astral.sh (uv), PyPI, Playwright browser CDN, github.com (static-ffmpeg binaries) | `skills/setup`, `lv/tools.py` | none | free |
| Suno (`suno.com`) | `music-video` skills | none: used only through the user's own signed-in Chrome via Claude in Chrome; no API | the user (their Suno plan) |
| npm registry, Remotion's headless-browser CDN, PyPI and the alignment models' hubs (first run) | `music-video` `doctor`, `align` | none | free |
| slide2video.com (decks come down; videos, captions, stills and timing go up) | `lv/site.py`, `lv/worker.py` (`pair`, `worker`) | a per-Mac device token in the macOS Keychain (service `slide2video`), created by pairing | free (invite-only site run by the maintainer) |
| Poly Pizza (`poly.pizza`) | source of `music-video/studio/assets/models` (CC0), no runtime use | none | free |

The repo itself holds no keys.

`batatais` is an instruction-only plugin with no runtime service or API key. Its
workflow recommends public OpenStreetMap/Overpass queries and photographic research
(including Street View), and optional licensed textures from sources such as Poly
Haven. The user's agent makes those requests during a reconstruction; installation
only downloads the plugin from GitHub and does not contact those services.
