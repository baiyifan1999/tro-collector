from collectors.logger import collector_logger as logger
from models.database import get_connection
from search.es_client import bulk_index_defendants

_SELECT_BASE = """
    SELECT
        d.id            AS defendant_id,
        d.case_id,
        d.cleaned_name  AS store_name,
        d.platform,
        d.source_doc_id,
        c.case_name,
        c.court,
        c.date_filed,
        doc.source_url
    FROM defendants d
    JOIN cases c ON c.id = d.case_id
    LEFT JOIN documents doc ON doc.id = d.source_doc_id
    WHERE d.is_valid = 1
"""


def _build_docs(rows):
    docs = []
    for row in rows:
        docs.append(
            {
                "defendant_id": row["defendant_id"],
                "case_id":      row["case_id"],
                "store_name":   row["store_name"] or "",
                "platform":     row["platform"] or "",
                "court":        row["court"] or "",
                "date_filed":   row["date_filed"] or None,
                "case_name":    row["case_name"] or "",
                "source_url":   row["source_url"] or "",
                "risk_score":   0,
            }
        )
    return docs


def sync_all_defendants() -> int:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(_SELECT_BASE)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    docs = _build_docs(rows)
    success = bulk_index_defendants(docs)
    logger.info(f"sync_all_defendants: 同步 {success}/{len(docs)} 条被告到 ES")
    return success


def sync_pending_defendants() -> int:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(_SELECT_BASE + " AND d.es_synced = 0")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        logger.info("sync_pending_defendants: 无待同步记录")
        return 0

    docs = _build_docs(rows)
    success = bulk_index_defendants(docs)

    # 只把成功入库的那批标记为已同步
    # helpers.bulk 按顺序返回，失败项会出现在 errors 里，
    # 这里用最简策略：成功数 == 总数才批量更新，否则逐条跳过失败
    synced_ids = [doc["defendant_id"] for doc in docs]
    if success == len(docs):
        _mark_synced(synced_ids)
    elif success > 0:
        # bulk 不直接告诉我们哪几条成功，保守策略：全部保留 es_synced=0
        # 等下次重试，避免把失败的误标为已同步
        logger.error(
            f"sync_pending_defendants: 部分失败 ({success}/{len(docs)})，"
            "保留 es_synced=0 等待下次重试"
        )

    logger.info(f"sync_pending_defendants: 同步 {success}/{len(docs)} 条被告到 ES")
    return success


def _mark_synced(defendant_ids: list):
    if not defendant_ids:
        return
    conn = get_connection()
    cursor = conn.cursor()
    fmt = ",".join(["%s"] * len(defendant_ids))
    cursor.execute(
        f"UPDATE defendants SET es_synced = 1 WHERE id IN ({fmt})",
        defendant_ids,
    )
    conn.commit()
    cursor.close()
    conn.close()
