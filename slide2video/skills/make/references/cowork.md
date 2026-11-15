# Make lesson videos: in a Cowork cloud session

Part of the make skill (`SKILL.md`, next to this `references/` folder): **LV** and `<folder>` are as it says.

- Run `LV doctor --no-keys` once at the start. It installs what's missing (a browser from npm if the normal download is blocked) and names any website the teacher must allow under Settings → Capabilities → Additional allowed domains; tell them in plain words and that they need to start a new chat afterwards.
- Keys come as an attached **.zip** of their keys file. Run `LV keys load "<path of the attached .zip>"`. **Never open, unzip, read or `cat` it yourself**; `keys load` prints only which keys it found. If the teacher attached the keys file unzipped (a plain text file whose contents you can already see), don't use or repeat the keys: tell them to delete those keys on the websites, make new ones, and attach them zipped next time ([guide](../../../docs/keys/keys-file.md)).
- The deck is among the attached files; use its folder as `<folder>` above. When a chapter is rendered, share the MP4 and its `.vtt` as downloadable files; that's not publishing. A file over 30 MB can't be downloaded: re-render that chapter with `--fps 24` and say so.
