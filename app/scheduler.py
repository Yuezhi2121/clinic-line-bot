import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import SCRAPE_INTERVAL_SECONDS
from app.database import get_db
from app.notifier import build_update_message, push_text
from app.scraper import fetch_progress

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def check_and_notify():
    """Fetch latest progress for all subscribed departments, then notify users."""
    try:
        db = await get_db()

        cursor = await db.execute(
            "SELECT DISTINCT hospital_code, dept_code FROM subscriptions"
        )
        rows = await cursor.fetchall()

        if not rows:
            return

        for row in rows:
            await _check_dept(db, row["hospital_code"], row["dept_code"])

    except Exception:
        logger.exception("Error in check_and_notify")


async def _check_dept(db, hospital_code: str, dept_code: str):
    """Check a single hospital+department and notify relevant subscribers."""
    try:
        doctors = await fetch_progress(hospital_code, dept_code)
    except Exception:
        logger.exception("Failed to fetch progress for hospital %s dept %s", hospital_code, dept_code)
        return

    for doc in doctors:
        await db.execute(
            """
            INSERT INTO clinic_status (hospital_code, dept_code, doctor_name, current_number, next_number, location, sub_dept, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(hospital_code, dept_code, doctor_name)
            DO UPDATE SET
                current_number = excluded.current_number,
                next_number = excluded.next_number,
                location = excluded.location,
                sub_dept = excluded.sub_dept,
                updated_at = CURRENT_TIMESTAMP
            """,
            (hospital_code, dept_code, doc.doctor_name, doc.current_number, doc.next_number, doc.location, doc.sub_dept),
        )

        cursor = await db.execute(
            """
            SELECT id, user_id, appointment_number, last_notified_number, hospital_name
            FROM subscriptions
            WHERE hospital_code = ? AND dept_code = ? AND doctor_name = ?
            """,
            (hospital_code, dept_code, doc.doctor_name),
        )
        subs = await cursor.fetchall()

        for sub in subs:
            if doc.current_number == 0:
                continue

            if doc.current_number == sub["last_notified_number"]:
                continue

            remaining = sub["appointment_number"] - doc.current_number
            if remaining < -5:
                await db.execute("DELETE FROM subscriptions WHERE id = ?", (sub["id"],))
                await push_text(
                    sub["user_id"],
                    f"你的號碼 {sub['appointment_number']} 號已過號較久，"
                    f"已自動取消訂閱 {sub['hospital_name']} {doc.doctor_name} 醫師。",
                )
                continue

            msg = build_update_message(
                sub["hospital_name"], doc.doctor_name, doc.sub_dept,
                doc.current_number, sub["appointment_number"],
            )
            await push_text(sub["user_id"], msg)

            await db.execute(
                "UPDATE subscriptions SET last_notified_number = ? WHERE id = ?",
                (doc.current_number, sub["id"]),
            )

    await db.commit()


def start_scheduler():
    scheduler.add_job(
        check_and_notify,
        "interval",
        seconds=SCRAPE_INTERVAL_SECONDS,
        id="check_progress",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started, checking every %ds", SCRAPE_INTERVAL_SECONDS)


def stop_scheduler():
    scheduler.shutdown(wait=False)
