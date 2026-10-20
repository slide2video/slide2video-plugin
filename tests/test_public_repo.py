"""The repo is public: no tracked text file may contain a term from the maintainer's local, git-ignored
`.private-terms.txt` (one term per line, `#` comments, matched case-insensitively as whole words)."""
import os
import re
import subprocess
import warnings

import pytest

from conftest import REPO

TERMS_FILE = REPO / ".private-terms.txt"


def _terms():
    if not TERMS_FILE.is_file():
        if os.environ.get("S2V_PUBLISH"):
            pytest.fail(f"{TERMS_FILE.name} is missing: the publish check needs the denylist")
        warnings.warn(f"{TERMS_FILE.name} missing: the denylist scan is skipped")
        return []
    lines = (t.strip().lower() for t in TERMS_FILE.read_text(encoding="utf-8").splitlines())
    return [t for t in lines if t and not t.startswith("#")]


def _tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout
    return [REPO / p for p in out.decode("utf-8").split("\0") if p]


def _text(path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _found(term, low):
    """The term as a whole word: not preceded or followed by a letter or digit."""
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", low) is not None


def _hits(files, terms):
    hits = []
    for f in files:
        text = _text(f)
        if text is None:
            continue
        low = text.lower()
        name = f.relative_to(REPO) if f.is_relative_to(REPO) else f.name
        hits += [f"{name}: {t}" for t in terms if _found(t, low)]
    return hits


def test_no_private_terms_in_tracked_files():
    assert _hits(_tracked(), _terms()) == []


def test_this_test_is_scanned():
    names = {f.name for f in _tracked()}
    assert {"test_public_repo.py", "AGENTS.md", "cli.py"} <= names


def test_scan_catches_a_planted_term(tmp_path):
    terms = _terms()
    if not terms:
        pytest.skip("needs the local denylist")
    planted = tmp_path / "planted.md"
    planted.write_text(f"a line with {terms[0].upper()} in it\n", encoding="utf-8")
    assert _hits([planted], terms)


def test_matching_is_on_whole_words(tmp_path):
    term = "zq term"  # made up: no real term is spelled here
    near = tmp_path / "near.md"
    near.write_text("azq term and zq termz here\n", encoding="utf-8")  # only inside longer words
    real = tmp_path / "real.md"
    real.write_text("a ZQ TERM, really\n", encoding="utf-8")
    assert _hits([near], [term]) == []
    assert _hits([real], [term])
