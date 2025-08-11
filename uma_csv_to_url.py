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
import re
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

from dotenv import load_dotenv
from rapidfuzz import process, fuzz

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

load_dotenv(Path(__file__).with_name(".env"))

LOCAL_WEB_LOGGING = os.getenv("LOCAL_WEB_LOGGING", "").strip().lower() == "true"

@dataclass
class Horse:
    name: str
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
            "name": self.name,
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
    mapping: Dict[str, str] = {}
    for skill_id, names in data.items():
        for name in names:
            key = name.lower()
            existing = mapping.get(key)
            if existing is None or (
                existing.startswith("9") and not skill_id.startswith("9")
            ):
                mapping[key] = skill_id
    return mapping


# --- normalization and uma lookup ------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_uma_lookup() -> tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
    """Return mappings for runner names and epithets."""
    ensure_repo(REPO_URL_TOOLS, TOOLS_DIR)
    uma_file = TOOLS_DIR / "umalator-global" / "umas.json"
    with open(uma_file, encoding="utf-8") as f:
        data = json.load(f)
    name_map: Dict[str, str] = {}
    outfit_map: Dict[str, Dict[str, str]] = {}
    for v in data.values():
        names = [n for n in v.get("name", []) if n]
        if not names:
            continue
        canonical = names[-1]
        name_map[_norm(canonical)] = canonical
        epi_dict: Dict[str, str] = {}
        for outfit_id, epithet in v.get("outfits", {}).items():
            epi_dict[_norm(epithet)] = outfit_id
        outfit_map[canonical] = epi_dict
    return name_map, outfit_map


UMA_NAME_MAP, UMA_OUTFIT_MAP = load_uma_lookup()


def parse_horse(row: Dict[str, str], skill_map: Dict[str, str]) -> Horse:
    skills: List[str] = []
    for name in row.get("Skills", "").split("|"):
        key = name.strip().lower()
        if not key:
            continue
        skill_id = skill_map.get(key)
        if skill_id:
            skills.append(skill_id)
    name_input = row.get("Name", "")
    epithet_input = row.get("Epithet", "")
    canonical_name = name_input
    outfit_id = ""
    if name_input:
        key = _norm(name_input)
        match = process.extractOne(key, UMA_NAME_MAP.keys(), scorer=fuzz.ratio)
        if match:
            canonical_name = UMA_NAME_MAP[match[0]]
    ep_map = UMA_OUTFIT_MAP.get(canonical_name, {})
    if epithet_input and ep_map:
        key = _norm(epithet_input)
        match = process.extractOne(key, ep_map.keys(), scorer=fuzz.ratio)
        if match:
            outfit_id = ep_map[match[0]]
    return Horse(
        name=canonical_name,
        outfitId=outfit_id,
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


def csv_to_hash(rows: List[Dict[str, str]]) -> str:
    """Return the encoded share hash for two rows of runner data."""
    if len(rows) < 2:
        raise ValueError("Need at least two rows")
    skill_map = load_skill_mapping()
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

        def log_message(self, format: str, *args: object) -> None:  # type: ignore[override]
            if LOCAL_WEB_LOGGING:
                super().log_message(format, *args)

    handler = partial(UmaToolsHandler, directory=str(serve_dir))

    class QuietServer(http.server.ThreadingHTTPServer):
        """HTTP server that suppresses common connection errors."""

        daemon_threads = True

        def handle_error(self, request, client_address):  # type: ignore[override]
            exc = sys.exc_info()[1]
            if isinstance(exc, ConnectionError):
                return
            super().handle_error(request, client_address)

    httpd = QuietServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, httpd.server_port


def launch_gui(
    runners: List[Dict[str, str]],
    httpd: http.server.ThreadingHTTPServer,
    thread: threading.Thread,
    port: int,
) -> None:
    """Display a runner selection GUI and handle user interaction."""

    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("UmaLator Runner Selector")

    columns = ("Runner", "Speed", "Stamina", "Power", "Guts", "Wit", "Skills")

    def setup_tree(parent: tk.Misc, label: str) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        tree.grid(row=1, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        vsb.grid(row=1, column=1, sticky="ns")
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        hsb.grid(row=2, column=0, sticky="ew")
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        for col in columns:
            tree.heading(col, text=col)
        tree.column("Runner", width=200, anchor="w")
        for col in ("Speed", "Stamina", "Power", "Guts", "Wit"):
            tree.column(col, width=60, anchor="center")
        tree.column("Skills", width=300, anchor="w")
        return tree

    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(0, weight=1)

    tree_left = setup_tree(root, "Runner 1")
    tree_left.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
    tree_right = setup_tree(root, "Runner 2")
    tree_right.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

    def runner_values(row: Dict[str, str]) -> List[str]:
        title = f"{row.get('Epithet', '')} {row.get('Name', '')}".strip()
        skills = [s.strip() for s in row.get("Skills", "").split("|") if s.strip()]
        skill_text = ", ".join(skills)
        return [
            title,
            row.get("Speed", ""),
            row.get("Stamina", ""),
            row.get("Power", ""),
            row.get("Guts", ""),
            row.get("Wit", ""),
            skill_text,
        ]

    for idx, row in enumerate(runners):
        values = runner_values(row)
        tree_left.insert("", "end", iid=str(idx), values=values)
        tree_right.insert("", "end", iid=str(idx), values=values)

    def on_submit() -> None:
        sel1 = tree_left.selection()
        sel2 = tree_right.selection()
        if not sel1 or not sel2:
            messagebox.showerror("Selection Error", "Please select two runners.")
            return
        idx1 = int(sel1[0])
        idx2 = int(sel2[0])
        share_hash = csv_to_hash([runners[idx1], runners[idx2]])
        url = f"http://127.0.0.1:{port}/index.html#{share_hash}"
        print(f"Umalator is now open with runners #{idx1+1} and #{idx2+1}.")
        try:
            webbrowser.open_new_tab(url)
        except Exception:
            pass

    btn = ttk.Button(root, text="Open in UmaLator", command=on_submit)
    btn.grid(row=1, column=0, columnspan=2, pady=5)

    def on_close() -> None:
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    def check_server() -> None:
        if not thread.is_alive():
            root.destroy()
        else:
            root.after(1000, check_server)

    root.after(1000, check_server)
    root.mainloop()


def main(argv: List[str]) -> int:
    data_dir = Path(__file__).with_name("data")
    csv_path = data_dir / "runners.csv"
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            runners = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"No runner data found at {csv_path}")
        return 1
    if len(runners) < 2:
        print("Need at least two runners to compare")
        return 1

    httpd, thread, port = start_server()
    try:
        launch_gui(runners, httpd, thread, port)
    finally:
        httpd.shutdown()
        thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
