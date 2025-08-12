# umamusume-ocr

## Purpose

Convert Uma Musume race screenshots into structured data and open them in the UmaLator simulator.

## Installation
 
The tools require Python 3.10+, Git, and a few system libraries.

### Linux / WSL

```bash
# 1. Install system packages (Debian/Ubuntu)
sudo apt update
sudo apt install -y git python3 python3-pip python3-tk libgl1
```

### macOS

```bash
# 1. Install prerequisites with Homebrew
brew update
brew install git python@3 tcl-tk
```

### Windows

```powershell
# 1. Install Git and Python with winget
winget install -e --id Git.Git
winget install -e --id Python.Python.3.10
```

### Common steps

```bash
# 2. Clone this repository
git clone https://github.com/ehuntzbe/umamusume-ocr.git
cd umamusume-ocr

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env  # Windows: copy .env.example .env
# edit .env to set LOG_LEVEL=INFO or enable LOCAL_WEB_LOGGING=true
```

### GUI alternative

1. Download and install [Git](https://git-scm.com/downloads) and [Python 3.10+](https://www.python.org/downloads/) using their graphical installers. On Windows, ensure "Add Python to PATH" is checked.
2. Visit [https://github.com/ehuntzbe/umamusume-ocr](https://github.com/ehuntzbe/umamusume-ocr) and either clone with GitHub Desktop or click **Code > Download ZIP**, then extract the archive.
3. Open a terminal or command prompt in the project folder and run `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` with your file manager and edit it in a text editor to adjust `LOG_LEVEL` or `LOCAL_WEB_LOGGING`.

### Environment variables

The scripts read configuration from `.env` in the project root. Available settings include:

- `LOG_LEVEL` — logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `LOCAL_WEB_LOGGING` — set to `true` to enable request logging for the local web server used by `uma_csv_to_url.py`

## Usage

### Command line

1. Place race result screenshots in the `data` directory (`data/` on Linux/macOS, `data\` on Windows).
2. Run the OCR script:

   ```bash
   python uma_ocr_to_csv.py
   ```

   The script writes `data/runners.csv` and moves processed images to `data/processed/`.
3. Build an UmaLator share link:

   ```bash
   python uma_csv_to_url.py
   ```

   A GUI lists the runners in `data/runners.csv`. Select two entries and the tool opens your browser to a locally served copy of UmaLator preloaded with those runners. Copy the portion of the URL after `index.html` to share or append to the public instance at https://alpha123.github.io/uma-tools/umalator-global/ as long as both versions remain in sync.

### Clipboard watcher (Windows)

For a faster workflow on Windows, you can monitor the clipboard for new screenshots:

```bash
python uma_clipboard_ocr.py
```

Use `Win+Shift+S` to capture a region of the screen. When an image is copied to the clipboard, the script saves it, extracts stats and skills, appends the data to `data/runners.csv`, and moves the image to `data/processed/` automatically.

### GUI alternative

1. Place race result screenshots in the `data` folder using your file manager.
2. Double-click `uma_ocr_to_csv.py`. A terminal window appears and processes the images.
3. After the CSV is created, double-click `uma_csv_to_url.py`. The runner selection window appears, and when you choose two runners, your browser opens a locally hosted UmaLator page with those runners preloaded. You can copy the segment of the URL after `index.html` and append it to the public UmaLator site if the repositories are in sync.

## How it works

- `uma_ocr_to_csv.py` uses RapidOCR to detect text in screenshots, normalizes the results, and fuzzy-matches them against canonical names and skills from the `uma-tools` repository. Each screenshot's stats and skills are appended to a CSV.
- `uma_csv_to_url.py` reads that CSV, maps skill names to IDs from `uma-skill-tools`, serves UmaLator's static assets locally, and provides a Tk GUI for selecting two runners before constructing a share URL. The URL path after `index.html` is compatible with the public UmaLator instance at https://alpha123.github.io/uma-tools/umalator-global/ when this repository remains in sync with upstream.

## Licensing and Dependencies

This project leverages two related open-source repositories:

- [uma-tools](https://github.com/alpha123/uma-tools) for general Uma Musume data utilities
- [uma-skill-tools](https://github.com/alpha123/uma-skill-tools) for skill-related processing

Please review and comply with the licenses provided by those upstream projects (for example, `uma-skill-tools` is GPLv3). This repository is itself distributed under the [GNU General Public License v3](LICENSE), and contributions must remain compatible with both the GPLv3 and the licenses of the above repositories.

## Code Generation

Most of the source code in this repository was generated with the help of OpenAI's ChatGPT Codex and subsequently refined.
