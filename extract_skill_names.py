"""Extract skill names from the provided HTML file.

Usage:
    python extract_skill_names.py [input_html] [output_txt]
"""
import html
import logging
import os
import pathlib
import re
import sys

from dotenv import load_dotenv

ENV_PATH = pathlib.Path(__file__).with_name(".env")
load_dotenv(ENV_PATH)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)
logger.debug("Environment loaded from %s with log level %s", ENV_PATH, LOG_LEVEL)

def extract(html_file: pathlib.Path) -> list[str]:
    logger.debug("Extracting from %s", html_file)
    try:
        text = html_file.read_text(encoding="utf-8", errors="ignore")
        logger.debug("Read %d characters from HTML", len(text))
    except FileNotFoundError:
        logger.error("HTML file not found: %s", html_file)
        return []
    names = re.findall(r'<span[^>]*class="skillName"[^>]*>(.*?)</span>', text, re.DOTALL)
    logger.debug("Found %d raw skill entries", len(names))
    skills = {
        html.unescape(name.strip())
        for name in names
        if name.strip() and not name.strip().endswith("CC")
    }
    logger.info("Found %d unique skills", len(skills))
    return sorted(skills)

def main() -> None:
    html_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("Uma Musume_ Pretty Derby race simulator.htm")
    out_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("skill_names.txt")
    logger.info("Extracting skills from %s", html_path)
    skills = extract(html_path)
    if not skills:
        logger.warning("No skills extracted; check input file")
    with open(out_path, "w", encoding="utf-8") as f:
        for s in skills:
            f.write(s + "\n")
    logger.info("Wrote %d skills to %s", len(skills), out_path)

if __name__ == "__main__":
    main()
