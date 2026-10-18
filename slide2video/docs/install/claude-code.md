# Install with Claude Code (recommended)

Install once, and every lesson after that is one command. Your keys are remembered, and the finished videos appear in a folder next to your slides.

## What you need

- **Claude Code** (the desktop app or the terminal version) and a Claude plan. Download it at https://claude.com/claude-code.
  - **Windows:** install **Git for Windows** first (https://git-scm.com/download/win), then Claude Code.
- About 1 GB of free disk space.
- An internet connection that allows downloads. Some school networks block them; a home network works.

## Install the plugin (once)

Pick either way; both end in the same place.

**A. In Claude Code.** Type:

```
/plugin marketplace add slide2video/slide2video-plugin
/plugin install slide2video@slide2video
```

Used lesson-videos before? The `lesson-videos` plugin no longer connects to slide2video.com, so switch: type the two lines above, then `/plugin uninstall lesson-videos`, and close and reopen Claude Code. Your keys and settings come along; connect this computer again from **Devices** on slide2video.com.

**B. On claude.ai.** Open **Customize** → **Plugins** → **Add** → **Add marketplace** → **Add from a repository**, type `slide2video/slide2video-plugin` and click **Sync**. Then find **slide2video** under **Discover** and click **Add**. It appears in Claude Code the next time you open it.

## Set up (about 10 minutes, once)

Type `/slide2video:setup`. Claude installs the free tools it needs (about 500 MB of downloads) and asks which voice you want.

- With the **free voice** there's nothing to sign up for.
- For the most natural voice (ElevenLabs) or for music and AI clips (Google), see [Getting the optional keys](../keys/README.md). If you have the Claude in Chrome extension, Claude can open the pages and click through for you.

## Make videos

1. Put your deck in a folder. PowerPoint (`.pptx`) and PDF work. For Keynote use File → Export To → PowerPoint; for Google Slides use File → Download → Microsoft PowerPoint.
2. Open Claude Code in that folder and type `/slide2video:make`.
3. Claude takes you through these steps:
   - It reads the deck and asks a few questions: grade level, how to split it into chapters, and video length.
   - It shows you a content brief and the possible issues it found in your slides.
   - It proposes a plan with costs. **Nothing that costs money happens until you approve it.**
   - It builds chapter 1 and asks for your feedback, then makes the rest.
4. The videos appear in a new `slide2video` folder next to your deck. Each one has a captions file (`.vtt`).

If you stop partway, run `/slide2video:make` again later and it picks up where it left off.

## Troubleshooting

| Problem | Fix |
|---|---|
| "uv not found" | Run `/slide2video:setup` again; it installs uv. |
| Downloads fail | Try another network, or ask IT to allow astral.sh, pypi.org, files.pythonhosted.org, github.com and cdn.playwright.dev. |
| "credits used up" | Your ElevenLabs month ran out. Finished scenes are saved; upgrade the plan or wait for next month, then run `/slide2video:make` again. |
| "Using this computer's own voice instead" | The free Microsoft voice didn't answer (network or service problem). Run `/slide2video:make` again later to switch back; finished scenes are kept. |
| "Gemini refused … billing" | Billing isn't set up, or the spend cap was reached. Videos still work without music and clips. |
| Claude can't open Chrome | Install the Claude in Chrome extension, or follow the [key guides](../keys/README.md) yourself. |
| A video looks wrong | Tell Claude what's wrong ("the text overlaps the photo at 1:20"). It fixes that scene and re-renders. |

## Keeping lessons in a project folder (optional)

By default everything goes next to your deck. If you'd rather keep all your lessons in one folder (one you back up, or keep in git), run `/slide2video:setup` and ask for a project folder. Then each lesson's text (plan, scripts, scenes) lives in `lessons/<course>/<unit>/` there; finished videos, class materials and the paid parts (narration, music, clips, chosen images) in a results folder (`~/Movies/slide2video` by default; a `~/Movies/Lesson Videos` you already have keeps being used); and rebuildable files in your computer's cache. Nothing changes if you don't.
