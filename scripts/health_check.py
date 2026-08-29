import shutil
from datetime import datetime, timedelta, timezone

from collectors.logger import collector_logger as logger
from models.database import get_connection


def run_health_check():
    # 检查一：7 天内是否有新案件
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM cases WHERE created_at >= %s",
            (datetime.now(timezone.utc) - timedelta(days=7),),
        )
        (recent_count,) = cursor.fetchone()
        cursor.close()
        conn.close()
        if recent_count == 0:
            logger.warning("连续 7 天无新案件入库")
    except Exception as e:
        logger.error(f"健康检查（案件数）异常: {e}")

    # 检查二：ES 待同步记录数
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM defendants WHERE es_synced = 0")
        (unsynced,) = cursor.fetchone()
        cursor.close()
        conn.close()
        if unsynced > 100:
            logger.warning(f"ES 待同步记录过多：{unsynced} 条")
    except Exception as e:
        logger.error(f"健康检查（ES 同步）异常: {e}")

    # 检查三：磁盘使用率
    try:
        usage = shutil.disk_usage("/")
        percent = usage.used / usage.total * 100
        if percent > 85:
            logger.warning(f"磁盘使用率过高：{percent:.1f}%")
    except Exception as e:
        logger.error(f"健康检查（磁盘）异常: {e}")

    # 检查四：最近采集时间
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(created_at) FROM cases")
        (latest,) = cursor.fetchone()
        cursor.close()
        conn.close()
        if latest is None or datetime.now(timezone.utc) - latest.replace(
            tzinfo=timezone.utc
        ) > timedelta(hours=48):
            logger.warning("超过 48 小时未采集到新数据")
    except Exception as e:
        logger.error(f"健康检查（采集时间）异常: {e}")

    logger.info("健康检查完成")
