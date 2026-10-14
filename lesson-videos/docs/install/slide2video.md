# Connect a computer to slide2video.com

slide2video.com lets you upload a slide deck from any computer, for example a school laptop, answer Claude's
questions there, and watch the finished videos there. The videos themselves are made on **your own computer at
home**, by Claude Code signed in to **your own** Claude account. The website never runs Claude.

slide2video.com is invite-only. If you haven't been invited, use [Claude Code](claude-code.md) or
[Cowork](cowork.md) instead.

## What you need

- An invitation to slide2video.com (you sign in there with an emailed code).
- A computer that stays at home and makes the videos. Today that's a **Mac**; Windows support is on the way.
- **Claude Code** on that computer, signed in to your own Claude account (any paid plan).
- About 1 GB of free disk space, and about 15 minutes the first time.

## 1. Install Claude Code and the plugin (once)

Follow "What you need" and "Install the plugin" in [Install with Claude Code](claude-code.md): install
Claude Code, sign in, then type:

```
/plugin marketplace add DanielLandi/plugins
/plugin install lesson-videos@daniellandi
```

## 2. Set up and connect this computer (once)

Type `/lesson-videos:setup`. Claude installs the free tools it needs (about 10 minutes) and asks which voice you
want. At the end it asks whether to **connect this computer to slide2video.com**: say yes.

It shows a short code, like `KQ7-4M2`, valid for 10 minutes. On any computer:

1. Sign in at https://slide2video.com.
2. Open **Devices**.
3. Type the code and click **Connect**.

Only type a code that your own computer is showing right now. Claude then confirms the connection, and the computer
appears under **Devices** with the time it was last seen.

Claude also gives you a line to paste into the **Terminal** app, which looks like this:

```
uv run "<your home folder>/.claude/plugins/…/lesson-videos/scripts/lesson-videos.py" worker --once
```

Keep it somewhere handy (a note works well). You use it in step 3.

## 3. Make videos

1. On slide2video.com, click **New lesson**, give it a title, add your deck (`.pptx` or `.pdf`) and any extra
   files, tick the box confirming there's no student information, and click **Upload and start**.
2. The lesson says **Waiting for your computer**. On your home computer, open Terminal (Applications ▸ Utilities ▸
   Terminal), paste the line from step 2, and press Return. Claude works on one step, then stops and says what it
   sent back. Leave the window open until then.
3. Back on the website, the lesson shows Claude's questions, then the plan with its cost, then each chapter to
   watch. After each answer, approval or piece of feedback, run the line again on your home computer.
4. Download each chapter's video and captions from the lesson page.

Running by itself in the background, so you don't have to paste the line each time, is coming next.

## Good to know

- **Your Claude account only.** Connect only computers signed in to your own Claude account, and don't connect
  your computer to someone else's slide2video account. Claude subscriptions are personal under
  [Anthropic's Consumer Terms](https://www.anthropic.com/legal/consumer-terms).
- **Never student information** in what you upload: no student names, photos of students, student work or grades.
- **Your lessons go only to your computers.** A lesson stays on the computer that started it; your other computers
  and other teachers' computers never see it.
- **Deleting** a lesson on the website removes it there at once, and from your computer the next time the line runs.

## Troubleshooting

| What you see | What to do |
|---|---|
| "The code expired before it was entered" | Run `/lesson-videos:setup` again and choose to connect; you get a new code. |
| "This computer isn't connected to slide2video.com" | It was removed under **Devices**, or never connected. Connect it again (step 2). |
| "Update the lesson-videos plugin on this computer" | In Claude Code, type `/plugin update lesson-videos`, then run the line again. |
| "Your Claude plan's usage limit was reached" | Nothing to do: the lesson continues by itself after the limit resets, the next time the line runs. |
| The lesson keeps saying **Waiting for your computer** | Run the line on your home computer. If it was asleep or offline mid-step, run it again; the step starts over. |
| "The device this lesson was on was removed" | That computer was removed under **Devices**, so the lesson can't continue. Delete it and upload the deck again. |
| Claude Code isn't installed on this computer | Install it (step 1) and sign in, then run the line again. |
