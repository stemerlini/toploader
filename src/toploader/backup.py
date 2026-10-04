"""Back the collection up to git when the app closes.

Only the files in data/ are committed (never code changes that happen to be
in the working tree), then the branch is pushed. Every step is best-effort:
a missing repository, no network or a slow remote must never stop the app
from closing, so failures just come back as a status line.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

DATA_FILES = ["data/collection.db", "data/config.json"]
PUSH_TIMEOUT = 20  # seconds


def _git(root: Path, *args: str, timeout: float = 10) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # never ask for a password
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def backup(root: Path, message: str) -> str:
    """Commit changed collection files and push. Returns a one-line status."""
    try:
        top = _git(root, "rev-parse", "--show-toplevel")
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != root.resolve():
            return "Backup skipped: the data folder is not a git repository."

        files = [f for f in DATA_FILES if (root / f).exists()]
        changed = _git(root, "status", "--porcelain", "--", *files).stdout.strip()
        if changed:
            _git(root, "add", "--", *files)
            # A pathspec commit records only these files, whatever else is staged.
            result = _git(root, "commit", "-q", "-m", message, "--", *files)
            if result.returncode != 0:
                return f"Backup failed to commit: {result.stderr.strip() or result.stdout.strip()}"

        ahead = _git(root, "rev-list", "--count", "@{upstream}..HEAD")
        if ahead.returncode != 0:
            return ("Collection committed locally (no remote to push to)." if changed
                    else "Collection unchanged.")
        if ahead.stdout.strip() == "0":
            return "Collection unchanged, GitHub is up to date." if not changed else \
                "Collection committed."

        try:
            push = _git(root, "push", "-q", timeout=PUSH_TIMEOUT)
        except subprocess.TimeoutExpired:
            return "Collection committed locally; push timed out, it will go up next time."
        if push.returncode != 0:
            return "Collection committed locally; push failed (offline?), it will go up next time."
        return "Collection backed up to GitHub." if changed else \
            "Earlier collection changes pushed to GitHub."
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Backup skipped: {exc}"
