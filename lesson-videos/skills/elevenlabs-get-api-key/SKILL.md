---
name: elevenlabs-get-api-key
description: Use when a teacher wants an ElevenLabs API key for lesson-videos narration and Claude in Chrome is available. Opens the ElevenLabs pages in their Chrome, fills in the key's name and permissions, and saves the key from the clipboard with `keys paste` so it never appears in the chat.
---

# Get an ElevenLabs key with Claude in Chrome

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```

**Rules for the whole skill**
- You never type passwords, create accounts, accept terms, or enter payment details. The teacher does those in the tab; you wait.
- Ask the teacher before clicking the final **Create** button.
- **Key secrecy:** from the moment the new key is shown until the teacher tells you they clicked **Copy** and closed that dialog, take **no screenshots** and **do not read the page** of that tab (no read_page, get_page_text, find or zoom). Then save it with `LV keys paste elevenlabs`.
- Never ask for the key in chat and never read `keys.env`. If the teacher pastes a key into the chat, tell them to delete that key on the website and create a new one.

## 0. Check Chrome

Call `mcp__claude-in-chrome__tabs_context_mcp`. If the Claude in Chrome tools aren't available or don't respond, tell the teacher in one sentence and point them to the illustrated guide `${CLAUDE_SKILL_DIR}/../../docs/keys/elevenlabs.md`; stop.

## 1. Explain the plans (before they sign up)

- **Free plan:** 10,000 characters a month, about one 5-minute video. Free-plan audio is for non-commercial use, a published video's title must include "elevenlabs.io", and the free plan must use a personal email address.
- **Starter:** $6/month for 30,000 characters (about four videos) and a commercial licence; they can cancel after the unit.
- They should read ElevenLabs' use policy (elevenlabs.io/use-policy) themselves: it restricts use by government entities without authorization. Don't decide for them.

## 2. Open the keys page

Open a new tab (`tabs_create_mcp`) at `https://elevenlabs.io/app/settings/api-keys`. If it shows a sign-in or sign-up page, tell the teacher to sign in or sign up in that tab and say "done"; wait.

## 3. Fill in the key

Click **Create API Key**. Set the name to `lesson-videos`. Under permissions turn on **Text to Speech** (access) and **User** (read); leave everything else off. Suggest a credit quota (30,000) so the key can never spend more; set it if they agree.

Tell the teacher what you filled in and ask: "Shall I click Create?" Click only after a yes.

## 4. Copy, then save

After clicking Create, say: "Your key is on screen now. Click **Copy** next to it, close the dialog, and tell me when you're done. I won't look at the page until then." Take no screenshots and read nothing until they answer.

Then run:

```
LV keys paste elevenlabs
```

It saves the key from the clipboard, clears the clipboard, tests the key and prints only its last four characters and the credits left. If it says the clipboard doesn't hold a key, ask them to click Copy again and re-run it.

## 5. Done

Tell them the key works and how many characters are left, then close the tab you opened. If you came from `/lesson-videos:setup`, continue there.
