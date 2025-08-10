import csv
import logging
import os
import re
import sys
from itertools import zip_longest
from pathlib import Path

import cv2
import math
import numpy as np
from dotenv import load_dotenv
from rapidocr_onnxruntime import RapidOCR
from rapidfuzz import process, fuzz
import json

# Reuse the skill name data source from uma_csv_to_url
from uma_csv_to_url import REPO_URL_TOOLS, TOOLS_DIR, ensure_repo


ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(ENV_PATH)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)
logger.debug("Environment loaded from %s with log level %s", ENV_PATH, LOG_LEVEL)


def _load_skills() -> list[str]:
    """Load canonical skill names from the uma-tools repository."""
    ensure_repo(REPO_URL_TOOLS, TOOLS_DIR)
    skill_file = TOOLS_DIR / "umalator-global" / "skillnames.json"
    logger.debug("Loading skills from %s", skill_file)
    try:
        with open(skill_file, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("Skill file not found: %s", skill_file)
        return []
    skills = [names[0] for names in data.values() if names]
    logger.info("Loaded %d skills", len(skills))
    return skills


CANONICAL_SKILLS = _load_skills()


def _load_umas() -> list[str]:
    """Load canonical runner names from the uma-tools repository."""
    ensure_repo(REPO_URL_TOOLS, TOOLS_DIR)
    uma_file = TOOLS_DIR / "umalator-global" / "umas.json"
    logger.debug("Loading umas from %s", uma_file)
    try:
        with open(uma_file, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("Uma file not found: %s", uma_file)
        return []
    names: list[str] = []
    for v in data.values():
        for name in v.get("name", []):
            if name:
                names.append(name)
    logger.info("Loaded %d umas", len(names))
    return names


CANONICAL_UMAS = _load_umas()


# --- normalization ---------------------------------------------------------

_CIRCLE_ALIASES = {
    "o": "○",
    "O": "○",
    "0": "○",
    "〇": "○",
    "◎": "◎",
    "○": "○",
}


def _normalize_circles(text: str) -> str:
    """Replace common lookalikes of the circle glyphs."""
    return "".join(_CIRCLE_ALIASES.get(ch, ch) for ch in text)


def _norm(s: str) -> str:
    s = _normalize_circles(s)
    return re.sub(r"[^a-z0-9◎○]", "", s.lower())


CANONICAL_MAP = {_norm(name): name for name in CANONICAL_SKILLS}
UMA_MAP = {_norm(name): name for name in CANONICAL_UMAS}

OCR = RapidOCR()


def _group_column(lines):
    lines.sort(key=lambda l: l[1])
    grouped = []
    for x0, y0, x1, y1, text in lines:
        if grouped and y0 - grouped[-1][3] < 25:
            grouped[-1][4].append(text)
            grouped[-1][2] = max(grouped[-1][2], x1)
            grouped[-1][3] = max(grouped[-1][3], y1)
        else:
            grouped.append([x0, y0, x1, y1, [text]])
    return grouped


def _group_skills(res):
    lines = []
    for box, text, _ in res:
        x0 = min(p[0] for p in box)
        y0 = min(p[1] for p in box)
        x1 = max(p[0] for p in box)
        y1 = max(p[1] for p in box)
        if y0 < 850:
            continue
        lines.append([x0, y0, x1, y1, text])

    if not lines:
        return []
    xs = [l[0] for l in lines]
    mid = (min(xs) + max(xs)) / 2
    left = [l for l in lines if l[0] < mid]
    right = [l for l in lines if l[0] >= mid]
    left_g = _group_column(left)
    right_g = _group_column(right)
    groups = []
    for l, r in zip_longest(left_g, right_g):
        if l:
            groups.append((l[0], l[1], l[2], l[3], " ".join(l[4])))
        if r:
            groups.append((r[0], r[1], r[2], r[3], " ".join(r[4])))
    return groups


def _detect_circle(img, rect):
    x0, y0, x1, y1 = map(int, rect)
    margin = 5
    xs = max(0, x1 - 50)
    xe = min(img.shape[1], x1 + 30)
    ys = max(0, y0 - margin)
    ye = min(img.shape[0], y1 + margin)
    crop = img[ys:ye, xs:xe]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, 1, 20, param1=50, param2=15, minRadius=5, maxRadius=30
    )
    if circles is None:
        return None
    cx, cy, r = max(circles[0], key=lambda c: c[2])
    canny = cv2.Canny(gray, 50, 150)
    mask = np.zeros_like(canny)
    inner_r = int(r * 0.55)
    cv2.circle(mask, (int(cx), int(cy)), inner_r, 255, 2)
    count = cv2.countNonZero(cv2.bitwise_and(canny, mask))
    coverage = count / (2 * math.pi * inner_r)
    if coverage > 0.6:
        return "◎"
    return "○"


def extract(path: str) -> dict:
    logger.info("Running OCR on %s", path)
    res, _ = OCR(path)
    logger.debug("OCR returned %d text boxes", len(res))
    img = cv2.imread(path)

    height, width = img.shape[:2]

    # --- runner name --------------------------------------------------------
    runner_name = ""
    best_score = 0
    for box, text, _ in res:
        x0 = min(p[0] for p in box)
        y0 = min(p[1] for p in box)
        x1 = max(p[0] for p in box)
        y1 = max(p[1] for p in box)
        if y1 < 400 and x0 > width * 0.5:
            key = _norm(text)
            if not key:
                continue
            match = process.extractOne(key, UMA_MAP.keys(), scorer=fuzz.ratio)
            if match and match[1] > best_score:
                best_score = match[1]
                runner_name = UMA_MAP[match[0]]
    if not runner_name:
        logger.warning("Runner name not detected in %s", path)

    # --- stats ---------------------------------------------------------------
    nums = []
    for box, text, _ in res:
        if re.fullmatch(r"\d{3,4}", text):
            x0 = min(p[0] for p in box)
            y0 = min(p[1] for p in box)
            nums.append((y0, x0, text))

    nums.sort()
    stats_vals = ["", "", "", "", ""]
    if nums:
        first_y = nums[0][0]
        row = [n for n in nums if abs(n[0] - first_y) < 30]
        row.sort(key=lambda n: n[1])
        stats_vals = [n[2] for n in row[:5]]
        logger.debug("Detected stat numbers: %s", stats_vals)
    else:
        logger.warning("No stat numbers detected in %s", path)

    stats = dict(zip(["Speed", "Stamina", "Power", "Guts", "Wit"], stats_vals))

    # --- skills --------------------------------------------------------------
    skills = []
    seen = set()

    groups = _group_skills(res)
    logger.debug("Grouped into %d skill boxes", len(groups))
    for x0, y0, x1, y1, text in groups:
        circle = _detect_circle(img, (x0, y0, x1, y1))
        if circle and circle not in text:
            text = f"{text} {circle}"
        key = _norm(text)
        if not key:
            continue
        match = process.extractOne(key, CANONICAL_MAP.keys(), scorer=fuzz.ratio, score_cutoff=80)
        if match:
            canonical = CANONICAL_MAP[match[0]]
            if canonical not in seen:
                seen.add(canonical)
                skills.append(canonical)
                logger.debug("Matched skill: %s", canonical)

    stats["Skills"] = "|".join(skills)
    stats["Name"] = runner_name
    logger.info("Extracted stats %s with %d skills", stats, len(skills))
    if not skills:
        logger.warning("No skills matched in %s", path)
    return stats


def append_csv(row: dict, output: Path) -> None:
    """Append a single row of stats to the CSV file, writing a header if needed."""
    fields = ["Name", "Speed", "Stamina", "Power", "Guts", "Wit", "Skills"]
    write_header = not output.exists()
    with open(output, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        w.writerow(row)
    logger.debug("Appended row to %s", output)


if __name__ == "__main__":
    base_dir = Path(__file__).with_name("data")
    processed_dir = base_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
    output_path = base_dir / "runners.csv"

    images = [p for p in base_dir.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    if not images:
        logger.info("No images found in %s", base_dir)
        sys.exit(0)

    for img_path in images:
        logger.info("Extracting data from %s", img_path)
        row = extract(str(img_path))
        append_csv(row, output_path)
        img_path.rename(processed_dir / img_path.name)
        logger.info("Moved %s to %s", img_path.name, processed_dir)

    logger.info("Processed %d images", len(images))
