---
name: setup
description: Use once per computer before making lesson videos, or whenever lesson-videos says a tool or key is missing. Installs uv, the renderer and ffmpeg, then helps the teacher choose a narrator voice (a free one needs no account) and optionally create ElevenLabs and Gemini API keys, checking them without ever showing them in chat. Also use it when the teacher says they copied a key and wants it saved.
---

# lesson-videos setup

You are helping a teacher who may never have used a terminal. Explain each step in one or two plain sentences, do the technical work yourself, and ask them only to click in their browser or paste into the file you open.

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```

If that path doesn't exist (in some claude.ai sessions `${CLAUDE_SKILL_DIR}` comes through empty), the plugin is under `/root/.claude/plugins/synced/`: use the `lesson-videos/scripts/lesson-videos.py` you find there.

**Never ask for an API key in chat, never read or print `keys.env`.** If the teacher pastes a key into the chat anyway, tell them it's safest to delete that key on the website and create a new one, then continue.

## 1. uv

Check whether `uv` works: run `uv --version`. If that fails, try the per-user install location: `~/.local/bin/uv --version` (macOS, and Git Bash on Windows) or `& "$HOME\.local\bin\uv.exe" --version` (PowerShell). If one works, use that path, quoted, in place of `uv` for the rest of this session.

If uv is missing, tell the teacher you're installing uv, a small free tool that downloads everything else (no administrator password needed), then run:
- macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Then use the full path above (the current window won't see uv on its PATH until Claude Code restarts).

## 2. Doctor

Tell the teacher the first run downloads about 500 MB (Python libraries, a headless Chrome for drawing frames, ffmpeg) and can take several minutes. Run it with the Bash tool's longest timeout (10 minutes); if it still times out, simply run it again, since finished downloads are kept. Run:

```
LV doctor --no-keys
```

Every line should start with ✓. For each ✗, do what the message says. Common ones:
- **Chromium / downloads blocked**: school networks sometimes block downloads. Suggest a home network, or ask IT to allow astral.sh, pypi.org, files.pythonhosted.org, github.com and Playwright's browser downloads (cdn.playwright.dev).
- **ffmpeg can't write H.264**: macOS `brew install ffmpeg`; Windows `winget install Gyan.FFmpeg`; then run doctor again.

## 3. Narrator voice: free, or ElevenLabs

**If Claude in Chrome is connected** (`mcp__claude-in-chrome__tabs_context_mcp` answers), offer to do the clicking: for ElevenLabs follow `/lesson-videos:elevenlabs-get-api-key`, for Gemini `/lesson-videos:google-get-api-key`; both save the key with `LV keys paste`, so skip step 5 for that key. Otherwise use the steps below; the teacher can also follow the illustrated guides in `${CLAUDE_SKILL_DIR}/../../docs/keys/`.

Videos work with **no accounts and no keys at all**. Explain the two choices in plain words:
- **Free Microsoft voice** (default): a natural-sounding voice from Microsoft Edge's Read Aloud feature. No account and no cost. It is an unofficial Microsoft service, fine for classroom use but not for commercial videos, and the narration text is sent to Microsoft. If it's ever unavailable, the computer's own voice is used instead (offline, more robotic), and if even that fails the video is made with captions only, so something is always produced.
- **ElevenLabs** (optional): the most natural voice, and the one used for the example videos. It needs an account and a key.

If they choose the free voice, skip to step 4. If they choose ElevenLabs, explain its plans before they sign up:
- **Free plan**: 10,000 characters a month, about one 5-minute video. Free-plan audio is for non-commercial use only and, if a video is published, its title must include "elevenlabs.io". The free plan must use a personal email address.
- **Starter plan**: $6/month for 30,000 characters (about four videos, enough for most units) and a commercial licence. They can cancel after the unit is done.
- One thing to read themselves: ElevenLabs' use policy (elevenlabs.io/use-policy) restricts use by government entities without authorization. A public school may count; a teacher using it personally is their own call. Don't decide for them.

Then open the keys page in their browser with `LV open https://elevenlabs.io/app/developers/api-keys` and guide them:
1. Sign up or log in.
2. Click **Create Key**. Name it `lesson-videos`.
3. Keep **Restrict Key** on. Set **Text to Speech** to **Access** and, under Administration, **User** to **Access**. Leave the rest on **No Access**.
4. Optional but recommended: put a limit in **Per credit refresh period** (for example 30000) so the key can never spend more.
5. Click **Create Key** and **Copy** the key. It is shown only once.

## 4. Gemini key (optional: music and AI video clips)

Ask whether they want background music and a few short AI-animated clips made from their photos. If not, and they chose the free voice in step 3, skip to step 7: there are no keys to enter. Videos still work.

If yes, explain: this needs a Google account with billing turned on (Google has no free tier for these), a minimum $5 prepayment, and costs about $0.40 per clip and $0.08 per music track, roughly $2–3 for a whole unit. Use a **personal** Google account: school accounts often have AI Studio turned off.

Run `LV open https://aistudio.google.com/api-keys` and guide them:
1. Sign in, accept the terms.
2. Click **Create API key** (let it create a project if asked) and **copy** the key.
3. `LV open https://aistudio.google.com/billing` (or follow the "Set up billing" link) to link a billing account and add the $5 prepayment.
4. `LV open https://aistudio.google.com/spend` and set a **monthly spend cap**, for example $10.

## 5. Paste the keys into the keys file

Run:
```
LV keys
```
It opens a small text file in TextEdit (Mac) or Notepad (Windows). Tell the teacher: paste the ElevenLabs key right after `ELEVENLABS_API_KEY=` and, if they made one, the Gemini key after `GEMINI_API_KEY=`, with no spaces, then **save and close** the file. Wait for them to say they've done it.

If the teacher prefers, they can click **Copy** on the website and you run `LV keys paste elevenlabs` (or `gemini`) instead of using the file.

## 6. Check

```
LV keys check
```
Read the result to them in plain words. "ElevenLabs: not set" is fine: the free Microsoft voice will be used. With a key, ✓ ElevenLabs shows how many characters are left this month. If it says it can't show the remaining credits, narration still works; to see the credits, they can edit the key and set User to Access. Gemini billing is only verified the first time music or a clip is made, because testing it costs money.

## 7. Optional: a project folder

Only if the teacher asks to keep lessons in one project folder (for example a folder they back up or keep in git): `LV init --path "<folder>"`. Lessons then live in `<folder>/lessons/<course>/<unit>/` as text, and finished videos, class materials and paid media in the results folder it prints. Nobody else needs this.

## Connect this computer to slide2video.com (optional)

Only if the teacher was invited to slide2video.com and wants this computer to make videos for lessons they upload
there. Today this works on a Mac (Windows support is on the way). Run `LV pair`. It prints a short code and the website address: the teacher signs in there (on
any computer), opens **Devices** and types the code. Then run `LV worker --status` to confirm the
connection.

Don't run `worker --once` yourself: one lesson step can take an hour or more, far longer than a command may run
here, so it would be stopped halfway. Instead, give the teacher the exact line to paste into the Terminal app
whenever the website says a lesson is waiting for this computer: the `LV` line with the real paths filled in (the
`uv` you used in step 1 and the full path of `lesson-videos.py`, no `${CLAUDE_SKILL_DIR}`), then `worker --once`.
It looks like this, with this computer's paths:

```
uv run "<full path on this computer>/lesson-videos/scripts/lesson-videos.py" worker --once
```

Tell them to open Terminal (Applications ▸ Utilities ▸ Terminal), paste the line, press Return, and leave the
window open until it says what it sent back.

## 8. Done

Summarize: what's ready, which narrator voice will be used (the free Microsoft voice unless they added an ElevenLabs key; `doctor`'s Narration line says which voices work right now), what was skipped, and the cost per video ($0 with the free voice; with ElevenLabs about 5,000–6,000 characters; Gemini about $0.40 per clip plus $0.08 for music). Tell them the next step: open Claude Code in the folder that holds their slide deck and run `/lesson-videos:make`.
