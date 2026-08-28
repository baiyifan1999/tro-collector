import os
import re

import pdfplumber
import pytesseract
from pdf2image import convert_from_path

from collectors.cleaner import ensure_column
from collectors.logger import collector_logger as logger
from models.database import get_connection

PLATFORM_PATTERN = re.compile(r"\b(Amazon|eBay|Wish|Walmart)\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://\S+")
# Matches a pure row-number cell: digits only, or common header labels
_HEADER_CELL = re.compile(r"^(no\.?|#|\d+)$", re.IGNORECASE)


def detect_pdf_type(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0] if pdf.pages else None
        text = first_page.extract_text() or "" if first_page else ""
    return "text" if len(text.strip()) > 50 else "scanned"


def _cell(value):
    return (value or "").strip()


def parse_text_pdf(pdf_path):
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if not row:
                        continue

                    first = _cell(row[0])

                    # Skip header rows
                    if _HEADER_CELL.match(first) and first.lower() not in ("", ):
                        # pure digit means it's a data row number, not a header
                        if not first.isdigit():
                            continue

                    # Continuation row: first cell empty → merge into previous entry
                    if first == "" or row[0] is None:
                        if results:
                            # Append non-empty cells to the last result's fields
                            extra = " ".join(_cell(c) for c in row[1:] if _cell(c))
                            if extra:
                                results[-1]["store_name"] = (
                                    results[-1]["store_name"] + "\n" + extra
                                ).strip()
                        continue

                    # Normal data row: expect [No., Store Name, Platform, URL]
                    cols = [_cell(c) for c in row]
                    # col 0 is the row number; data starts at 1
                    store_name = cols[1] if len(cols) > 1 else ""
                    platform = cols[2] if len(cols) > 2 else ""
                    url = cols[3] if len(cols) > 3 else ""

                    if not store_name:
                        continue

                    results.append(
                        {"store_name": store_name, "platform": platform, "url": url}
                    )

    return results


def parse_scanned_pdf(pdf_path):
    results = []
    images = convert_from_path(pdf_path, dpi=200)

    for image in images:
        raw_text = pytesseract.image_to_string(image)
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        for line in lines:
            url_match = URL_PATTERN.search(line)
            platform_match = PLATFORM_PATTERN.search(line)

            url = url_match.group(0) if url_match else ""
            platform = platform_match.group(0).capitalize() if platform_match else ""

            if url:
                # store_name is the text that appears before the URL on the same line
                store_name = line[: url_match.start()].strip()
            elif platform:
                store_name = line[: platform_match.start()].strip()
            else:
                continue

            if not store_name:
                continue

            results.append(
                {"store_name": store_name, "platform": platform, "url": url}
            )

    return results


def _lookup_source_doc_id(cursor, case_id, pdf_path):
    # Derive the MinIO object_name from the local path:
    # /tmp/tro_pdfs/case_{case_id}/{doc_id}.pdf → cases/case_{case_id}/{doc_id}.pdf
    filename = os.path.basename(pdf_path)
    minio_path = f"cases/case_{case_id}/{filename}"
    cursor.execute(
        "SELECT id FROM documents WHERE case_id = %s AND minio_path = %s LIMIT 1",
        (case_id, minio_path),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def parse_schedule_a(pdf_path, case_id):
    try:
        pdf_type = detect_pdf_type(pdf_path)
        logger.info(f"Detected PDF type '{pdf_type}' for {pdf_path}")

        if pdf_type == "text":
            entries = parse_text_pdf(pdf_path)
        else:
            entries = parse_scanned_pdf(pdf_path)

    except Exception as e:
        logger.error(f"Failed to parse {pdf_path}: {e}")
        return []

    if not entries:
        logger.warning(f"No defendants extracted from {pdf_path}")
        return []

    conn = get_connection()
    cursor = conn.cursor()
    setup_cursor = conn.cursor()

    ensure_column(setup_cursor, "defendants", "cleaned_name", "cleaned_name TEXT")
    ensure_column(setup_cursor, "defendants", "is_valid", "is_valid TINYINT DEFAULT 1")
    ensure_column(setup_cursor, "defendants", "platform", "platform VARCHAR(100)")
    ensure_column(setup_cursor, "defendants", "source_doc_id", "source_doc_id INT")
    conn.commit()
    setup_cursor.close()

    source_doc_id = _lookup_source_doc_id(cursor, case_id, pdf_path)

    saved = 0
    for entry in entries:
        store_name = entry.get("store_name", "").strip()
        if not store_name:
            continue

        cursor.execute(
            """
            INSERT INTO defendants
                (case_id, defendant_name, cleaned_name, is_valid, platform, source_doc_id)
            VALUES (%s, %s, %s, 1, %s, %s)
            """,
            (
                case_id,
                store_name,
                store_name,
                entry.get("platform", ""),
                source_doc_id,
            ),
        )
        saved += 1

    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"parse_schedule_a: wrote {saved} defendants for case {case_id}")
    return saved
