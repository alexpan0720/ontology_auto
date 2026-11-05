"""Convert the article body in article.html to a Word file for WeChat's "导入文档".

Usage: python build_docx.py   (writes ../推文-alexpan本体.docx)
"""
import pathlib
import re

from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLUE = RGBColor(0x25, 0x63, 0xEB)
GREY = RGBColor(0x94, 0xA3, 0xB8)
FONT = "Microsoft YaHei"
MONO = "Consolas"


def set_font(run, name: str = FONT) -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)


def add_runs(par, node: Tag, bold: bool = False, color: RGBColor | None = None) -> None:
    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).replace("\n", "")
            if text.strip() or text == " ":
                run = par.add_run(text)
                set_font(run)
                run.bold = bold or None
                if color:
                    run.font.color.rgb = color
        elif child.name == "b":
            add_runs(par, child, True, BLUE if "2563eb" in child.get("style", "") else color)
        elif child.name == "span" and "Consolas" in child.get("style", ""):
            run = par.add_run(child.get_text())
            set_font(run, MONO)
            run.font.size = Pt(10)
        else:
            add_runs(par, child, bold, color)


def add_image(doc: Document, img: Tag) -> None:
    pct = re.search(r"width:(\d+)%", img.get("style", ""))
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(ROOT / img["src"]), width=Cm(15.5 * int(pct.group(1)) / 100 if pct else 15.5))


def main() -> None:
    soup = BeautifulSoup((ROOT / "article.html").read_text(encoding="utf-8"), "html.parser")
    body = soup.find(id="article")
    doc = Document()
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(2.5)
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    for el in body.find_all(["p", "h2", "ul", "section"], recursive=False):
        if el.name == "h2":
            h = doc.add_heading(level=2)
            run = h.add_run(el.get_text(strip=True))
            set_font(run)
            run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
        elif el.name == "ul":
            for li in el.find_all("li"):
                add_runs(doc.add_paragraph(style="List Bullet"), li)
        elif el.name == "section" and "monospace" in el.get("style", ""):
            for line in el.get_text().splitlines():
                run = doc.add_paragraph().add_run(line)
                set_font(run, MONO)
                run.font.size = Pt(10)
        elif el.name == "section":
            for p in el.find_all("p"):
                par = doc.add_paragraph()
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                add_runs(par, p, color=BLUE if "2563eb" in p.get("style", "") else None)
        elif el.find("img"):
            add_image(doc, el.find("img"))
        else:
            par = doc.add_paragraph()
            caption = "#94a3b8" in el.get("style", "")
            if caption:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_runs(par, el, color=GREY if caption else None)
            if caption:
                for run in par.runs:
                    run.font.size = Pt(9)

    out = ROOT / "推文-alexpan本体.docx"
    doc.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
