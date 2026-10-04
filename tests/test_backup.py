"""Backing the collection up to git when the app closes."""

import subprocess

import pytest

from toploader.backup import backup


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A project folder with a collection, cloned from a bare 'GitHub' remote."""
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(remote), str(work))
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.com")
    (work / "data").mkdir()
    (work / "data" / "collection.db").write_bytes(b"v1")
    (work / "data" / "config.json").write_text("{}")
    (work / "app.py").write_text("code v1")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "initial")
    git(work, "push", "-q", "-u", "origin", "main")
    return work, remote


def test_changed_collection_is_committed_and_pushed(repo):
    work, remote = repo
    (work / "data" / "collection.db").write_bytes(b"v2")
    assert backup(work, "Collection: 3 cards") == "Collection backed up to GitHub."
    assert git(remote, "log", "-1", "--format=%s") == "Collection: 3 cards"
    assert git(remote, "show", "main:data/collection.db") == "v2"


def test_nothing_to_do_when_unchanged(repo):
    work, remote = repo
    assert backup(work, "msg") == "Collection unchanged, GitHub is up to date."
    assert git(remote, "rev-list", "--count", "main") == "1"


def test_code_changes_are_never_included(repo):
    work, remote = repo
    (work / "app.py").write_text("code v2, work in progress")
    git(work, "add", "app.py")  # even if staged
    (work / "data" / "collection.db").write_bytes(b"v2")
    backup(work, "msg")
    assert git(remote, "show", "main:app.py") == "code v1"
    assert git(work, "status", "--porcelain") == "M  app.py"  # still staged, untouched


def test_push_failure_keeps_a_local_commit_that_goes_up_later(repo):
    work, remote = repo
    git(work, "remote", "set-url", "origin", str(work.parent / "missing.git"))
    (work / "data" / "collection.db").write_bytes(b"v2")
    status = backup(work, "offline change")
    assert "committed locally" in status and "push failed" in status
    assert git(work, "log", "-1", "--format=%s") == "offline change"

    git(work, "remote", "set-url", "origin", str(remote))  # back online
    assert backup(work, "msg") == "Earlier collection changes pushed to GitHub."
    assert git(remote, "show", "main:data/collection.db") == "v2"


def test_not_a_repository(tmp_path):
    (tmp_path / "data").mkdir()
    assert backup(tmp_path, "msg").startswith("Backup skipped")
