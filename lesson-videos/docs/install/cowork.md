# Use it in Cowork (nothing to install)

For a **Claude Pro or Max** plan on claude.ai, in any web browser. Good for school laptops that don't allow installing apps.

The trade-off: each Cowork chat runs on a fresh computer in the cloud, so you attach your slides (and, if you use them, your keys) every time, and download the finished videos before you leave. If you can install apps, [Claude Code](claude-code.md) is smoother.

## 1. Add the plugin (once)

On claude.ai open **Customize** → **Plugins** → **Add** → **Add marketplace** → **Add from a repository**. Type `DanielLandi/plugins` and click **Sync**. Then open **Discover**, find **Lesson videos** and click **Add**.

<!-- screenshot: cowork-add-marketplace.webp -->

## 2. Allow the voice website (once)

Claude's cloud computers can only reach a few package websites unless you allow more. Open **Settings** → **Capabilities** → **Additional allowed domains** and add:

- `speech.platform.bing.com`: the free Microsoft voice. Without it, videos have captions but no voice.
- Only if you use them: `api.elevenlabs.io` (ElevenLabs voice) and `generativelanguage.googleapis.com` (music and AI clips).

<!-- screenshot: cowork-allowed-domains.webp -->

The change applies to **new** chats, not one that's already open.

## 3. Make videos

1. Start a new chat on claude.ai.
2. Attach your deck (`.pptx` or `.pdf`).
3. Using ElevenLabs or Google? Also attach your keys file **as a .zip**. [How to make it](../keys/keys-file.md).
4. Type `/lesson-videos:make`.

The first few minutes go to setting up the cloud computer. Then Claude works the same way as in Claude Code: a few questions, a content brief, a plan with costs for you to approve, chapter 1 for your feedback, then the rest. Each finished chapter appears as a file to download, with its `.vtt` captions.

## Good to know

- **Speed.** Rendering in the cloud is slower than on a laptop: about 8 minutes for a 5-minute video.
- **Download as you go.** When the chat ends, its cloud computer is gone. If you stop partway, start a new chat, attach the same files, and run `/lesson-videos:make` again; already-finished chapters must be downloaded first.
- **Plan limits.** A whole unit is a lot of work; on a Pro plan expect to spread it over a few sessions.

## Troubleshooting

| Problem | Fix |
|---|---|
| "blocked by Claude's network setting … add *website*" | Do step 2 for that website, then start a **new** chat. |
| "No keys found in that file" | Check each key is right after its `=` sign, save, zip the file again and attach the .zip. See [the keys file](../keys/keys-file.md). |
| Claude says it could see your keys | You attached the keys file without zipping it. Delete those keys on the websites, make new ones, and attach them zipped next time. |
| Chromium or renderer errors | Type `/lesson-videos:setup` in the same chat; it reinstalls the renderer. |
| A video is too big to download | Ask Claude to re-render that chapter smaller. |
