"""Where a lesson's files live. Teacher mode (no project, or a folder outside it): one folder per chapter next to
the deck, as `<deck folder>/slide2video/_work/chN`. Project mode (a lesson inside the registered project's lessons
folder): text in the project, finished videos and paid media in the results folder, rebuildable files in the cache."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .project import CONFIG, _config, load_project
from .util import UserError


@dataclass(frozen=True)
class ChapterPaths:
    code: Path      # script.json, scenes.js
    sources: Path   # assets/, and the base for relative paths in script.json (e.g. "../music/bed.mp3")
    build: Path     # timing.js, narration.mp3, stills, render parts, logs
    voice: Path     # narration takes: paid, so never in the cache
    out: Path       # the finished MP4 and .vtt
    lesson_id: str | None

    @property
    def assets(self) -> Path:
        return self.sources / "assets"

    @property
    def name(self) -> str:
        return self.code.name

    @property
    def project(self) -> bool:
        return self.lesson_id is not None


@dataclass(frozen=True)
class LessonPaths:
    code: Path      # brief.md, plan.md, chN/
    sources: Path   # music/, clips/, chN/assets, chN/voice
    work: Path      # deck/ (what ingest extracts)
    out: Path       # finished videos
    lesson_id: str | None

    @property
    def project(self) -> bool:
        return self.lesson_id is not None

    def chapter(self, name: str) -> ChapterPaths:
        if not self.project:
            ch = self.code / name
            out = self.out if self.code.name == "_work" else ch / "out"
            return ChapterPaths(ch, ch, ch / "build", ch / "build" / "voice", out, None)
        src = self.sources / name
        return ChapterPaths(self.code / name, src, self.work / name, src / "voice", self.out, self.lesson_id)


def _below(path: Path, root: Path) -> Path | None:
    """The part of path under root, comparing folders the way the disk does (a path typed in another case on a
    case-insensitive disk, or reached through a link, is still inside); None when it is not under root."""
    if path.is_relative_to(root):
        return path.relative_to(root)
    if not root.exists():
        return None
    for folder in (path, *path.parents):
        if folder.exists() and os.path.samefile(folder, root):
            return path.relative_to(folder)
    return None


def _unregistered_project(path: Path) -> Path | None:
    """A project folder (config.yaml with lessons_dir) whose lessons folder holds path, found by walking up."""
    for folder in path.parents:
        if (folder / CONFIG).is_file():
            try:
                lessons = _config(folder).get("lessons_dir")
            except UserError:  # someone else's config.yaml: not ours to judge
                continue
            if lessons and _below(path, (folder / str(lessons)).resolve()) is not None:
                return folder
    return None


def lesson(path: Path) -> LessonPaths:
    path = Path(path).resolve()
    proj = load_project()
    if proj is not None:
        root = proj.lessons_dir.resolve()
        rel = _below(path, root)
        if rel is not None and rel == Path("."):
            raise UserError(f"{path} holds all lessons; give one lesson folder, as {root.name}/<course>/<unit>")
        if rel is not None:
            unit = proj.results_dir / "lessons" / rel
            return LessonPaths(path, unit / "_source", proj.work_dir / "lessons" / rel, unit, rel.as_posix())
    other = _unregistered_project(path)
    if other is not None:
        using = f"the one in use is {proj.home}" if proj is not None else "no project folder is registered"
        raise UserError(f"{path} is a lesson in the project folder {other}, but {using}. Run `init --path \"{other}\"` "
                        "first, so narration and media go to that project's folders (nothing was written).")
    return LessonPaths(path, path, path, path.parent if path.name == "_work" else path, None)


def chapter(path: Path) -> ChapterPaths:
    path = Path(path).resolve()
    return lesson(path.parent).chapter(path.name)
