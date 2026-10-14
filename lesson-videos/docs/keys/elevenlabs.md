# ElevenLabs key, step by step

ElevenLabs gives the most natural narration voice. Without it, lesson-videos uses a free Microsoft voice, so this is optional.

## Before you sign up: pick a plan

- **Free plan:** 10,000 characters a month, about one 5-minute video. Free-plan audio is for non-commercial use, a published video's title must include "elevenlabs.io", and the free plan must use a personal email address.
- **Starter:** $6/month for 30,000 characters (about four videos) and a commercial licence. You can cancel after the unit.
- Read ElevenLabs' use policy (https://elevenlabs.io/use-policy) yourself: it restricts use by government entities without authorization. Whether that applies to you is your call.

## Make the key

1. Open https://elevenlabs.io/app/settings/api-keys and sign up or sign in.

   <!-- screenshot: elevenlabs-keys-page.webp -->

2. Click **Create API Key**.
3. Name it `lesson-videos`.
4. Under permissions, turn on **Text to Speech** (access) and **User** (read). Leave the rest off.
5. Optional but recommended: set a **credit quota** (for example 30,000) so the key can never spend more.

   <!-- screenshot: elevenlabs-create-dialog.webp -->

6. Click **Create**, then **Copy**. The key is shown only once.

## Save it

- **In Claude Code:** right after clicking Copy, ask Claude to "save my ElevenLabs key from the clipboard". It runs `keys paste elevenlabs`, which saves the key without showing it and clears your clipboard. Or run `/lesson-videos:setup`, which opens a small file to paste the key into.
- **In Cowork:** paste it into your keys file and attach it zipped. See [the keys file](keys-file.md).
