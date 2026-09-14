"""Tests for .github/scripts/extract_changelog.py."""

import extract_changelog as ec

SAMPLE_CHANGELOG = """# Changelog

## [Unreleased]

### Added
- wip feature

## [0.2.0] - 2026-01-02

### Added
- thing two

## [0.1.0] - 2026-01-01

### Added
- thing one
"""


def test_find_latest_release_skips_unreleased():
    """find_latest_release should return the newest released section, not Unreleased."""
    result = ec.find_latest_release(SAMPLE_CHANGELOG)

    assert result is not None
    version, body = result
    assert version == "0.2.0"
    assert "thing two" in body
    assert "thing one" not in body


def test_find_latest_release_no_released_section():
    """find_latest_release should return None when only Unreleased exists."""
    text = "# Changelog\n\n## [Unreleased]\n\n### Added\n- wip\n"
    assert ec.find_latest_release(text) is None


def test_main_writes_release_notes_and_prints_version(tmp_path, monkeypatch, capsys):
    """main() should print the version and write its notes to release_notes.md.

    Args:
        tmp_path: pytest fixture used as a scratch CHANGELOG.md location.
        monkeypatch: pytest fixture used to chdir into tmp_path.
        capsys: pytest fixture used to capture the printed version.
    """
    (tmp_path / "CHANGELOG.md").write_text(SAMPLE_CHANGELOG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = ec.main()

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "0.2.0"
    notes = (tmp_path / "release_notes.md").read_text(encoding="utf-8")
    assert "thing two" in notes


def test_main_missing_changelog(tmp_path, monkeypatch):
    """main() should return exit code 1 when CHANGELOG.md is missing.

    Args:
        tmp_path: pytest fixture providing an empty directory with no changelog.
        monkeypatch: pytest fixture used to chdir into tmp_path.
    """
    monkeypatch.chdir(tmp_path)
    assert ec.main() == 1


def test_main_no_release_section(tmp_path, monkeypatch, capsys):
    """main() should exit 0 and write nothing when only Unreleased exists.

    Args:
        tmp_path: pytest fixture used as a scratch CHANGELOG.md location.
        monkeypatch: pytest fixture used to chdir into tmp_path.
        capsys: pytest fixture used to assert nothing was printed.
    """
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n- wip\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = ec.main()

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert not (tmp_path / "release_notes.md").exists()
