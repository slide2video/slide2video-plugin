# lesson-videos

Turn your slide deck into narrated, animated study videos, one per chapter or unit, using Claude Code.

Each video is 4–6 minutes long and includes:
- a friendly narrator who explains each idea in your wording (a free voice, or ElevenLabs if you have an account)
- animated diagrams and your own slide images, revealed in sync with the narration
- captions, "test tip" and "trap" callouts
- a 3-question pause-and-answer quiz and a 30-second recap
- optional background music and a few AI-animated clips made from your photos

Before building anything, Claude also lists places where your slides contradict each other or have typos.

## What you need

- **Claude Code** (the desktop app or the terminal version) and a Claude plan. Download it at https://claude.com/claude-code.
  - **Windows:** install **Git for Windows** first (https://git-scm.com/download/win), then Claude Code.
- **Nothing else is required.** Without any accounts, videos use a free Microsoft voice.
- *(Optional)* **An ElevenLabs account** for the most natural voice. Its free plan covers about one video a month; Starter ($6/month) covers a whole unit.
- *(Optional)* **A Google account with billing** for music and AI clips: about $2–3 for a whole unit, with a $5 minimum prepayment.
- About 1 GB of free disk space and an internet connection that allows downloads. Some school networks block them; a home network works.

## Install (about 10 minutes, once)

1. Open Claude Code and type:
   ```
   /plugin marketplace add DanielLandi/plugins
   /plugin install lesson-videos@daniellandi
   ```
2. Type `/lesson-videos:setup`. Claude installs the free tools it needs and asks which voice you want. With the free voice there's nothing to sign up for. If you choose ElevenLabs or Google, it walks you through creating the keys step by step. It opens a small file for you to paste the keys into, so they never appear in the chat.

## Make videos

1. Put your deck in a folder. PowerPoint (`.pptx`) and PDF work. For Keynote use File → Export To → PowerPoint; for Google Slides use File → Download → Microsoft PowerPoint.
2. Open Claude Code in that folder and type `/lesson-videos:make`.
3. Claude takes you through these steps:
   - It reads the deck and asks a few questions: grade level, how to split it into chapters, and video length.
   - It shows you a content brief and the possible issues it found in your slides.
   - It proposes a plan with costs. **Nothing that costs money happens until you approve it.**
   - It builds chapter 1 and asks for your feedback, then makes the rest.
4. The videos appear in a new `lesson-videos` folder next to your deck. Each one has a captions file (`.vtt`).

If you stop partway, run `/lesson-videos:make` again later and it picks up where it left off.

## Costs

| Item | Cost |
|---|---|
| Narration | Free with the free Microsoft voice. With ElevenLabs: about 5,000–6,000 characters per 5-minute video (free plan: 10,000 a month; Starter: $6/month for 30,000). |
| Music (optional) | About $0.08 per track (Google Lyria). |
| AI clips (optional) | About $0.40 per 8-second clip (Google Veo). |
| Claude | Uses your Claude plan. A whole unit is a lot of work, so on a Pro plan expect to spread it over a few sessions. |

## Good to know

- **Privacy.** Your slides are read by Claude (Anthropic). The narration text goes to Microsoft (free voice) or ElevenLabs, and any photos you choose for AI clips go to Google.
- **The free voice** comes from Microsoft Edge's Read Aloud feature through an unofficial connection. It's fine for classroom use but not for commercial videos. If it ever stops working, your computer's own voice is used instead (more robotic), and if that fails too, the video is made with captions only, so you always get a video.
- **ElevenLabs free-plan rules** (only if you use ElevenLabs). Free-plan audio is for non-commercial use, and a published video's title must include "elevenlabs.io".
  - ElevenLabs' use policy also restricts use by government entities without authorization. Read it (elevenlabs.io/use-policy) and decide whether it applies to you.
- **Images from other sources.** If your deck has pictures from elsewhere on the web, check their licences before posting the videos publicly. Unlisted links or sharing the files directly is safer.
- **Where things are kept.** Your keys and sound effects are stored in `~/.lesson-videos` (on Windows, `C:\Users\<you>\.lesson-videos`). Deleting that folder removes them.

## Troubleshooting

| Problem | Fix |
|---|---|
| "uv not found" | Run `/lesson-videos:setup` again; it installs uv. |
| Downloads fail | Try another network, or ask IT to allow astral.sh, pypi.org, files.pythonhosted.org, github.com and cdn.playwright.dev. |
| "credits used up" | Your ElevenLabs month ran out. Finished scenes are saved; upgrade the plan or wait for next month, then run `/lesson-videos:make` again. |
| "Using this computer's own voice instead" | The free Microsoft voice didn't answer (network or service problem). Run `/lesson-videos:make` again later to switch back; finished scenes are kept. |
| "Gemini refused … billing" | Billing isn't set up, or the spend cap was reached. Videos still work without music and clips. |
| A video looks wrong | Tell Claude what's wrong ("the text overlaps the photo at 1:20"). It fixes that scene and re-renders. |

Made by Daniel Landi. MIT licence. Fonts: Patrick Hand and Nunito (SIL Open Font Licence).
