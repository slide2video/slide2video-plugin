---
name: google-get-api-key
description: Use when a teacher wants a Google Gemini API key for lesson-videos music and AI clips and Claude in Chrome is available. Opens Google AI Studio in their Chrome, creates the key, saves it from the clipboard with `keys paste` so it never appears in the chat, then guides billing and sets a spend cap.
---

# Get a Gemini key with Claude in Chrome

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```

**Rules for the whole skill**
- You never type passwords, create accounts, accept terms, or enter payment or card details. The teacher does those in the tab; you wait.
- Ask the teacher before clicking **Create API key** and before saving a spend cap.
- **Key secrecy:** from the moment the new key is shown until the teacher tells you they clicked **Copy** and closed that dialog, take **no screenshots** and **do not read the page** of that tab (no read_page, get_page_text, find or zoom). Then save it with `LV keys paste gemini`.
- Never ask for the key in chat and never read `keys.env`. If the teacher pastes a key into the chat, tell them to delete that key in AI Studio and create a new one.

## 0. Check Chrome

Call `mcp__claude-in-chrome__tabs_context_mcp`. If the Claude in Chrome tools aren't available or don't respond, tell the teacher in one sentence and point them to the illustrated guide `${CLAUDE_SKILL_DIR}/../../docs/keys/google.md`; stop.

## 1. Explain the cost (before anything else)

Music and AI clips need a Google account with billing turned on (there's no free tier for them), a minimum $5 prepayment, and cost about $0.40 per clip and $0.08 per music track: roughly $2–3 for a whole unit. Use a **personal** Google account; school accounts often have AI Studio turned off. Ask whether they want to go ahead.

## 2. Create the key

Open a new tab (`tabs_create_mcp`) at `https://aistudio.google.com/api-keys`. If Google asks them to sign in or accept terms, they do it and say "done"; wait. Ask "Shall I click Create API key?"; on yes, click it and let it create a project if it asks.

After clicking, say: "Your key is on screen now. Click **Copy** next to it, close the dialog, and tell me when you're done. I won't look at the page until then." Take no screenshots and read nothing until they answer. Then run:

```
LV keys paste gemini
```

## 3. Billing (the teacher pays; you only open the page)

Navigate the same tab to `https://aistudio.google.com/billing` (or click the "Set up billing" link). Tell the teacher to link a billing account and add the $5 prepayment themselves, and say "done"; wait.

## 4. Spend cap

Navigate to `https://aistudio.google.com/spend`. Propose a monthly cap of $10. On their yes, set it and save. Tell them the amount you saved.

## 5. Done

Billing is only confirmed the first time music or a clip is made, because testing it costs money. Close the tab you opened. If you came from `/lesson-videos:setup`, continue there.
