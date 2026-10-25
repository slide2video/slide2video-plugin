"""The job contract with slide2video.com. Canonical schemas live in slide2video/site-contract/; the site keeps
a pinned copy. contract.json names the plugin version the site is built for; its major is the contract version."""
from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache

from . import config
from .util import read_json

CONTRACT_DIR = config.PLUGIN_ROOT / "site-contract"
PLUGIN: str = read_json(CONTRACT_DIR / "contract.json")["plugin"]
VERSION: int = int(PLUGIN.split(".")[0])


_DATE_TIME = re.compile(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})")


def _format_checker():
    """jsonschema's format checks, with `date-time` checked here: jsonschema checks it only when the optional
    rfc3339-validator package is installed, and the website always checks it (RFC 3339, an offset required)."""
    import jsonschema
    fc = jsonschema.FormatChecker()

    @fc.checks("date-time", raises=ValueError)
    def date_time(v) -> bool:
        if not isinstance(v, str):
            return True   # the type keyword's job
        if not _DATE_TIME.fullmatch(v):
            raise ValueError(f"{v!r} isn't an RFC 3339 date-time")
        dt.datetime.fromisoformat(v.upper().replace("Z", "+00:00"))   # a real date and time
        return True
    return fc


@lru_cache(maxsize=None)
def _validator(kind: str):
    import jsonschema
    schema = read_json(CONTRACT_DIR / "schemas" / f"{kind}.schema.json")
    return jsonschema.Draft202012Validator(schema, format_checker=_format_checker())


def problems(kind: str, obj) -> list[str]:
    """Plain-language schema problems ('' path = the top level); empty when obj is valid."""
    errors = sorted(_validator(kind).iter_errors(obj), key=lambda e: str(list(e.absolute_path)))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(top)'}: {e.message}" for e in errors]
