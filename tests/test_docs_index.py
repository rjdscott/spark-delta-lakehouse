"""Checks for the docs index generator.

The generator is the thing standing between the index tables and drift, so it
gets the one test the scaffold ships with.
"""

from __future__ import annotations

import datetime as dt

import docs_index


def write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"))


def test_adr_row_and_dangling_supersede(tmp_path):
    write(
        tmp_path / "adr" / "0001-pick-a-database.md",
        """
# 0001. Pick a database

- **Status:** Superseded by [0002](0002-pick-another.md)
""",
    )
    block, problems = docs_index.render("adr", tmp_path)

    assert "| [0001](0001-pick-a-database.md) | Pick a database |" in block
    assert problems == ["adr/0001-pick-a-database.md: superseded by 0002, which does not exist"]


def test_duplicate_adr_numbers_are_an_error(tmp_path):
    for slug in ("0007-one.md", "0007-two.md"):
        write(tmp_path / "adr" / slug, "# 0007. Something\n\n- **Status:** Accepted\n")

    _, problems = docs_index.render("adr", tmp_path)

    assert problems == ["ADR number 0007 used twice: 0007-one.md, 0007-two.md"]


def test_empty_surface_renders_placeholder(tmp_path):
    (tmp_path / "runbooks").mkdir(parents=True)

    block, problems = docs_index.render("runbooks", tmp_path)

    assert block.splitlines()[1] == docs_index.EMPTY
    assert problems == []


def test_runbook_row_carries_last_verified(tmp_path):
    write(
        tmp_path / "runbooks" / "restore-a-backup.md",
        "# Restore a backup\n\n- **Last verified:** 2026-08-07 against abc1234\n",
    )
    block, _ = docs_index.render("runbooks", tmp_path)

    assert (
        "| [restore-a-backup](restore-a-backup.md) | Restore a backup "
        "| 2026-08-07 against abc1234 |"
    ) in block


def test_silent_in_progress_plan_is_flagged(tmp_path):
    old = dt.date.today() - dt.timedelta(days=docs_index.STALE_DAYS + 1)
    write(
        tmp_path / "plans" / "2026-01-01-migrate" / "README.md",
        f"# Migrate the warehouse\n\n- **Status:** 🟡 In progress\n\n{old.isoformat()} started\n",
    )
    _, problems = docs_index.render("plans", tmp_path)

    assert len(problems) == 1
    assert "silent since" in problems[0]


def test_recently_touched_plan_is_not_flagged(tmp_path):
    fresh = dt.date.today() - dt.timedelta(days=1)
    write(
        tmp_path / "plans" / "2026-01-01-migrate" / "README.md",
        "# Migrate the warehouse\n\n- **Status:** 🟡 In progress\n",
    )
    write(
        tmp_path / "plans" / "2026-01-01-migrate" / "phase-01-cut-over.md",
        f"# Phase 01\n\n## Progress log\n\n{fresh.isoformat()} still going\n",
    )
    block, problems = docs_index.render("plans", tmp_path)

    assert problems == []
    assert fresh.isoformat() in block


def test_target_date_in_the_future_is_not_activity(tmp_path):
    """A plan naming a cutover date must not report it as a sign of life."""
    old = dt.date.today() - dt.timedelta(days=docs_index.STALE_DAYS + 1)
    write(
        tmp_path / "plans" / "2020-01-01-migrate" / "README.md",
        f"# Migrate\n\n- **Status:** 🟡 In progress\n\n{old.isoformat()} started. "
        f"Target 2099-12-31.\n",
    )
    _, problems = docs_index.render("plans", tmp_path)

    assert len(problems) == 1
    assert f"silent since {old.isoformat()}" in problems[0]


def test_check_mode_reports_a_stale_index(tmp_path, monkeypatch, capsys):
    """The drift detection itself, end to end. This is the whole point of --check."""
    readme = tmp_path / "runbooks" / "README.md"
    write(readme, f"# Runbooks\n\n{docs_index.START}\n_None yet._\n{docs_index.END}\n")
    write(tmp_path / "runbooks" / "thaw-the-cache.md", "# Thaw the cache\n")
    monkeypatch.setattr(docs_index, "DOCS", tmp_path)

    assert docs_index.main(["--check"]) == 1
    assert "index out of date" in capsys.readouterr().err

    assert docs_index.main([]) == 0
    assert "thaw-the-cache" in readme.read_text()
    assert docs_index.main(["--check"]) == 0


def test_dead_links_are_caught_but_placeholders_are_not(tmp_path):
    """Tier-stripping orphans references. Template placeholders are not links."""
    write(tmp_path / "README.md", "See [gone](docs/gone.md) and [real](kept.md).\n")
    write(tmp_path / "kept.md", "# Kept\n")
    write(
        tmp_path / "template.md",
        "Supersede with [NNNN](NNNN-slug.md), see [opt](<option>).\n"
        "```\n$ tool\n[out](2020-01-01-x/)\n```\n",
    )

    assert docs_index.dead_links(tmp_path) == ["README.md: dead link to docs/gone.md"]
