"""Download H&M product photos for only the products the website shows.

Usage (inside Ubuntu, after `python -m src.serving.site_data`):
    python -m scripts.download_images

Reads web/public/data/image_ids.txt and saves web/public/images/<article_id>.jpg. The photos
come from a public Kaggle dataset of H&M's own product images resized to 224 x 224
(tbierhance/hm-fashion-images-squared-224, about 285 MB). It is downloaded once to a
temporary folder, only the photos the site needs are kept, and the download is deleted.
Photos already in place are skipped, so it is safe to run again. Some products have no photo
in the dataset; the website shows a designed colour card for those.

Needs a Kaggle API token in ~/.kaggle/kaggle.json. The photos are H&M's and are never
committed (web/public/images/ is in .gitignore).
"""

import sys
import tempfile
import zipfile
from pathlib import Path

from src.config import project_path

DATASET = "tbierhance/hm-fashion-images-squared-224"
FOLDER = "images_224x224"


def photo_name(article_id: str) -> str:
    """Where a product's photo sits inside the dataset: grouped by the first 3 digits."""
    return f"{FOLDER}/{article_id[:3]}/{article_id}.jpg"


def extract(archive: Path, article_ids: list[str], out_dir: Path) -> dict[str, int]:
    counts = {"saved": 0, "missing": 0}
    with zipfile.ZipFile(archive) as zf:
        available = set(zf.namelist())
        for article_id in article_ids:
            name = photo_name(article_id)
            if name not in available:
                counts["missing"] += 1
                continue
            (out_dir / f"{article_id}.jpg").write_bytes(zf.read(name))
            counts["saved"] += 1
    return counts


def main() -> int:
    ids_file = project_path("web/public/data/image_ids.txt")
    out_dir = project_path("web/public/images")
    if not ids_file.exists():
        print("Run first: python -m src.serving.site_data", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)

    wanted = ids_file.read_text(encoding="utf-8").split()
    needed = [a for a in wanted if not (out_dir / f"{a}.jpg").exists()]
    print(f"{len(wanted)} products, {len(wanted) - len(needed)} photos already in place, {len(needed)} to fetch")
    if not needed:
        return 0

    # Imported here because importing kaggle authenticates immediately.
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Downloading {DATASET} (about 285 MB) ...", flush=True)
        api.dataset_download_files(DATASET, path=tmp, quiet=False, unzip=False)
        archive = next(Path(tmp).glob("*.zip"))
        counts = extract(archive, needed, out_dir)

    print(f"Saved {counts['saved']} photos; {counts['missing']} products have no photo in the dataset "
          f"and will show as colour cards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
