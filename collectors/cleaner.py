import re

from models.database import get_connection

PLACEHOLDER_PATTERNS = [
    r"Does\s+\d+",
    r"Schedule A",
    r"Schedule B",
    r"Exhibit 1",
    r"Exhibit 2",
    r"Partnerships and Unincorporated",
    r"Individuals, Corporations",
]


def is_placeholder(name):
    if not name:
        return False

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return True

    return False


def normalize_name(name):
    if name is None:
        return name

    cleaned = name.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    cleaned = re.sub(r"\bCompany Limited\b", "Co., Ltd.", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bCo\.,?\s*Ltd\.?\b", "Co., Ltd.", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(
        r"\bIncorporated\b|\bInc\.?(?![A-Za-z])",
        "Inc.",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\bL\.L\.C\.?(?![A-Za-z])|\bLLC\b",
        "LLC",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned


def ensure_column(cursor, table, column, ddl):
    cursor.execute(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    (count,) = cursor.fetchone()

    if count == 0:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def clean_defendants():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    setup_cursor = conn.cursor()
    ensure_column(setup_cursor, "defendants", "is_valid", "is_valid TINYINT DEFAULT 1")
    ensure_column(setup_cursor, "defendants", "cleaned_name", "cleaned_name TEXT")
    conn.commit()
    setup_cursor.close()

    cursor.execute("SELECT id, defendant_name FROM defendants")
    rows = cursor.fetchall()

    valid_count = 0
    filtered_count = 0

    update_cursor = conn.cursor()
    for row in rows:
        name = row["defendant_name"]
        cleaned = normalize_name(name)
        is_valid = 0 if is_placeholder(name) else 1

        if is_valid:
            valid_count += 1
        else:
            filtered_count += 1

        update_cursor.execute(
            "UPDATE defendants SET cleaned_name = %s, is_valid = %s WHERE id = %s",
            (cleaned, is_valid, row["id"]),
        )

    conn.commit()
    update_cursor.close()
    cursor.close()
    conn.close()

    print(f"Valid defendants: {valid_count}, filtered out: {filtered_count}")
