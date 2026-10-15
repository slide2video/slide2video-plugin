# Job contract notes

The JSON schemas in `schemas/` describe the files that travel between slide2video.com and the worker. Two device
API behaviours are not files and live here:

- `GET /api/device/next` answers a turn (`turn.json`), nothing (204), or `{"stop": true}` once after the teacher
  pressed **Disconnect** for this computer: the worker (`worker --watch`) then exits.
- `GET /api/device/next?start=1` is a watcher's first call: it clears a Disconnect left from while the computer was
  offline, then answers as usual.
