# Your keys file (for Cowork)

In Cowork every chat starts on a fresh cloud computer, so your keys come along as a small file you attach. **Always attach it zipped:** claude.ai shows the text of an attached text file to Claude, but leaves a .zip closed, and lesson-videos opens it without ever showing your keys.

## Make it once

1. Download [the empty keys file](../keys-template.txt) (on the GitHub page, click the **Download raw file** button).
2. Open it in TextEdit (Mac) or Notepad (Windows). On a Mac, if it opens with formatting, choose **Format → Make Plain Text**.
3. Paste each key right after its `=` sign, with no spaces:
   ```
   ELEVENLABS_API_KEY=sk_...
   GEMINI_API_KEY=AIza...
   ```
   Leave a line empty after `=` if you don't have that key.
4. Save it as `lesson-videos-keys.txt`.
5. Zip it:
   - **Mac:** right-click the file → **Compress**. You get `lesson-videos-keys.txt.zip`.
   - **Windows:** right-click the file → **Send to** → **Compressed (zipped) folder**.

## Use it

Attach the **.zip** to each Cowork chat along with your deck. Claude runs `keys load` on it, which saves the keys inside the cloud computer and says only which keys it found.

## Keep it private

- Store it somewhere only you can open. Don't email it or put it in a shared folder.
- If it ever leaks, or you attached it without zipping it, delete those keys on the [ElevenLabs](elevenlabs.md) and [Google](google.md) websites and make new ones.
