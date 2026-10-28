# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Turn an uploaded document into plain-text sections, then into LLM-sized chunks.

Each format keeps the structure that carries meaning: a PDF page number, a
Word table's header beside each value, a spreadsheet row as ``header: value``
pairs. A data dictionary is almost always a table, and a value read without its
column header ("1", "有效") defines nothing.
"""

from __future__ import annotations

import csv
import io
from pathlib import PurePath

SUPPORTED_SUFFIXES = (".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md")

#: Characters per chunk sent to the extractor: large enough to keep a section
#: and its definitions together, small enough for a fast, focused LLM call.
CHUNK_CHARS = 6000
#: Rows of one spreadsheet read at most; a dictionary longer than this is rare
#: and the excess would only be truncated by the chunk budget anyway.
MAX_SHEET_ROWS = 5000


class DocumentError(ValueError):
    """The upload cannot be read; the message is user-facing."""


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentError("无法识别文件编码，请另存为 UTF-8 后再上传")


def _clean(value: object) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _rows_to_lines(rows: list[list[str]]) -> list[str]:
    """Rows of a table as ``header: value; ...`` lines, header taken from the first row."""
    rows = [[_clean(c) for c in row] for row in rows]
    rows = [row for row in rows if any(row)]
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    if not body:
        return ["; ".join(c for c in header if c)]
    lines = []
    for row in body:
        pairs = [
            f"{header[i] if i < len(header) and header[i] else f'列{i + 1}'}: {cell}"
            for i, cell in enumerate(row)
            if cell
        ]
        if pairs:
            lines.append("; ".join(pairs))
    return lines


def _pdf(data: bytes) -> list[str]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, KeyError) as exc:
        raise DocumentError(f"PDF 文件无法读取：{exc}") from exc
    sections = [
        f"[第 {i} 页]\n{text.strip()}"
        for i, text in enumerate(pages, 1)
        if text.strip()
    ]
    if not sections:
        raise DocumentError("PDF 中没有可提取的文字（可能是扫描件），请上传文字版文档")
    return sections


def _docx(data: bytes) -> list[str]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - python-docx raises several types
        raise DocumentError(f"Word 文件无法读取（仅支持 .docx）：{exc}") from exc

    sections: list[str] = []
    paragraphs: list[str] = []
    # Walk the body in document order so a table stays next to the heading
    # that explains it.
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = Paragraph(child, document).text.strip()
            if text:
                paragraphs.append(text)
        elif tag == "tbl":
            if paragraphs:
                sections.append("\n".join(paragraphs))
                paragraphs = []
            table = Table(child, document)
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            lines = _rows_to_lines(rows)
            if lines:
                sections.append("[表格]\n" + "\n".join(lines))
    if paragraphs:
        sections.append("\n".join(paragraphs))
    return sections


def _xlsx(data: bytes) -> list[str]:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - openpyxl raises several types
        raise DocumentError(f"Excel 文件无法读取：{exc}") from exc
    sections = []
    for sheet in workbook.worksheets:
        rows = []
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i >= MAX_SHEET_ROWS:
                break
            rows.append(list(row))
        lines = _rows_to_lines(rows)
        if lines:
            sections.append(f"[工作表 {sheet.title}]\n" + "\n".join(lines))
    workbook.close()
    return sections


def _csv(data: bytes) -> list[str]:
    text = _decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))[:MAX_SHEET_ROWS]
    lines = _rows_to_lines(rows)
    return ["\n".join(lines)] if lines else []


def extract_sections(file_name: str, data: bytes) -> list[str]:
    """The document's text as sections, in reading order."""
    suffix = PurePath(file_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise DocumentError(
            "不支持的文件类型，请上传 PDF、Word（.docx）、Excel（.xlsx）、CSV、TXT 或 Markdown 文件"
        )
    if not data:
        raise DocumentError("文件是空的")
    if suffix == ".pdf":
        sections = _pdf(data)
    elif suffix == ".docx":
        sections = _docx(data)
    elif suffix in (".xlsx", ".xlsm"):
        sections = _xlsx(data)
    elif suffix == ".csv":
        sections = _csv(data)
    else:
        sections = [_decode(data)]
    sections = [s.strip() for s in sections if s and s.strip()]
    if not sections:
        raise DocumentError("文件中没有可提取的文字")
    return sections


def chunk(sections: list[str], max_chars: int = CHUNK_CHARS) -> list[str]:
    """Pack *sections* into chunks of at most *max_chars*, splitting long ones by line."""
    pieces: list[str] = []
    for section in sections:
        if len(section) <= max_chars:
            pieces.append(section)
            continue
        current = ""
        for line in section.split("\n"):
            while len(line) > max_chars:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.append(line[:max_chars])
                line = line[max_chars:]
            if current and len(current) + 1 + len(line) > max_chars:
                pieces.append(current)
                current = ""
            current = f"{current}\n{line}" if current else line
        if current:
            pieces.append(current)

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + 2 + len(piece) > max_chars:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks
