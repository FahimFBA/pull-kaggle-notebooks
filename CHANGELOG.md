# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-14

### Added

- Interactive CLI (`pull_kaggle_notebooks.py`) that prompts for a Kaggle dataset link,
  username, and API key, then downloads every public notebook attached to that dataset.
- Rich-powered progress UI: spinner while listing notebooks, per-notebook progress bar
  while downloading, and a summary table of successes/failures at the end.
- `requirements.txt` and `README.md` with setup and usage instructions.
