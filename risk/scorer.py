import re
from datetime import date

from rapidfuzz import fuzz

from collectors.logger import collector_logger as logger
from models.database import get_connection

_RESULT_SCORES = {
    "granted":   20,
    "pending":   12,
    "settled":   8,
    "dismissed": 0,
}

_PLATFORM_MULTIPLIERS = {1: 1.0, 2: 1.2}


def calculate_score(case_count, latest_date, case_results, platform_count):
    quantity_score = min(case_count * 5, 50)

    if latest_date:
        if isinstance(latest_date, str):
            latest_date = date.fromisoformat(latest_date[:10])
        years_ago = (date.today() - latest_date).days / 365.25
        recency_score = max(30 - int(years_ago * 10), 0)
    else:
        recency_score = 0

    type_score = max(
        (_RESULT_SCORES.get(r.lower(), 5) for r in (case_results or [])),
        default=0,
    )

    multiplier = _PLATFORM_MULTIPLIERS.get(
        platform_count if platform_count <= 2 else 3, 1.5
    )

    return min(int((quantity_score + recency_score + type_score) * multiplier), 100)


def normalize_company_name(name):
    if not name:
        return ""
    cleaned = name.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(
        r"\bCompany Limited\b|\bCo\.,?\s*Ltd\.?\b",
        "Co., Ltd.",
        cleaned,
        flags=re.IGNORECASE,
    )
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


def group_by_company(defendants):
    groups = {}        # canonical_name -> [defendant dicts]
    canonicals = []    # ordered list of canonical names for comparison

    for d in defendants:
        raw = d.get("cleaned_name") or d.get("defendant_name") or ""
        name = normalize_company_name(raw)
        if not name:
            continue

        best_canonical = None
        best_ratio = 0
        for canonical in canonicals:
            ratio = fuzz.ratio(name, canonical)
            if ratio >= 85 and ratio > best_ratio:
                best_ratio = ratio
                best_canonical = canonical

        if best_canonical:
            groups[best_canonical].append(d)
        else:
            canonicals.append(name)
            groups[name] = [d]

    return groups


def update_risk_scores():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            d.id,
            d.case_id,
            d.cleaned_name,
            d.defendant_name,
            d.platform,
            c.date_filed
        FROM defendants d
        JOIN cases c ON c.id = d.case_id
        WHERE d.is_valid = 1
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    groups = group_by_company(rows)

    upsert_cursor = get_connection().cursor()
    # keep a reference so we can commit later
    upsert_conn = get_connection()
    upsert_cursor = upsert_conn.cursor()

    updated = 0
    for company_name, members in groups.items():
        case_ids = {m["case_id"] for m in members}
        platforms = {m["platform"] for m in members if m.get("platform")}
        dates = [
            m["date_filed"] for m in members
            if m.get("date_filed")
        ]
        latest_date = max(dates) if dates else None

        score = calculate_score(
            case_count=len(case_ids),
            latest_date=latest_date,
            case_results=["pending"],   # tro_status not yet available
            platform_count=len(platforms) if platforms else 1,
        )

        upsert_cursor.execute(
            """
            INSERT INTO risk_scores (company_name, risk_score)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                risk_score = VALUES(risk_score),
                updated_at = CURRENT_TIMESTAMP
            """,
            (company_name, score),
        )
        updated += 1

    upsert_conn.commit()
    upsert_cursor.close()
    upsert_conn.close()

    logger.info(f"update_risk_scores: 更新 {updated} 家公司的风险评分")
    return updated
