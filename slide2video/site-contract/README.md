# Job contract notes

The JSON schemas in `schemas/` describe the files that travel between slide2video.com and the worker. Three device
API behaviours are not files and live here:

- `GET /api/device/next` answers a turn (`turn.json`), nothing (204), or `{"stop": true}` once after the person
  pressed **Disconnect** for this computer: the worker (`worker --watch`) then exits.
- `GET /api/device/next?start=1` is a watcher's first call: it clears a Disconnect left from while the computer was
  offline, then answers as usual.
- `POST /api/device/turns/:id/heartbeat` renews a running turn's lease with `{"progress": "<last line>"}`, plus
  `"fraction"` (0–1) when that line counts through items and, since 2.1.0, `"notes"`: up to 5 short plain sentences
  (at most 200 characters each) that Claude wrote about this turn, oldest first. A website that doesn't know a field
  ignores it.

## Versions

`contract.json` `plugin` is the plugin version slide2video.com is built for. Its major is the contract version
(the schemas' `"contract": {"const": N}`). Every device call sends `X-LV-Plugin: <the plugin's version>`; the
website refuses a different major with a 426 whose `error` the plugin prints as is, and answers every other call
with `X-LV-Latest: <plugin>` so an older plugin can say an update is available.
