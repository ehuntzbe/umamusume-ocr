"""Generate a UmaLator simulator URL from OCR CSV data.

This refactors the previous web form automation by generating a
share link compatible with the local UmaLator UI.

The share link format and default parameters are derived from the
`serialize` function in the UmaLator project and the data structures
from `uma-skill-tools`, both by alpha123 and licensed under
GPL-3.0-or-later.
"""

from __future__ import annotations

import base64
import csv
import gzip
import json
import os
import subprocess
import sys
import urllib.parse
import webbrowser
import http.server
import threading
from functools import partial
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

REPO_URL_TOOLS = "https://github.com/alpha123/uma-tools"
REPO_URL_SKILL_TOOLS = "https://github.com/alpha123/uma-skill-tools"

EXTERNAL_DIR = Path(__file__).with_name("external")
TOOLS_DIR = EXTERNAL_DIR / "uma-tools"
SKILL_TOOLS_DIR = EXTERNAL_DIR / "uma-skill-tools"

# Defaults pulled from UmaLator source
DEFAULT_COURSE_ID = 10606  # Tokyo Turf 1600m (global)
DEFAULT_NSAMPLES = 500
DEFAULT_USE_POS_KEEP = True

DEFAULT_RACEDEF = {
    "mood": 2,
    "ground": 1,  # GroundCondition.Good
    "weather": 1,  # Weather.Sunny
    "season": 1,  # Season.Spring
    "time": 2,  # Time.Midday
    "grade": 100,  # Grade.G1
}

@dataclass
class Horse:
    speed: int
    stamina: int
    power: int
    guts: int
    wisdom: int
    skills: List[str]
    outfitId: str = ""
    strategy: str = "Senkou"
    distanceAptitude: str = "S"
    surfaceAptitude: str = "A"
    strategyAptitude: str = "A"

    def to_json(self) -> Dict:
        return {
            "outfitId": self.outfitId,
            "speed": self.speed,
            "stamina": self.stamina,
            "power": self.power,
            "guts": self.guts,
            "wisdom": self.wisdom,
            "strategy": self.strategy,
            "distanceAptitude": self.distanceAptitude,
            "surfaceAptitude": self.surfaceAptitude,
            "strategyAptitude": self.strategyAptitude,
            "skills": self.skills,
        }


def ensure_repo(url: str, path: Path) -> None:
    """Clone the repository if it does not exist."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", url, str(path)], check=True)


def load_skill_mapping() -> Dict[str, str]:
    ensure_repo(REPO_URL_TOOLS, TOOLS_DIR)
    skill_file = TOOLS_DIR / "umalator-global" / "skillnames.json"
    with open(skill_file, encoding="utf-8") as f:
        data = json.load(f)
    mapping = {}
    for skill_id, names in data.items():
        for name in names:
            mapping[name.lower()] = skill_id
    return mapping


def parse_horse(row: Dict[str, str], skill_map: Dict[str, str]) -> Horse:
    skills = []
    for name in row.get("Skills", "").split("|"):
        key = name.strip().lower()
        if not key:
            continue
        skill_id = skill_map.get(key)
        if skill_id:
            skills.append(skill_id)
    return Horse(
        speed=int(row.get("Speed", 0) or 0),
        stamina=int(row.get("Stamina", 0) or 0),
        power=int(row.get("Power", 0) or 0),
        guts=int(row.get("Guts", 0) or 0),
        wisdom=int(row.get("Wit", 0) or 0),
        skills=skills,
    )


def build_share_hash(uma1: Horse, uma2: Horse) -> str:
    payload = {
        "courseId": DEFAULT_COURSE_ID,
        "nsamples": DEFAULT_NSAMPLES,
        "usePosKeep": DEFAULT_USE_POS_KEEP,
        "racedef": DEFAULT_RACEDEF,
        "uma1": uma1.to_json(),
        "uma2": uma2.to_json(),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    zipped = gzip.compress(raw)
    return urllib.parse.quote(base64.b64encode(zipped).decode("ascii"))


def csv_to_hash(csv_path: Path) -> str:
    """Return the encoded share hash for two rows of CSV data."""
    skill_map = load_skill_mapping()
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 2:
        raise ValueError("CSV must contain at least two rows")
    uma1 = parse_horse(rows[0], skill_map)
    uma2 = parse_horse(rows[1], skill_map)
    return build_share_hash(uma1, uma2)


def _prepare_static_assets() -> Path:
    """Ensure UmaLator static assets are available and return the base dir."""
    ensure_repo(REPO_URL_TOOLS, TOOLS_DIR)
    return TOOLS_DIR / "umalator-global"


def start_server() -> tuple[http.server.ThreadingHTTPServer, threading.Thread, int]:
    """Serve the UmaLator UI over HTTP and return server and port."""
    serve_dir = _prepare_static_assets()

    class UmaToolsHandler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:  # type: ignore[override]
            # Strip any query parameters
            path = urllib.parse.urlparse(path).path

            if path.startswith("/uma-tools/"):
                rel = path[len("/uma-tools/") :]
                return str(TOOLS_DIR / rel)

            first = path.lstrip("/").split("/", 1)[0]
            if first in {"icons", "courseimages", "fonts", "strings"}:
                rel = path.lstrip("/")
                return str(TOOLS_DIR / rel)

            if path.lstrip("/") in {"skill_meta.json", "umas.json", "icons.json"}:
                return str(TOOLS_DIR / path.lstrip("/"))

            return super().translate_path(path)

    handler = partial(UmaToolsHandler, directory=str(serve_dir))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, httpd.server_port


def main(argv: List[str]) -> int:
    """Start the local server and interactively load CSV files.

    A CSV file may be supplied on the command line for an initial load. While
    the server is running, users can enter additional CSV paths to reload the
    simulator without restarting the script. Pressing enter on an empty line
    exits the program.
    """

    csv_path: Path | None = Path(argv[1]) if len(argv) > 1 else None
    httpd, thread, port = start_server()
    try:
        while True:
            if csv_path is None:
                user_input = input("CSV file path (blank to quit): ").strip()
                if not user_input:
                    break
                csv_path = Path(user_input)
            try:
                share_hash = csv_to_hash(csv_path)
            except Exception as exc:  # pragma: no cover - interactive error
                print(f"Failed to load {csv_path}: {exc}")
            else:
                url = f"http://127.0.0.1:{port}/index.html#{share_hash}"
                print(url)
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            user_input = input(
                "Reload with another CSV? (path or blank to quit): "
            ).strip()
            if not user_input:
                break
            csv_path = Path(user_input)
    finally:
        httpd.shutdown()
        thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
