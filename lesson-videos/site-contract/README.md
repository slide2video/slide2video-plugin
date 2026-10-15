# Job contract notes

The JSON schemas in `schemas/` describe the files that travel between slide2video.com and the worker. Two device
API behaviours are not files and live here:

- `GET /api/device/next` answers a turn (`turn.json`), nothing (204), or `{"stop": true}` once after the teacher
  pressed **Disconnect** for this computer: the worker (`worker --watch`) then exits.
- `GET /api/device/next?start=1` is a watcher's first call: it clears a Disconnect left from while the computer was
  offline, then answers as usual.

## Versions

`contract.json` `plugin` is the plugin version slide2video.com is built for. Its major is the contract version
(the schemas' `"contract": {"const": N}`). Every device call sends `X-LV-Plugin: <the plugin's version>`; the
website refuses a different major with a 426 whose `error` the plugin prints as is, and answers every other call
with `X-LV-Latest: <plugin>` so an older plugin can say an update is available.
