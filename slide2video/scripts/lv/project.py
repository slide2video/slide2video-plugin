"""The optional project folder. With one registered (`init --path`), a lesson's text (brief, plan, scripts, scenes)
lives in the project, its finished videos and paid media (narration takes, music, clips, chosen images) in the
results folder, and rebuildable files in the OS cache. Without one, everything stays next to the deck."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .util import UserError, read_text, write_text

CONFIG = "config.yaml"


def settings_file() -> Path:
    if value := os.environ.get("LESSON_VIDEOS_SETTINGS"):
        return Path(value).expanduser()
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Preferences"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "lesson-videos" / "settings.json"


def cache_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "lesson-videos"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "lesson-videos" / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "lesson-videos"


def default_results() -> Path:
    return Path.home() / ("Movies" if sys.platform == "darwin" else "Videos") / "Lesson Videos"


@dataclass(frozen=True)
class Project:
    home: Path
    lessons_dir: Path
    results_dir: Path
    work_dir: Path

    @property
    def exists(self) -> bool:
        return self.home.is_dir()


def project_home() -> Path | None:
    if value := os.environ.get("LESSON_VIDEOS_PROJECT"):
        return Path(value).expanduser()
    f = settings_file()
    if not f.is_file():
        return None
    try:
        saved = json.loads(read_text(f)).get("project")
    except (json.JSONDecodeError, AttributeError) as e:
        raise UserError(f"{f}: not valid settings; fix or delete it, then run `init` again") from e
    return Path(saved).expanduser() if saved else None


def _config(home: Path) -> dict:
    f = home / CONFIG
    if not f.is_file():
        return {}
    try:
        raw = yaml.safe_load(read_text(f)) or {}
    except yaml.YAMLError as e:
        raise UserError(f"{f}: not valid YAML ({str(e).splitlines()[0]})") from e
    if not isinstance(raw, dict):
        raise UserError(f"{f}: expected `key: value` lines")
    return raw


def _absolute(home: Path, value) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else home / path


def load_project(home: Path | None = None) -> Project | None:
    home = home or project_home()
    if home is None:
        return None
    home = Path(home).expanduser().resolve()
    raw = _config(home)
    return Project(home=home,
                   lessons_dir=_absolute(home, raw.get("lessons_dir") or "lessons"),
                   results_dir=_absolute(home, raw.get("results_dir") or default_results()),
                   work_dir=_absolute(home, raw.get("work_dir") or cache_dir() / "work"))


def init_project(home: Path) -> tuple[Project, bool]:
    home = Path(home).expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    created = not (home / CONFIG).is_file()
    if created:
        results = "~/" + default_results().relative_to(Path.home()).as_posix()
        write_text(home / CONFIG,
                   "# slide2video project folder. Lessons (text) live in lessons_dir; finished videos, class materials\n"
                   "# and paid media in results_dir/lessons; rebuildable files in the OS cache unless work_dir is set.\n"
                   + yaml.safe_dump({"lessons_dir": "lessons", "results_dir": results}, sort_keys=False))
    p = load_project(home)
    p.lessons_dir.mkdir(parents=True, exist_ok=True)
    write_text(settings_file(), json.dumps({"project": str(home)}))
    return p, created
