"""The job contract with slide2video.com. Canonical schemas live in slide2video/site-contract/; the site keeps
a pinned copy. contract.json names the plugin version the site is built for; its major is the contract version."""
from __future__ import annotations

from functools import lru_cache

from . import config
from .util import read_json

CONTRACT_DIR = config.PLUGIN_ROOT / "site-contract"
PLUGIN: str = read_json(CONTRACT_DIR / "contract.json")["plugin"]
VERSION: int = int(PLUGIN.split(".")[0])


@lru_cache(maxsize=None)
def _validator(kind: str):
    import jsonschema
    schema = read_json(CONTRACT_DIR / "schemas" / f"{kind}.schema.json")
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def problems(kind: str, obj) -> list[str]:
    """Plain-language schema problems ('' path = the top level); empty when obj is valid."""
    errors = sorted(_validator(kind).iter_errors(obj), key=lambda e: str(list(e.absolute_path)))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(top)'}: {e.message}" for e in errors]
