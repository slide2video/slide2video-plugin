# slide2video plugins

| Plugin | What it does |
|---|---|
| [`slide2video`](./slide2video) | Turns a slide deck into narrated, animated videos, one per chapter. Start with its [README](./slide2video/README.md). |

Install in Claude Code:

```
/plugin marketplace add slide2video/slide2video-plugin
/plugin install slide2video@slide2video
```

Used lesson-videos before? The `lesson-videos` plugin no longer connects to slide2video.com, so switch: type the two lines above, then `/plugin uninstall lesson-videos`, and close and reopen Claude Code. Your keys and settings come along; connect this computer again from **Devices** on slide2video.com.

This is plugin version 2 (contract 2). It works with slide2video.com only, where your work is organised as video projects. School is the public style: the one this repo ships, for teachers turning lesson slides into study videos. See the
[plugin README](./slide2video/README.md) for how it works.
