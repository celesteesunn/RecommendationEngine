"""Download the H&M tabular files from Kaggle into data/raw/.

Usage:
    python -m src.data.download            # skip files that already exist
    python -m src.data.download --force    # re-download everything

Prerequisites:
    1. Accept the competition rules on Kaggle:
       https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/rules
    2. Place your API token at ~/.kaggle/kaggle.json
       (or set KAGGLE_USERNAME and KAGGLE_KEY environment variables).
"""

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

from src.config import load_config, project_path

# transactions_train.csv is ~3.5 GB unzipped; the zip and CSV coexist while extracting.
MIN_FREE_DISK_GB = 6


def has_kaggle_credentials() -> bool:
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    config_dir = Path(os.environ.get("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle"))
    return (config_dir / "kaggle.json").is_file()


def extract_zip(zip_path: Path, target_dir: Path) -> None:
    print(f"  extracting {zip_path.name} ...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target_dir)
    zip_path.unlink()


def download_file(api, competition: str, file_name: str, raw_dir: Path, force: bool) -> None:
    csv_path = raw_dir / file_name
    if csv_path.exists() and not force:
        print(f"[skip] {file_name} already exists")
        return

    print(f"[download] {file_name}")
    api.competition_download_file(competition, file_name, path=str(raw_dir), force=force, quiet=False)

    # Kaggle serves large files zipped; small files may arrive as plain CSV.
    zip_path = raw_dir / f"{file_name}.zip"
    if zip_path.exists():
        extract_zip(zip_path, raw_dir)

    if not csv_path.exists():
        raise FileNotFoundError(f"Expected {csv_path} after download, but it was not found")
    print(f"  saved {csv_path} ({csv_path.stat().st_size / 1e6:,.0f} MB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = parser.parse_args()

    config = load_config()
    competition = config["dataset"]["kaggle_competition"]
    raw_dir = project_path(config["paths"]["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)

    if not has_kaggle_credentials():
        print("Kaggle credentials not found. Place kaggle.json in ~/.kaggle/ "
              "or set KAGGLE_USERNAME and KAGGLE_KEY.", file=sys.stderr)
        return 1

    free_gb = shutil.disk_usage(raw_dir).free / 1e9
    if free_gb < MIN_FREE_DISK_GB:
        print(f"Only {free_gb:.1f} GB free; at least {MIN_FREE_DISK_GB} GB is needed.", file=sys.stderr)
        return 1

    # Imported here because importing kaggle authenticates immediately.
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    for file_name in config["dataset"]["files"]:
        try:
            download_file(api, competition, file_name, raw_dir, args.force)
        except Exception as exc:  # kaggle raises ApiException with an HTTP status
            if "403" in str(exc):
                print(f"Access denied for {file_name}. Accept the competition rules first: "
                      f"https://www.kaggle.com/competitions/{competition}/rules", file=sys.stderr)
                return 1
            raise

    print("All files downloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
