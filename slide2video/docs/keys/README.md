# Getting the optional keys

> **Have Claude Code and the Claude in Chrome extension?** Type `/slide2video:elevenlabs-get-api-key` (or `/slide2video:google-get-api-key`) and Claude opens the pages and clicks through for you; you only sign in and, for Google, add billing.

## Do you need a key?

| You want | You need | Cost |
|---|---|---|
| Narrated videos | Nothing: the free Microsoft voice is used | $0 |
| The most natural voice | An ElevenLabs key | Free plan: about 1 video a month. Starter: $6/month, about 4 videos. |
| Background music and a few AI-animated clips from your photos | A Google Gemini key, with billing | About $0.08 per music track and $0.40 per clip, roughly $2–3 per unit, with a $5 minimum prepayment |

## Step by step

- [ElevenLabs](elevenlabs.md)
- [Google Gemini](google.md)
- [Using your keys in Cowork](keys-file.md)

## Keeping keys safe

- A key works like a password for that service: whoever has it can spend your credits.
- Never paste a key into the chat with Claude. If you did, delete that key on the website and make a new one.
- In Claude Code, keys are saved in `~/.slide2video/keys.env` on your computer (on Windows, `C:\Users\<you>\.slide2video\keys.env`).
