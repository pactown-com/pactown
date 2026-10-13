"""Build a portable A4 PDF from the canonical Polish document.

Requires Pandoc, Chrome/Chromium and requirements-docs.txt; makes no HTTP requests.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import quote, unquote, urlsplit

from pypdf import PdfReader, PdfWriter


def build(root: Path, output: Path | None, revision: str | None,
          config_path: Path | None = None) -> Path:
    config_path = config_path or root / "docs/pdf-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    document_path = root / config["source"]
    raw = document_path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError("Document metadata missing")
    metadata, content = raw[4:].split("\n---\n", 1)
    source = json.loads(metadata)
    revision = revision or subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    # Accept only a real immutable commit; links cannot be accidentally tied to a branch.
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--verify", revision + "^{commit}"], text=True).strip()
    browser = os.environ.get("CHROMIUM_PATH") or shutil.which("google-chrome") or shutil.which("chromium")
    if not browser:
        raise RuntimeError("Set CHROMIUM_PATH to a Chrome/Chromium executable")
    output = output or root / config["output"]
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    parsed = subprocess.run(["pandoc", "--from=markdown", "--to=json"],
                            input=content, capture_output=True, text=True, check=True)
    ast = json.loads(parsed.stdout)

    def portable(node):
        if isinstance(node, dict):
            if node.get("t") in ("Link", "Image"):
                target = node["c"][-1][0]
                url = urlsplit(target)
                if not url.scheme and url.path:
                    path = (document_path.parent / unquote(url.path)).resolve()
                    relative = path.relative_to(root)
                    if not path.is_file():
                        raise ValueError("Missing document asset or link: " + target)
                    if node["t"] == "Link":
                        # Validate the link against the chosen source commit, not a dirty filesystem.
                        subprocess.run(["git", "-C", str(root), "cat-file", "-e",
                                        revision + ":" + relative.as_posix()], check=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                        node["c"][-1][0] = ("https://github.com/" + config["repository"]
                            + "/blob/" + revision + "/" + quote(relative.as_posix())
                            + ("#" + url.fragment if url.fragment else ""))
                    else:
                        mime = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg"}[path.suffix]
                        node["c"][-1][0] = "data:" + mime + ";base64," + base64.b64encode(path.read_bytes()).decode()
            for value in node.values():
                portable(value)
        elif isinstance(node, list):
            for value in node:
                portable(value)

    portable(ast)
    # The Markdown title remains visible in source; the PDF has its own cover.
    if ast["blocks"] and ast["blocks"][0].get("t") == "Header":
        ast["blocks"].pop(0)
    if config.get("recipient_lines"):
        recipient = '<div class="recipient">' + ''.join(
            '<p>' + html.escape(line) + '</p>' for line in config["recipient_lines"]) + '</div>'
        ast["blocks"].insert(0, {"t": "RawBlock", "c": ["html", recipient]})
    stylesheet = (root / config.get("css", "docs/media/print.css")).resolve()
    stylesheet.relative_to(root)
    toc_args = ["--toc", "--toc-depth=2"] if config.get("toc", True) else []
    with tempfile.TemporaryDirectory(prefix=".docs-pdf-", dir=output.parent) as temp:
        work = Path(temp)
        html = work / "document.html"
        subprocess.run(["pandoc", "--from=json", "--to=html5", "--standalone", "--mathml",
                        "--embed-resources", "--fail-if-warnings", *toc_args,
                        "--css=" + str(stylesheet),
                        "--metadata=title:" + config["title"],
                        "--metadata=subtitle:" + config["subtitle"],
                        "--metadata=author:" + config["author"],
                        "--metadata=date:" + source["updated"],
                        "--output=" + str(html)], input=json.dumps(ast), text=True, check=True)
        raw_pdf = work / "raw.pdf"
        proc = subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-sandbox",
                               "--no-pdf-header-footer", "--user-data-dir=" + str(work / "browser"),
                               "--print-to-pdf=" + str(raw_pdf), html.as_uri()],
                              capture_output=True, timeout=90)
        if proc.returncode or not raw_pdf.is_file():
            raise RuntimeError("PDF rendering failed; browser exit " + str(proc.returncode))
        reader = PdfReader(raw_pdf)
        if len(reader.pages) < 3:
            raise ValueError("Incomplete PDF")
        writer = PdfWriter(clone_from=reader)
        writer.add_metadata({"/Title": config["title"], "/Author": config["author"],
                             "/Subject": "Dokumentacja PL; źródła: " + revision,
                             "/Keywords": "Pactown, Markdown, architektura, dokumentacja"})
        final = work / "final.pdf"
        with final.open("wb") as stream:
            writer.write(stream)
        final.replace(output)
        print(f"PDF: {len(reader.pages)} pages; {output.stat().st_size} bytes; {output}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--revision", default=os.environ.get("DOCS_GIT_REF"))
    parser.add_argument("--config", type=Path, help="Alternative document/PDF configuration")
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.output, args.revision, args.config)
