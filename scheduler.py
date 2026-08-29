import os

import requests
from apscheduler.schedulers.blocking import BlockingScheduler

from collectors.cleaner import clean_defendants
from collectors.courtlistener import collect_all
from collectors.logger import collector_logger as logger
from collectors.pdf_collector import collect_documents
from collectors.pdf_parser import parse_schedule_a
from models.database import get_connection, init_db, save_cases
from risk.scorer import update_risk_scores
from search.sync import sync_pending_defendants
from storage.minio_client import get_presigned_url

PDF_TMP_DIR = "/tmp/tro_pdfs"


def daily_job():
    try:
        logger.info("定时任务开始")
        init_db()
        results = collect_all()
        save_cases(results)

        # --- PDF 采集与解析（独立 try，失败不影响已有流程）---
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, docket_id FROM cases WHERE DATE(created_at) = CURDATE()"
            )
            today_cases = cursor.fetchall()
            cursor.close()
            conn.close()

            for case in today_cases:
                case_id = case["id"]
                docket_id = case["docket_id"]
                count = collect_documents(case_id, docket_id)
                logger.info(f"case {case_id}: 上传 {count} 份文书到 MinIO")

            # 解析所有未处理的 schedule_a 文书
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, case_id, minio_path FROM documents "
                "WHERE doc_type = 'schedule_a' AND extracted = 0"
            )
            pending = cursor.fetchall()
            cursor.close()
            conn.close()

            for doc in pending:
                doc_id = doc["id"]
                case_id = doc["case_id"]
                minio_path = doc["minio_path"]

                presigned_url = get_presigned_url(minio_path)
                filename = os.path.basename(minio_path)
                local_path = os.path.join(PDF_TMP_DIR, f"case_{case_id}", filename)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                # 从 MinIO 临时链接下载（presigned URL 已含鉴权，无需额外 Header）
                resp = requests.get(presigned_url, stream=True, timeout=60)
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                parse_schedule_a(local_path, case_id)

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE documents SET extracted = 1 WHERE id = %s", (doc_id,)
                )
                conn.commit()
                cursor.close()
                conn.close()

                logger.info(f"doc {doc_id} 解析完成，extracted 已置 1")

        except Exception as e:
            logger.error(f"PDF 采集/解析异常: {e}")

        clean_defendants()
        sync_pending_defendants()
        update_risk_scores()
        logger.info("定时任务完成")

    except Exception as e:
        logger.error(f"定时任务异常: {e}")


if __name__ == "__main__":
    daily_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(daily_job, "cron", hour=2, minute=0)
    scheduler.start()
