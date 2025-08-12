import time
import hashlib
from pathlib import Path
from typing import Optional

from PIL import ImageGrab, Image

from uma_ocr_to_csv import extract, append_csv


BASE_DIR = Path(__file__).with_name("data")
PROCESSED_DIR = BASE_DIR / "processed"
OUTPUT_CSV = BASE_DIR / "runners.csv"


def _hash_image(img: Image.Image) -> str:
    """Return a hash of the image bytes to detect changes."""
    md5 = hashlib.md5()
    md5.update(img.tobytes())
    return md5.hexdigest()


def _save_temp(img: Image.Image) -> Path:
    """Save the clipboard image to the data directory."""
    BASE_DIR.mkdir(exist_ok=True)
    timestamp = int(time.time())
    path = BASE_DIR / f"clip_{timestamp}.png"
    img.save(path)
    return path


def main() -> None:
    print("Watching clipboard for images. Use your OS screenshot shortcut to capture a region. Press Ctrl+C to quit.")
    PROCESSED_DIR.mkdir(exist_ok=True)
    last_hash: Optional[str] = None
    while True:
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            current = _hash_image(img)
            if current != last_hash:
                last_hash = current
                temp_path = _save_temp(img)
                row = extract(str(temp_path))
                append_csv(row, OUTPUT_CSV)
                temp_path.rename(PROCESSED_DIR / temp_path.name)
                print(f"Added {row.get('Name','')} to {OUTPUT_CSV}")
        time.sleep(1)


if __name__ == "__main__":
    main()
