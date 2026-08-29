from collectors.logger import collector_logger as logger
from models.database import get_connection


def check_new_cases():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, case_name, court, date_filed, docket_number
        FROM cases
        WHERE DATE(created_at) = CURDATE()
        """
    )
    cases = cursor.fetchall()
    cursor.close()
    conn.close()
    return cases


def build_alert_message(cases):
    lines = [f"[TRO 预警] 发现 {len(cases)} 个新案件"]
    for i, case in enumerate(cases, start=1):
        lines.append(
            f"{i}. {case.get('case_name', '未知案件')}\n"
            f"   法院：{case.get('court', '-')} | "
            f"日期：{case.get('date_filed', '-')}"
        )
    return "\n".join(lines)


def send_alert(cases):
    if not cases:
        return 0

    message = build_alert_message(cases)
    logger.warning("[预警]" + message)

    conn = get_connection()
    cursor = conn.cursor()
    sent = 0
    for case in cases:
        cursor.execute(
            "INSERT IGNORE INTO alert_log (case_id, notified) VALUES (%s, 1)",
            (case["id"],),
        )
        if cursor.rowcount:
            sent += 1

    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"send_alert: 写入 {sent} 条预警记录（已预警过的已跳过）")
    return sent
