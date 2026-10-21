"""Build the PDF of each report from its Markdown (Markdown -> HTML -> headless Chrome).

    python rapport/build_pdf.py                       # every *.md of rapport/
    python rapport/build_pdf.py rapport/rapport_M7_catalogue_local_FR.md

Needs the `markdown` package and Chrome (or Edge). Images are referenced relative to rapport/.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
BROWSERS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
]

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.5;
       color: #1d1d27; }
h1 { font-size: 22pt; margin: 0 0 6px; color: #2b2560; }
h2 { font-size: 15pt; margin: 26px 0 8px; padding-bottom: 4px; border-bottom: 2px solid #e4e2f3;
     color: #2b2560; page-break-after: avoid; }
h3 { font-size: 12pt; margin: 18px 0 6px; color: #3b3486; page-break-after: avoid; }
h4 { font-size: 10.5pt; margin: 14px 0 4px; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
a { color: #3b3486; text-decoration: none; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 9pt; background: #f2f1f8;
       padding: 1px 4px; border-radius: 3px; }
pre { background: #f7f7fb; border: 1px solid #e6e5f0; border-left: 4px solid #4b3f9e; border-radius: 6px;
      padding: 10px 12px; overflow: hidden; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 7.5pt; line-height: 1.2; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9pt;
        page-break-inside: auto; }
th { background: #2b2560; color: white; text-align: left; padding: 5px 7px; }
td { border-bottom: 1px solid #e4e2f3; padding: 4px 7px; vertical-align: top; }
tr { page-break-inside: avoid; }
tr:nth-child(even) td { background: #fafafe; }
blockquote { margin: 8px 0; padding: 6px 12px; border-left: 4px solid #b9b3e6; background: #f7f6fd; }
img { max-width: 100%; max-height: 120mm; display: block; margin: 8px auto; border-radius: 6px; }
td img { max-height: 90mm; }
hr { border: none; border-top: 1px solid #e4e2f3; margin: 18px 0; }
"""


def browser() -> Path:
    for path in BROWSERS:
        if path.is_file():
            return path
    sys.exit("Chrome / Edge not found: install one or add its path to BROWSERS")


def build(md_path: Path) -> Path:
    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), md_path.stem)
    html = (
        f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{title}</title>'
        f'<base href="{md_path.parent.as_uri()}/"><style>{CSS}</style></head><body>{body}</body></html>'
    )
    pdf = md_path.with_suffix(".pdf")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "report.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                str(browser()),
                "--headless=new",
                "--disable-gpu",
                "--allow-file-access-from-files",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
    return pdf


def main() -> None:
    targets = [Path(a).resolve() for a in sys.argv[1:]] or sorted(HERE.glob("*.md"))
    for md_path in targets:
        print(f"{md_path.name} -> {build(md_path).name}")


if __name__ == "__main__":
    main()
