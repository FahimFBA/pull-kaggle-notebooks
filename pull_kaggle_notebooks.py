#!/usr/bin/env python3
"""Download every public notebook (kernel) attached to a Kaggle dataset."""

import os
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Prompt
from rich.table import Table

console = Console()

DATASET_URL_RE = re.compile(
    r"(?:https?://(?:www\.)?kaggle\.com/datasets/)?"
    r"(?P<owner>[\w-]+)/(?P<slug>[\w-]+)/?$"
)


def parse_dataset_ref(raw: str) -> str:
    """Normalize a dataset URL or slug into an ``owner/slug`` reference.

    Args:
        raw: Raw user input, either a full Kaggle dataset URL
            (e.g. ``https://www.kaggle.com/datasets/owner/slug``) or an
            already-normalized ``owner/slug`` string.

    Returns:
        The dataset reference in ``owner/slug`` form.

    Exits:
        Calls ``sys.exit(1)`` if ``raw`` cannot be parsed as a dataset reference.
    """
    raw = raw.strip().rstrip("/")
    match = DATASET_URL_RE.search(raw)
    if not match:
        console.print(
            "[red]Could not parse dataset reference.[/red] "
            "Expected something like 'https://www.kaggle.com/datasets/owner/dataset-slug' "
            "or 'owner/dataset-slug'."
        )
        sys.exit(1)
    return f"{match.group('owner')}/{match.group('slug')}"


def prompt_inputs() -> tuple[str, str, str, Path]:
    """Interactively prompt the user for all inputs needed to run a pull.

    Returns:
        A ``(dataset_ref, username, api_key, download_dir)`` tuple, where
        ``dataset_ref`` is a normalized ``owner/slug`` string and
        ``download_dir`` is an expanded, absolute path.
    """
    console.print(
        Panel.fit(
            "[bold cyan]Kaggle Notebook Puller[/bold cyan]\n"
            "Downloads every notebook attached to a Kaggle dataset.",
            border_style="cyan",
        )
    )

    dataset_ref = parse_dataset_ref(
        Prompt.ask("[bold]Kaggle dataset link or slug[/bold] (e.g. owner/dataset-name)")
    )
    username = Prompt.ask("[bold]Kaggle username[/bold]")
    api_key = Prompt.ask("[bold]Kaggle API key[/bold]", password=True)
    download_dir = Prompt.ask(
        "[bold]Download directory[/bold]", default="./kaggle_notebooks"
    )

    return dataset_ref, username, api_key, Path(download_dir).expanduser().resolve()


def build_authenticated_api(username: str, api_key: str):
    """Build and authenticate a Kaggle API client from a username and key.

    Sets ``KAGGLE_USERNAME``/``KAGGLE_KEY`` env vars before importing the
    ``kaggle`` package, since it authenticates as a side effect of import.

    Args:
        username: Kaggle account username.
        api_key: Kaggle API key (from ``kaggle.json`` or account settings).

    Returns:
        An authenticated ``kaggle.api.kaggle_api_extended.KaggleApi`` instance.
    """
    os.environ["KAGGLE_USERNAME"] = username
    os.environ["KAGGLE_KEY"] = api_key

    from kaggle.api.kaggle_api_extended import KaggleApi  # noqa: E402  (needs env vars set first)

    api = KaggleApi()
    api.authenticate()
    return api


def list_all_kernels(api, dataset_ref: str, console: Console):
    """Page through the Kaggle API to collect every kernel for a dataset.

    Args:
        api: Authenticated ``KaggleApi`` instance.
        dataset_ref: Dataset reference in ``owner/slug`` form.
        console: Rich console used to show a lookup spinner.

    Returns:
        List of kernel metadata objects (``ApiKernelMetadata``) attached to
        the dataset. Empty if the dataset has no public notebooks.
    """
    kernels = []
    page = 1
    with console.status("[bold cyan]Looking up notebooks for dataset...", spinner="dots"):
        while True:
            batch = api.kernels_list(dataset=dataset_ref, page=page, page_size=100)
            if not batch:
                break
            kernels.extend(batch)
            page += 1
    return kernels


def download_kernels(api, kernels, download_dir: Path) -> tuple[list[str], list[tuple[str, str]]]:
    """Download each kernel's notebook and metadata, showing a progress bar.

    A failure on one kernel is recorded and does not stop the remaining
    downloads.

    Args:
        api: Authenticated ``KaggleApi`` instance.
        kernels: Kernel metadata objects as returned by ``list_all_kernels``.
        download_dir: Base directory to save notebooks into; created if
            missing. Each kernel gets its own subdirectory inside it.

    Returns:
        A ``(succeeded, failed)`` tuple: ``succeeded`` is a list of kernel
        refs downloaded successfully; ``failed`` is a list of
        ``(kernel_ref, error_message)`` pairs for the ones that errored.
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.fields[kernel]}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task("Downloading", total=len(kernels), kernel="starting...")
        for kernel in kernels:
            kernel_ref = kernel.ref
            progress.update(task, kernel=kernel_ref)
            try:
                kernel_dir = download_dir / kernel_ref.replace("/", "_")
                api.kernels_pull(kernel_ref, path=str(kernel_dir), metadata=True)
                succeeded.append(kernel_ref)
            except Exception as exc:  # noqa: BLE001 - report and keep going
                failed.append((kernel_ref, str(exc)))
            progress.advance(task)

    return succeeded, failed


def print_summary(dataset_ref: str, download_dir: Path, succeeded: list[str], failed: list[tuple[str, str]]):
    """Print a results table and totals panel for a completed download run.

    Args:
        dataset_ref: Dataset reference in ``owner/slug`` form, used in the title.
        download_dir: Directory the notebooks were saved to.
        succeeded: Kernel refs downloaded successfully.
        failed: ``(kernel_ref, error_message)`` pairs for kernels that failed.
    """
    table = Table(title=f"Results for dataset {dataset_ref}", show_lines=False)
    table.add_column("Notebook", style="cyan")
    table.add_column("Status", style="bold")

    for ref in succeeded:
        table.add_row(ref, "[green]done[/green]")
    for ref, error in failed:
        table.add_row(ref, f"[red]failed[/red] ({error})")

    console.print(table)
    console.print(
        Panel.fit(
            f"[bold green]{len(succeeded)} downloaded[/bold green]   "
            f"[bold red]{len(failed)} failed[/bold red]\n"
            f"Saved to: [underline]{download_dir}[/underline]",
            border_style="green" if not failed else "yellow",
        )
    )


def main():
    """Run the interactive flow: prompt, authenticate, list, download, report."""
    dataset_ref, username, api_key, download_dir = prompt_inputs()

    try:
        api = build_authenticated_api(username, api_key)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Authentication failed:[/red] {exc}")
        sys.exit(1)

    try:
        kernels = list_all_kernels(api, dataset_ref, console)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to list notebooks:[/red] {exc}")
        sys.exit(1)

    if not kernels:
        console.print(
            f"[yellow]No public notebooks found for dataset '{dataset_ref}'.[/yellow]"
        )
        sys.exit(0)

    console.print(f"[bold]Found {len(kernels)} notebook(s).[/bold] Starting download...")

    succeeded, failed = download_kernels(api, kernels, download_dir)
    print_summary(dataset_ref, download_dir, succeeded, failed)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
