#!/usr/bin/env python3
"""Generate the index tables in the docs/*/README.md files, and check the
integrity rules that a human reviewer would otherwise have to hold in their
head.

The tables are a cache of the filesystem. Hand-maintained caches drift, so
this regenerates them from the documents themselves:

    make docs        # rewrite the tables
    make docs-check  # fail if they are stale, or a rule is broken

Rules checked:
  - index tables match what is on disk
  - every "Superseded by [NNNN]" points at an ADR that exists
  - no two ADRs share a number
  - no in-progress plan has been silent for more than STALE_DAYS
  - no relative link points at a file that does not exist

Metadata comes from lines the document templates already require, so no
frontmatter ceremony: the first `# ` heading is the title, and
`- **Key:** value` near the top of the file supplies the rest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

START = "<!-- index:start -->"
END = "<!-- index:end -->"
EMPTY = "_None yet._"

STALE_DAYS = 60

DATED_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}-")
DATE_ANYWHERE = re.compile(r"\d{4}-\d{2}-\d{2}")
SUPERSEDED = re.compile(r"Superseded by \[(\d{4})\]")
LINK = re.compile(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)")
FENCE = re.compile(r"^```.*?^```", re.M | re.S)


def rel(path: Path) -> str:
    """Surface-relative label for error messages, e.g. `adr/0004-thing.md`."""
    return f"{path.parent.name}/{path.name}"


def title_of(path: Path) -> str:
    """First `# ` heading, with any `NNNN. ` prefix stripped."""
    for line in path.read_text().splitlines():
        if line.startswith("# "):
            return re.sub(r"^\d{4}\.\s*", "", line[2:].strip())
    return path.stem


def meta(path: Path, key: str, default: str = "?") -> str:
    """Value of a `- **Key:** value` line, searched over the whole file."""
    pattern = re.compile(rf"^\s*[-*]\s*\*\*{re.escape(key)}:?\*\*:?\s*(.+?)\s*$", re.I | re.M)
    match = pattern.search(path.read_text())
    return match.group(1) if match else default


def latest_date(directory: Path) -> str | None:
    """Most recent YYYY-MM-DD appearing anywhere under a plan directory.

    Progress logs are dated appends, so the newest date in the tree is the
    last time anyone touched the work. Cheaper and more honest than mtime,
    which a checkout resets.

    Future dates are ignored. Plans routinely name a target or cutover date,
    and counting one as activity would let a plan abandoned years ago report
    itself as fresh, which is precisely the case the staleness check exists
    to catch.
    """
    today = dt.date.today().isoformat()
    dates = [
        d
        for f in sorted(directory.rglob("*.md"))
        for d in DATE_ANYWHERE.findall(f.read_text())
        if d <= today
    ]
    return max(dates) if dates else None


def dated_dirs(surface: Path) -> list[Path]:
    if not surface.is_dir():
        return []
    return sorted(p for p in surface.iterdir() if p.is_dir() and DATED_DIR.match(p.name))


def adr_rows(surface: Path) -> tuple[list[str], list[str]]:
    rows, problems, seen = [], [], {}
    files = sorted(p for p in surface.glob("*.md") if p.name not in {"README.md", "template.md"})
    for path in files:
        number = path.name[:4]
        if not number.isdigit():
            problems.append(f"{rel(path)}: filename must start with NNNN-")
            continue
        if number in seen:
            problems.append(f"ADR number {number} used twice: {seen[number]}, {path.name}")
        seen[number] = path.name
        status = meta(path, "Status")
        target = SUPERSEDED.search(status)
        if target and not list(surface.glob(f"{target.group(1)}-*.md")):
            problems.append(f"{rel(path)}: superseded by {target.group(1)}, which does not exist")
        rows.append(f"| [{number}]({path.name}) | {title_of(path)} | {status} |")
    return rows, problems


def plan_rows(surface: Path) -> tuple[list[str], list[str]]:
    rows, problems = [], []
    today = dt.date.today()
    for directory in dated_dirs(surface):
        readme = directory / "README.md"
        if not readme.exists():
            problems.append(f"{rel(directory)}: no README.md")
            continue
        status = meta(readme, "Status")
        touched = latest_date(directory)
        if "🟡" in status or "progress" in status.lower():
            if touched is None:
                problems.append(f"{rel(directory)}: in progress, no dated entries")
            elif (today - dt.date.fromisoformat(touched)).days > STALE_DAYS:
                problems.append(
                    f"{rel(directory)}: in progress but silent since {touched}. "
                    f"Mark it ⏸ Deferred or delete it."
                )
        rows.append(
            f"| [{directory.name}]({directory.name}/) | {title_of(readme)} "
            f"| {status} | {touched or '-'} |"
        )
    return rows, problems


def audit_rows(surface: Path) -> tuple[list[str], list[str]]:
    rows, problems = [], []
    for directory in dated_dirs(surface):
        summary = directory / "00-executive-summary.md"
        if not summary.exists():
            problems.append(f"{rel(directory)}: no 00-executive-summary.md")
            continue
        rows.append(
            f"| [{directory.name}]({directory.name}/) | {title_of(summary)} "
            f"| {meta(summary, 'Lens')} | {meta(summary, 'Commit')} |"
        )
    return rows, problems


def runbook_rows(surface: Path) -> tuple[list[str], list[str]]:
    rows = [
        f"| [{p.stem}]({p.name}) | {title_of(p)} | {meta(p, 'Last verified')} |"
        for p in sorted(surface.glob("*.md"))
        if p.name != "README.md"
    ]
    return rows, []


def research_rows(surface: Path) -> tuple[list[str], list[str]]:
    rows, problems = [], []
    for directory in dated_dirs(surface):
        readme = directory / "README.md"
        if not readme.exists():
            problems.append(f"{rel(directory)}: no README.md")
            continue
        rows.append(f"| [{directory.name}]({directory.name}/) | {title_of(readme)} |")
    return rows, problems


SURFACES = {
    "adr": (["| # | Title | Status |", "|---|-------|--------|"], adr_rows),
    "plans": (
        ["| Plan | Goal | Status | Last activity |", "|------|------|--------|---------------|"],
        plan_rows,
    ),
    "audits": (
        ["| Audit | Verdict | Lens | Commit |", "|-------|---------|------|--------|"],
        audit_rows,
    ),
    "runbooks": (
        ["| Runbook | Task | Last verified |", "|---------|------|---------------|"],
        runbook_rows,
    ),
    "research": (["| Workspace | Question |", "|-----------|----------|"], research_rows),
}


def render(name: str, docs: Path | None = None) -> tuple[str, list[str]]:
    # Resolved at call time, not bound as a default, so DOCS stays overridable.
    header, collect = SURFACES[name]
    rows, problems = collect((docs or DOCS) / name)
    body = "\n".join(header + rows) if rows else EMPTY
    return f"{START}\n{body}\n{END}", problems


def dead_links(root: Path | None = None) -> list[str]:
    """Relative markdown links that point at nothing.

    The reason this exists is tiering: deleting `docs/plans/` is a supported
    move, and it silently orphans every reference to it. Without this check a
    freshly cookie-cuttered repo passes `make check` while its README points
    into space.

    Placeholders in the templates (`NNNN-slug.md`, `<option>`) are skipped,
    since they are meant to be filled in, not followed.
    """
    root = root or ROOT
    problems = []
    for path in sorted(root.rglob("*.md")):
        if any(part in {".git", ".venv", "node_modules"} for part in path.parts):
            continue
        # Fenced blocks quote example output, which is not a link to follow.
        body = FENCE.sub("", path.read_text())
        for match in LINK.finditer(body):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if "NNNN" in target or "<" in target or target.startswith("..."):
                continue
            if not (path.parent / target).exists():
                problems.append(f"{path.relative_to(root)}: dead link to {target}")
    return problems


def splice(readme: Path, block: str) -> str:
    text = readme.read_text()
    if START not in text or END not in text:
        raise SystemExit(f"{readme}: missing {START} / {END} markers")
    return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail instead of writing")
    args = parser.parse_args(argv)

    stale, problems = [], []
    for name in SURFACES:
        readme = DOCS / name / "README.md"
        if not readme.exists():
            continue  # surface not adopted at this tier, fine
        block, found = render(name)
        problems += found
        updated = splice(readme, block)
        if updated == readme.read_text():
            continue
        if args.check:
            stale.append(rel(readme))
        else:
            readme.write_text(updated)
            print(f"updated docs/{rel(readme)}")

    # After the write loop: a regenerated index must not be judged on the rows
    # it no longer contains.
    problems += dead_links()

    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if stale:
        print(
            "error: index out of date in " + ", ".join(stale) + ". Run `make docs`.",
            file=sys.stderr,
        )
    return 1 if problems or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
