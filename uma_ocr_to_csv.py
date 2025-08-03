import csv
import re
import sys
from rapidocr_onnxruntime import RapidOCR
from rapidfuzz import process, fuzz
from pathlib import Path


def _load_skills() -> list[str]:
    """Load canonical skill names from the skills file."""
    skill_file = Path(__file__).with_name("skill_names.txt")
    with open(skill_file, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


CANONICAL_SKILLS = _load_skills()


# Normalization helper
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


CANONICAL_MAP = {_norm(name): name for name in CANONICAL_SKILLS}

OCR = RapidOCR()


def extract(path: str) -> dict:
    res, _ = OCR(path)

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

    stats["Skills"] = "|".join(skills)
    return stats


def write_csv(rows, output):
    fields = ["Speed", "Stamina", "Power", "Guts", "Wit", "Skills"]
    with open(output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    img1, img2, out = sys.argv[1], sys.argv[2], sys.argv[3]
    rows = [extract(img1), extract(img2)]
    write_csv(rows, out)
    print("✅ CSV written to:", out)
