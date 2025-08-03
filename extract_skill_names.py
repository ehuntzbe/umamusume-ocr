"""Extract skill names from the provided HTML file.

Usage:
    python extract_skill_names.py [input_html] [output_txt]
"""
import html
import pathlib
import re
import sys

def extract(html_file: pathlib.Path) -> list[str]:
    text = html_file.read_text(encoding="utf-8", errors="ignore")
    names = re.findall(r'<span[^>]*class="skillName"[^>]*>(.*?)</span>', text, re.DOTALL)
    skills = {
        html.unescape(name.strip())
        for name in names
        if name.strip() and not name.strip().endswith("CC")
    }
    return sorted(skills)

def main() -> None:
    html_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("Uma Musume_ Pretty Derby race simulator.htm")
    out_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("skill_names.txt")
    skills = extract(html_path)
    with open(out_path, "w", encoding="utf-8") as f:
        for s in skills:
            f.write(s + "\n")
    print(f"wrote {len(skills)} skills to {out_path}")

if __name__ == "__main__":
    main()
