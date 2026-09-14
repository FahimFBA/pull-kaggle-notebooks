"""Tests for pull_kaggle_notebooks.py.

Kaggle API interactions are stubbed out with lightweight fakes so the suite
runs fully offline with no real Kaggle credentials.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import pull_kaggle_notebooks as pkn


# --------------------------------------------------------------------------
# parse_dataset_ref
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.kaggle.com/datasets/zynicide/wine-reviews", "zynicide/wine-reviews"),
        ("https://www.kaggle.com/datasets/zynicide/wine-reviews/", "zynicide/wine-reviews"),
        ("zynicide/wine-reviews", "zynicide/wine-reviews"),
    ],
)
def test_parse_dataset_ref_valid(raw, expected):
    """parse_dataset_ref should normalize URLs and bare slugs to owner/slug.

    Args:
        raw: Input string as provided by the parametrize table.
        expected: Expected normalized ``owner/slug`` result.
    """
    assert pkn.parse_dataset_ref(raw) == expected


@pytest.mark.parametrize("raw", ["", "onlyoneword", "   "])
def test_parse_dataset_ref_invalid_exits(raw):
    """parse_dataset_ref should exit(1) on input with no owner/slug pair.

    Args:
        raw: Unparsable input string as provided by the parametrize table.
    """
    with pytest.raises(SystemExit) as exc_info:
        pkn.parse_dataset_ref(raw)
    assert exc_info.value.code == 1


# --------------------------------------------------------------------------
# prompt_inputs
# --------------------------------------------------------------------------


def test_prompt_inputs_returns_normalized_values(monkeypatch, tmp_path):
    """prompt_inputs should return prompt answers normalized into the right types.

    Args:
        monkeypatch: pytest fixture used to stub ``Prompt.ask`` with canned answers.
        tmp_path: pytest fixture providing a temporary directory for the download dir answer.
    """
    answers = iter(["owner/my-dataset", "myuser", "mykey", str(tmp_path / "out")])
    monkeypatch.setattr(pkn.Prompt, "ask", lambda *a, **kw: next(answers))

    dataset_ref, username, api_key, download_dir = pkn.prompt_inputs()

    assert dataset_ref == "owner/my-dataset"
    assert username == "myuser"
    assert api_key == "mykey"
    assert download_dir == (tmp_path / "out").resolve()


# --------------------------------------------------------------------------
# build_authenticated_api
# --------------------------------------------------------------------------


def test_build_authenticated_api_sets_env_and_authenticates(monkeypatch):
    """build_authenticated_api should set KAGGLE_* env vars and return a usable client.

    Args:
        monkeypatch: pytest fixture used to clear any pre-existing Kaggle env vars.
    """
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)

    api = pkn.build_authenticated_api("testuser", "testkey")

    assert os.environ["KAGGLE_USERNAME"] == "testuser"
    assert os.environ["KAGGLE_KEY"] == "testkey"
    assert hasattr(api, "kernels_list")
    assert hasattr(api, "kernels_pull")


# --------------------------------------------------------------------------
# list_all_kernels
# --------------------------------------------------------------------------


def _kernel(ref):
    """Build a minimal stand-in for a Kaggle ``ApiKernelMetadata`` object.

    Args:
        ref: Kernel reference string, e.g. ``"owner/notebook-slug"``.

    Returns:
        A ``SimpleNamespace`` exposing the ``ref`` attribute the code under test reads.
    """
    return SimpleNamespace(ref=ref)


class FakeListApi:
    """Fake Kaggle API that serves kernels_list results page by page."""

    def __init__(self, pages):
        """Store the pages of kernel results to serve in order.

        Args:
            pages: List of pages, each a list of kernel objects; an empty
                list signals the end of pagination.
        """
        self.pages = pages
        self.calls = []

    def kernels_list(self, dataset, page, page_size):
        """Return the requested page and record the call arguments.

        Args:
            dataset: Dataset reference passed by the caller.
            page: 1-indexed page number to return.
            page_size: Page size passed by the caller (recorded, not used to slice).

        Returns:
            The list of kernel objects for ``page``, or an empty list once
            ``pages`` is exhausted.
        """
        self.calls.append((dataset, page, page_size))
        index = page - 1
        return self.pages[index] if index < len(self.pages) else []


def test_list_all_kernels_paginates_until_empty():
    """list_all_kernels should keep requesting pages until an empty page is returned."""
    pages = [
        [_kernel("owner/nb-1"), _kernel("owner/nb-2")],
        [_kernel("owner/nb-3")],
        [],
    ]
    api = FakeListApi(pages)

    kernels = pkn.list_all_kernels(api, "owner/dataset", pkn.console)

    assert [k.ref for k in kernels] == ["owner/nb-1", "owner/nb-2", "owner/nb-3"]
    assert api.calls == [
        ("owner/dataset", 1, 100),
        ("owner/dataset", 2, 100),
        ("owner/dataset", 3, 100),
    ]


def test_list_all_kernels_empty_dataset():
    """list_all_kernels should return an empty list when the first page is empty."""
    api = FakeListApi([[]])
    kernels = pkn.list_all_kernels(api, "owner/dataset", pkn.console)
    assert kernels == []


# --------------------------------------------------------------------------
# download_kernels
# --------------------------------------------------------------------------


class FakeDownloadApi:
    """Fake Kaggle API whose kernels_pull fails for a chosen set of refs."""

    def __init__(self, fail_refs=()):
        """Configure which kernel refs should raise when pulled.

        Args:
            fail_refs: Iterable of kernel ref strings that ``kernels_pull``
                should raise a ``RuntimeError`` for.
        """
        self.fail_refs = set(fail_refs)
        self.pulled = []

    def kernels_pull(self, kernel, path, metadata=False):
        """Record the pull call and raise if ``kernel`` is a configured failure.

        Args:
            kernel: Kernel ref being "pulled".
            path: Destination path passed by the caller.
            metadata: Whether metadata was requested.

        Raises:
            RuntimeError: If ``kernel`` is in ``fail_refs``.
        """
        self.pulled.append((kernel, path, metadata))
        if kernel in self.fail_refs:
            raise RuntimeError(f"boom: {kernel}")


def test_download_kernels_reports_success_and_failure(tmp_path):
    """download_kernels should collect one success and one failure separately.

    Args:
        tmp_path: pytest fixture providing a temporary download directory.
    """
    kernels = [_kernel("owner/good-one"), _kernel("owner/bad-one")]
    api = FakeDownloadApi(fail_refs={"owner/bad-one"})
    download_dir = tmp_path / "downloads"

    succeeded, failed = pkn.download_kernels(api, kernels, download_dir)

    assert succeeded == ["owner/good-one"]
    assert len(failed) == 1
    assert failed[0][0] == "owner/bad-one"
    assert "boom" in failed[0][1]
    assert download_dir.is_dir()
    assert api.pulled[0] == ("owner/good-one", str(download_dir / "owner_good-one"), True)


def test_download_kernels_empty_list(tmp_path):
    """download_kernels should return empty results and still create the download dir.

    Args:
        tmp_path: pytest fixture providing a temporary download directory.
    """
    api = FakeDownloadApi()
    download_dir = tmp_path / "downloads"

    succeeded, failed = pkn.download_kernels(api, [], download_dir)

    assert succeeded == []
    assert failed == []
    assert download_dir.is_dir()


# --------------------------------------------------------------------------
# print_summary
# --------------------------------------------------------------------------


def test_print_summary_lists_results(capsys):
    """print_summary should print each result row plus the totals line.

    Args:
        capsys: pytest fixture used to capture the console output.
    """
    pkn.print_summary(
        "owner/dataset",
        Path("/tmp/out"),
        succeeded=["owner/nb-1"],
        failed=[("owner/nb-2", "some error")],
    )
    out = capsys.readouterr().out
    assert "owner/nb-1" in out
    assert "owner/nb-2" in out
    assert "some error" in out
    assert "1 downloaded" in out
    assert "1 failed" in out
