"""Styles: what a project asks, checks and writes. Each style is a folder <id>/ with style.json (checked against
styles/style.schema.json) and guide.md. Styles come only from the plugin's own styles/ folder."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config
from .util import UserError, read_json

ROOT = config.PLUGIN_ROOT / "styles"
SCHEMA = ROOT / "style.schema.json"


@dataclass(frozen=True)
class Style:
    id: str
    data: dict
    folder: Path
    origin: str          # always "plugin"

    @property
    def guide(self) -> Path:
        return self.folder / "guide.md"


def _roots() -> list[tuple[Path, str]]:
    return [(ROOT, "plugin")]


def _load(folder: Path, validator) -> dict:
    f = folder / "style.json"
    try:
        data = read_json(f)
    except (OSError, ValueError) as e:
        raise UserError(f"{folder}: no readable style.json ({e}).") from None
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        where = "/".join(map(str, errors[0].path)) or "(top)"
        raise UserError(f"{f}: {where}: {errors[0].message}")
    if data["id"] != folder.name:
        raise UserError(f"{f}: id {data['id']!r} must equal the folder name {folder.name!r}.")
    if not (folder / "guide.md").is_file():
        raise UserError(f"{folder}: guide.md is missing.")
    return data


def installed() -> dict[str, Style]:
    """Every installed style by id, the plugin's first. Any broken style is an error naming its folder."""
    import jsonschema
    validator = jsonschema.Draft202012Validator(read_json(SCHEMA))
    found: dict[str, Style] = {}
    for root, origin in _roots():
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
            data = _load(folder, validator)
            if data["id"] in found:
                raise UserError(f"Two styles have the id {data['id']!r}: {found[data['id']].folder} and {folder}.")
            found[data["id"]] = Style(data["id"], data, folder, origin)
    return found


def get(style_id: str) -> Style:
    found = installed()
    if style_id not in found:
        raise UserError(f"No style {style_id!r}. Installed: {', '.join(found)}.")
    return found[style_id]
