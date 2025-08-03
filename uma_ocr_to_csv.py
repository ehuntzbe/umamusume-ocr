# uma_ocr_to_csv.py (improved skill matching)

import csv, re, sys
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from difflib import get_close_matches

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 1. Populate this with all in-game skill names you care about:
# Canonical names + known fuzzy variants
KNOWN_SKILL_ALIASES = {
    "Flashy☆Landing": ["flashylanding", "flashyxlanding", "flashylandingjeez"],
    "Early Lead": ["earlylead"],
    "Escape Artist": ["escapeartist"],
    "Breath of Fresh Air": ["breathoffreshair"],
    "Straightaway Adept": ["straightawayadept"],
    "Professor of Curvature": ["professorofcurvature"],
    "Front Runner Corners": ["frontrunnercorners"],
    "Leader's Pride": ["leaderspride", "leaderspridepe"],
    # Add more as needed...
}


def normalize_candidate(raw):
    s = raw.strip()
    # remove level suffixes ("Lvl 4", "Lvl4", etc.)
    s = re.sub(r"\s*[Ll]vl\S*$", "", s)
    # remove stray single letters at end (like trailing "P")
    s = re.sub(r"\s+[A-Z]$", "", s)
    # remove stray "om" fragments
    s = s.replace(" om ", " ")
    # collapse multiple spaces
    return re.sub(r"\s{2,}", " ", s).strip()

def extract_from_image(path):
    img = Image.open(path).convert("L")

    # Crop to just the skill section (Y values are estimates)
    # You may need to fine-tune these based on your image resolution
    W, H = img.size
    skill_region = img.crop((0, int(H * 0.45), W, int(H * 0.90)))  # bottom 45% of image

    # Enhance contrast
    skill_region = ImageEnhance.Contrast(skill_region).enhance(2.5)
    skill_region = skill_region.point(lambda p: p > 180 and 255)
    skill_region = skill_region.filter(ImageFilter.SHARPEN)

    # OCR just this cropped area
    txt = pytesseract.image_to_string(skill_region)
    print("🔎 Raw OCR lines:")
    for i, line in enumerate(txt.splitlines()):
        print(f"{i+1:02}: {repr(line)}")


    # Stats: still pulled from full image
    full_txt = pytesseract.image_to_string(img)
    nums = re.findall(r"\d{3,4}", full_txt)
    stats = dict(zip(["Speed", "Stamina", "Power", "Guts", "Wit"], nums + [""] * 5))
    

    # 2️⃣ Prepare for substring matching
    # Normalize a line by stripping to lowercase alphanumeric
    def norm(s):
        return re.sub(r'[^a-z0-9]', '', s.lower())

    matched = set()
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]

    def norm(s):
        return re.sub(r'[^a-z0-9]', '', s.lower())

    for ln in lines:
        ln_norm = norm(ln)
        for canonical, aliases in KNOWN_SKILL_ALIASES.items():
            for alias in aliases:
                if alias in ln_norm:
                    matched.add(canonical)
                    break


    return {
        **stats,
        "Skills": "|".join(sorted(matched))
    }


def write_csv(rows, output):
    fields = ["Speed","Stamina","Power","Guts","Wit","Skills"]
    with open(output, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

if __name__=="__main__":
    img1, img2, out = sys.argv[1], sys.argv[2], sys.argv[3]
    rows = [extract_from_image(img1), extract_from_image(img2)]
    write_csv(rows, out)
    print("✅ CSV written to:", out)
