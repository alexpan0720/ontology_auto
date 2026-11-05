"""Inline every images/*.png referenced by article.html as a data URI.

Usage: python build_standalone.py   (writes ../article_standalone.html)
"""
import base64
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def inline(match: re.Match) -> str:
    data = base64.b64encode((ROOT / match.group(1)).read_bytes()).decode()
    return f'src="data:image/png;base64,{data}"'


def main() -> None:
    html = (ROOT / "article.html").read_text(encoding="utf-8")
    html = re.sub(r'src="(images/[^"]+\.png)"', inline, html)
    out = ROOT / "article_standalone.html"
    out.write_text(html, encoding="utf-8")
    print("wrote", out, f"{out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
