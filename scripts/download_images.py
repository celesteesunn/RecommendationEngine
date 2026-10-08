"""Download H&M photos for only the products the website shows, and shrink them.

Usage (inside Ubuntu, after `python -m src.serving.site_data`):
    python -m scripts.download_images

Reads web/public/data/image_ids.txt and saves web/public/images/<article_id>.jpg, 400 pixels
wide. Photos already downloaded are skipped, so it is safe to run again. Some products have no
photo in the dataset; the website shows a designed colour card for those.

Needs a Kaggle API token in ~/.kaggle/kaggle.json and the competition rules accepted. The
photos are H&M's and are never committed (web/public/images/ is in .gitignore).
"""

import io
import sys
import tempfile
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

from src.config import load_config, project_path

WIDTH = 400
WORKERS = 8
_local = threading.local()


def kaggle_api():
    """One authenticated client per thread."""
    if not hasattr(_local, "api"):
        from kaggle.api.kaggle_api_extended import KaggleApi

        _local.api = KaggleApi()
        _local.api.authenticate()
    return _local.api


def shrink(data: bytes, target: Path) -> None:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    height = round(image.height * WIDTH / image.width)
    image.resize((WIDTH, height), Image.LANCZOS).save(target, "JPEG", quality=82, optimize=True)


def download(competition: str, article_id: str, out_dir: Path) -> str:
    target = out_dir / f"{article_id}.jpg"
    if target.exists():
        return "skipped"
    remote = f"images/{article_id[:3]}/{article_id}.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        try:
            kaggle_api().competition_download_file(competition, remote, path=tmp, quiet=True)
        except Exception as exc:  # the API raises a generic error with the HTTP status inside
            return "missing" if "404" in str(exc) else f"error: {exc}"
        files = list(Path(tmp).iterdir())
        if not files:
            return "missing"
        path = files[0]
        # Kaggle sometimes sends a single file zipped.
        data = zipfile.ZipFile(path).read(zipfile.ZipFile(path).namelist()[0]) if path.suffix == ".zip" \
            else path.read_bytes()
    shrink(data, target)
    return "downloaded"


def main() -> int:
    config = load_config()
    competition = config["dataset"]["kaggle_competition"]
    ids_file = project_path("web/public/data/image_ids.txt")
    out_dir = project_path("web/public/images")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not ids_file.exists():
        print("Run first: python -m src.serving.site_data", file=sys.stderr)
        return 1

    article_ids = ids_file.read_text(encoding="utf-8").split()
    counts: dict[str, int] = {}
    errors = []
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(download, competition, a, out_dir): a for a in article_ids}
        for done, future in enumerate(as_completed(futures), 1):
            result = future.result()
            key = result.split(":")[0]
            counts[key] = counts.get(key, 0) + 1
            if key == "error":
                errors.append(f"{futures[future]}: {result}")
            if done % 100 == 0 or done == len(article_ids):
                print(f"{done}/{len(article_ids)} {counts}", flush=True)

    for line in errors[:10]:
        print(line, file=sys.stderr)
    return 1 if counts.get("error", 0) == len(article_ids) else 0


if __name__ == "__main__":
    sys.exit(main())
