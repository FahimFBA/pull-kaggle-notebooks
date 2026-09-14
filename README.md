# pull-kaggle-notebooks

Download every public notebook attached to a Kaggle dataset, with a live progress UI.

## Setup

```bash
pip install -r requirements.txt
```

You need a Kaggle API key. Get one at https://www.kaggle.com/settings -> API -> "Create New Token". This gives you a username and key (found inside the downloaded `kaggle.json`).

## Run

```bash
python pull_kaggle_notebooks.py
```

You'll be prompted for:
- **Dataset link or slug** — e.g. `https://www.kaggle.com/datasets/owner/dataset-name` or just `owner/dataset-name`
- **Kaggle username**
- **Kaggle API key**
- **Download directory** — defaults to `./kaggle_notebooks`

Each notebook is saved to its own subfolder inside the download directory, along with its metadata.
