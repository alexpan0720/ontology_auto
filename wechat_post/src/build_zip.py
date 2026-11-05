"""Pack the Word file, preview page and every image used by article.html.

Usage: python build_zip.py   (run after build_standalone.py and build_docx.py)
"""
import pathlib
import re
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> None:
    html = (ROOT / "article.html").read_text(encoding="utf-8")
    images = re.findall(r'src="(images/[^"]+\.png)"', html)
    out = ROOT / "推文素材包-alexpan本体.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT / "推文-alexpan本体.docx", "推文-alexpan本体.docx")
        z.write(ROOT / "article_standalone.html", "推文预览.html")
        for src in images:
            z.write(ROOT / src, "图片/" + src.split("/")[1])
    print("wrote", out, len(images), "images", f"{out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
