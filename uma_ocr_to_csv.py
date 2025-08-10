import csv
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from rapidocr_onnxruntime import RapidOCR
from rapidfuzz import process, fuzz


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
    """Load canonical skill names from the skills file."""
    skill_file = Path(__file__).with_name("skill_names.txt")
    logger.debug("Loading skills from %s", skill_file)
    try:
        with open(skill_file, encoding="utf-8") as f:
            skills = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error("Skill file not found: %s", skill_file)
        return []
    logger.info("Loaded %d skills", len(skills))
    return skills


CANONICAL_SKILLS = _load_skills()


# Normalization helper
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


CANONICAL_MAP = {_norm(name): name for name in CANONICAL_SKILLS}

OCR = RapidOCR()


def extract(path: str) -> dict:
    logger.info("Running OCR on %s", path)
    res, _ = OCR(path)
    logger.debug("OCR returned %d text boxes", len(res))

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
    sorted_res = sorted(
        res,
        key=lambda item: (
            round(min(p[1] for p in item[0]) / 50),
            min(p[0] for p in item[0]),
        ),
    )
    for box, text, _ in sorted_res:
        y0 = min(p[1] for p in box)
        if y0 < 950:  # skip upper text regions
            continue
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
    logger.info("Extracted stats %s with %d skills", stats, len(skills))
    if not skills:
        logger.warning("No skills matched in %s", path)
    return stats


def write_csv(rows, output):
    fields = ["Speed", "Stamina", "Power", "Guts", "Wit", "Skills"]
    with open(output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    logger.debug("Wrote %d rows to %s", len(rows), output)


if __name__ == "__main__":
    base_dir = Path(__file__).with_name("data")
    img1_name, img2_name = sys.argv[1], sys.argv[2]
    img1_path = base_dir / img1_name
    img2_path = base_dir / img2_name
    output_path = base_dir / f"{Path(img1_name).stem}_{Path(img2_name).stem}.csv"

    logger.info("Extracting data from %s and %s", img1_path, img2_path)
    rows = [extract(str(img1_path)), extract(str(img2_path))]
    write_csv(rows, output_path)
    logger.info("CSV written to %s", output_path)
