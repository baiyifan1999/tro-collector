from apscheduler.schedulers.blocking import BlockingScheduler

from collectors.courtlistener import collect_all
from collectors.cleaner import clean_defendants
from collectors.logger import collector_logger as logger
from models.database import init_db, save_cases


def daily_job():
    try:
        logger.info("定时任务开始")
        init_db()
        results = collect_all()
        save_cases(results)
        clean_defendants()
        logger.info("定时任务完成")
    except Exception as e:
        logger.error(f"定时任务异常: {e}")


if __name__ == "__main__":
    daily_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(daily_job, "cron", hour=2, minute=0)
    scheduler.start()
