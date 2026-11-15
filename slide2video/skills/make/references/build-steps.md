# Make lesson videos: steps 5–8 (music and clips, chapters, wrap-up)

Part of the make skill (`SKILL.md`, next to this `references/` folder): **LV**, **WORK**, the style and the ground rules are as it says. Steps 0–4 are in `plan-steps.md`.

## 5. Music and clips (only if approved and a Gemini key is set)

- Music: `LV music "WORK" --prompt "<the style's music prompt>"`. If it fails with a billing message, tell the teacher in one line and continue without music.
- Each clip: copy the source photo path from `WORK/deck/media/`, then `LV clip "<photo>" --work "WORK" --name <short-name> --prompt "<realistic footage of this exact photo: name the subject and keep it exactly as it is; only gentle natural motion (water, leaves, clouds, light); no text, no people added, no new objects>"`. A clip is 10 seconds. Look at `WORK/clips/<name>-strip.jpg`: if the subject changes into something else partway, or something appears that isn't in the photo, note how many seconds are usable and use `--max <seconds × 24>` below. The model may move the camera its own way (it often pulls back slowly); that's fine.

## 6. Reference chapter (chapter 1), then stop for feedback

Follow the workflow in `guide.md` for chapter 1 in `WORK/ch1/`, starting with `LV chapter "WORK" 1`. It writes the chapter's slides (word for word, with their charts, speaker notes and images, and any slide its outline mentions) and the brief without the other chapters' sections to the file it prints, and the chapter's pictures to the contact sheets it prints. Build from those instead of the whole `slides.md`, `brief.md` and `contact-*.jpg`; open `slides.md` only for a slide the chapter needs that isn't in that file.
1. Write `script.json` (narration per scene; `"music": "../music/bed.mp3"` only if music exists).
2. `LV narrate "WORK/ch1"`. It prints which voice it used. If it had to fall back (for example the free Microsoft voice was unavailable, or ElevenLabs credits ran out), tell the teacher in one line; running `narrate` again later switches back, and finished takes are kept.
3. Copy each image you use with `LV asset "WORK/deck/media/<file>" "WORK/ch1/assets/<name>.jpg"` (in a project folder, the target is in the `assets:` folder from `LV where "WORK/ch1"`) (it straightens, downscales to 1600 px and converts transparent PNGs; use `.png` as the target to keep transparency); for clips run `LV frames "WORK/clips/<name>.mp4" "WORK/ch1/assets/clip_<name>" [--max N]` (same `assets:` folder in a project; clips are in the `clips/` folder that `clip` printed).
4. Write `scenes.js`. Every chart, table and number from the deck appears unchanged: follow "Numbers from the deck" in `guide.md` and do its check.
5. `LV stills "WORK/ch1" <one time per scene>` and look at the `stills.jpg` it prints. Fix overlaps, text running off cards, things hidden behind captions, empty-looking scenes, and every `cue miss` warning. Repeat until clean (2–3 rounds is normal).
6. `LV render "WORK/ch1"`. Run `narrate` and `render` in the foreground with the Bash tool's longest timeout (10 minutes), never in the background. Each returns within about 4 minutes: if it ends with `not finished` (exit code 3), run the same command again, as often as it says, until it finishes; what it already made is kept.
7. Verify: `render` prints the video length next to the narration length (they should match), and saves four frames of the finished video to the `final.jpg` it prints; look at them.

Then **stop**. Tell the teacher where the video is (the path `render` printed) and ask about tone, pace, reading level, voice and look. Apply their feedback to chapter 1 (re-narrating only changed scenes is cheap) before moving on, and write the agreed style notes at the top of `plan.md` so later chapters (and later sessions) follow them.

## 7. Remaining chapters

Default: one chapter at a time, same steps as 6 (`LV chapter "WORK" <N>`, then 6.1–6.7), checking in briefly after each. If the teacher asks for speed, you may hand chapters to parallel helper agents; give each the exact **LV** command line (with the real plugin path, since helpers don't get it substituted), the paths to `guide.md` and the style's guide, the chapter file and contact sheets `LV chapter "WORK" <N>` printed for it, `plan.md` (with the style notes), its own `WORK/chN/` folder, and the finished `WORK/ch1/` as the reference. Tell the teacher this uses much more of their Claude plan.

Between chapters, `LV status "WORK"` shows what's left. If the session ends, the next `/slide2video:make` resumes from step 0.

## 8. Wrap up

Write `README.md` in the folder with the finished videos: a table of the videos with their lengths, one line on what each covers, and these notes:
- Narration: say which voice was used: an AI voice from ElevenLabs, the free Microsoft Edge voice (an unofficial Microsoft service; for classroom, non-commercial use), the computer's built-in voice, or captions only. Music and clips, if any, are AI-generated (Google).
- If the deck contains photos or diagrams from other sources, check their licences before posting the videos publicly; keeping them unlisted or sharing the files directly is safer.
- If ElevenLabs' free plan was used, a published video's title must include "elevenlabs.io".
- Each `.vtt` file holds the captions (they are also burned into the video).

Add any notes the style's guide lists for the wrap-up.

Tell the teacher the videos are done and where they are.
