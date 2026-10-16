---
name: serve
description: Use when the teacher wants this computer to make the videos for lessons they upload to slide2video.com ("start making videos", "serve", "connect to the website and keep working"), or asks whether it's working, to stop it, or whether it can start by itself. Starts the slide2video worker in the background, keeps the computer awake while it runs, and stops when asked or when Disconnect is pressed on the website.
---

# slide2video: make videos for slide2video.com

You are helping a teacher who may never have used a terminal. Explain in one or two plain sentences, do the
technical work yourself.

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/slide2video.py"
```

If that path doesn't exist (in some claude.ai sessions `${CLAUDE_SKILL_DIR}` comes through empty), the plugin is
under `/root/.claude/plugins/synced/`: use the `slide2video/scripts/slide2video.py` you find there.

**pro.slide2video.com (Daniel only, before launch):** if the person typed `pro` after the command
(`/slide2video:serve pro`), add `--site pro` to every `LV pair` and `LV worker` command below, and say
pro.slide2video.com wherever this skill says slide2video.com. Never suggest it otherwise.

## 1. Check the connection

Run `LV worker --status`. If it says "Connected to …", go on. If this computer isn't connected, offer to connect it
now (the same as step 8 of `/slide2video:setup`: run `LV pair` with the Bash tool's `run_in_background`, read the
code line from its output, give the teacher the address and code, then check `LV worker --status` again).
`LV worker --status` also names the plugin version; if it says a newer one is available, mention it (it isn't urgent).

## 2. Start

Start `LV worker --watch` with the Bash tool's `run_in_background`. It runs until stopped, so never run it in the
foreground. Read the first lines of its output:
- "Making videos for …": it started.
- "already making videos": it is already running in another window; tell the teacher, nothing else to do.
- anything else: tell the teacher in plain words and do what the message says.

Then tell the teacher:
- This computer now makes the videos for lessons on slide2video.com, one step after another.
- **Keep this Claude Code window open.** The screen may turn off, but the computer won't go to sleep while this runs.
  On a laptop, keep the lid open (or a display plugged in): a closed lid still puts it to sleep.
- The website's **Devices** page shows this computer as Online.
- To stop: say "stop" here, or press **Disconnect** on the Devices page.

## 3. While it runs

- **"Is it working?"**: read the last lines of the background task's output and say in plain words what it's doing
  (waiting for lessons, working on a lesson, or the last thing it sent back).
- **"Stop"**: stop the background Bash task and confirm it has ended. Starting again is running this skill again.
  First read its last line: if it is "Working on …", a step is in progress. Tell the teacher that stopping now
  means that step starts over from the beginning when they start again, and that **Disconnect** on the website's
  Devices page instead lets the step finish first, then stops. Stop only once they have chosen.
- If the background task ends by itself, read its last lines: "Disconnected from the website" means someone pressed
  Disconnect; a "connect" message means the pairing was removed (offer step 1); a "needs" or "Update the
  slide2video plugin" message means: run `/plugin update slide2video`, then close and reopen Claude Code, then
  run this skill again (the worker keeps its old code until Claude Code is reopened); "hasn't caught up" means the
  website isn't updated yet: nothing to do on this computer, try again later.
- A line "A newer slide2video (…) is available" is only advice: the worker keeps making videos. Tell the teacher
  in plain words and suggest updating (the same three steps) once nothing is being worked on, since reopening Claude Code stops the worker.

## Start automatically

If the teacher asks whether this can start by itself when the computer starts: it is not built in, on purpose.
Starting on its own, the computer would make videos with nobody watching, it would stay awake from every start-up,
and it isn't yet known whether Claude Code started in the background by the system can use the Claude subscription
without asking to sign in. The supported way is to open Claude Code and run `/slide2video:serve`.

Only if the teacher asks for it anyway, you can set it up for this one computer: on a Mac a LaunchAgent in
`~/Library/LaunchAgents/` that runs the same `worker --watch` command with full paths (the `uv` path from
`which uv` and the full path of `slide2video.py`) at log-in; on Windows a Task Scheduler task at log-on. Test it
once, show the teacher where it is and how to remove it. Never set it up unasked.
