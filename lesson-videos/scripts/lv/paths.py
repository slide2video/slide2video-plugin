"""Where a lesson's files live. Teacher mode (no project, or a folder outside it): one folder per chapter next to
the deck, as `<deck folder>/lesson-videos/_work/chN`. Project mode (a lesson inside the registered project's lessons
folder): text in the project, finished videos and paid media in the results folder, rebuildable files in the cache."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .project import load_project
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


def lesson(path: Path) -> LessonPaths:
    path = Path(path).resolve()
    proj = load_project()
    if proj is not None:
        root = proj.lessons_dir.resolve()
        if path == root:
            raise UserError(f"{path} holds all lessons; give one lesson folder, as {root.name}/<course>/<unit>")
        if path.is_relative_to(root):
            rel = path.relative_to(root)
            unit = proj.results_dir / "lessons" / rel
            return LessonPaths(path, unit / "_source", proj.work_dir / "lessons" / rel, unit, rel.as_posix())
    return LessonPaths(path, path, path, path.parent if path.name == "_work" else path, None)


def chapter(path: Path) -> ChapterPaths:
    path = Path(path).resolve()
    return lesson(path.parent).chapter(path.name)
