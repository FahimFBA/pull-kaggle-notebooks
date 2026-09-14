#!/usr/bin/env python3
"""Extract the newest released version and its notes from CHANGELOG.md.

Reads ``CHANGELOG.md`` (Keep a Changelog format), finds the topmost
``## [x.y.z] - date`` section (skipping ``## [Unreleased]``), prints the
version number to stdout, and writes that section's body to
``release_notes.md`` for use as GitHub release notes.

If no released version section is found, prints nothing and does not
write ``release_notes.md``.
"""

import re
import sys
from pathlib import Path

CHANGELOG_PATH = Path("CHANGELOG.md")
NOTES_PATH = Path("release_notes.md")
SECTION_RE = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>.+))?\s*$", re.MULTILINE)


def find_latest_release(text: str) -> tuple[str, str] | None:
    """Find the topmost non-"Unreleased" version section in a changelog.

    Args:
        text: Full contents of the changelog file.

    Returns:
        A ``(version, body)`` tuple for the first released section found,
        or ``None`` if the changelog has no released version section.
    """
    matches = list(SECTION_RE.finditer(text))
    for i, match in enumerate(matches):
        version = match.group("version")
        if version.strip().lower() == "unreleased":
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip("\n")
        return version, body
    return None


def main() -> int:
    """Extract the latest release section and write it out.

    Returns:
        Process exit code: 0 on success (including "nothing to release"),
        1 if ``CHANGELOG.md`` is missing.
    """
    if not CHANGELOG_PATH.exists():
        print("CHANGELOG.md not found", file=sys.stderr)
        return 1

    result = find_latest_release(CHANGELOG_PATH.read_text(encoding="utf-8"))
    if result is None:
        return 0

    version, body = result
    NOTES_PATH.write_text(body + "\n", encoding="utf-8")
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
