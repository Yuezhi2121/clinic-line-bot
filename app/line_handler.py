import json
import logging

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)

from app.config import DEPARTMENTS, LINE_CHANNEL_ACCESS_TOKEN
from app.database import get_db
from app.scraper import fetch_progress, format_progress_message, _get_current_time_code, TIME_CODE_LABELS

logger = logging.getLogger(__name__)

_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

WELCOME_TEXT = (
    "👋 嗨！我是林口長庚看診進度小幫手！\n\n"
    "我可以幫你：\n"
    "1️⃣ 即時查詢看診進度\n"
    "2️⃣ 訂閱通知，快到你的號碼時自動提醒\n\n"
    "━━━━━━━━━━━━━━━\n"
    "📌 快速開始：\n\n"
    "🔍 查詢進度\n"
    "  直接輸入科別，例如：\n"
    "  「內科」「外科」「中醫」\n\n"
    "🔔 訂閱通知\n"
    "  輸入「訂閱」\n"
    "  ➜ 選科別 ➜ 選醫師 ➜ 輸入你的號碼\n"
    "  設定完成後，有進度更新就會通知你！\n\n"
    "━━━━━━━━━━━━━━━\n"
    "📖 所有指令：\n"
    "  「科別」查看所有科別\n"
    "  「狀態」查看我的訂閱\n"
    "  「取消」取消訂閱\n"
    "  「小幫手」顯示此說明\n"
)

HELP_TEXT = WELCOME_TEXT

DEPT_LIST_TEXT = (
    "🏥 可查詢的科別：\n\n"
    + "\n".join(f"  • {name}" for name in DEPARTMENTS if name not in ("COVID-19服務", "類流感暨COVID-19新冠門診"))
    + "\n\n直接輸入科別名稱即可查詢看診進度"
)


async def handle_text_message(user_id: str, text: str) -> str:
    """Process a text message and return a reply string."""
    text = text.strip()
    db = await get_db()

    # Check user conversation state
    cursor = await db.execute(
        "SELECT state, context FROM user_state WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    state = row["state"] if row else "IDLE"
    context = json.loads(row["context"]) if row else {}

    # Commands that work in any state
    if text in ("幫助", "help", "？", "?", "小幫手"):
        await _set_state(db, user_id, "IDLE", {})
        return WELCOME_TEXT

    if text in ("科別", "看科別", "科別列表"):
        await _set_state(db, user_id, "IDLE", {})
        return DEPT_LIST_TEXT

    if text in ("取消訂閱", "取消"):
        return await _handle_cancel(db, user_id)

    if text in ("狀態", "我的訂閱", "查詢訂閱"):
        return await _handle_status(db, user_id)

    if text == "訂閱":
        await _set_state(db, user_id, "WAITING_DEPT", {})
        return "請輸入要訂閱的科別名稱，例如：「中醫」「內科」\n\n" + DEPT_LIST_TEXT

    # State machine
    if state == "WAITING_DEPT":
        return await _handle_waiting_dept(db, user_id, text)

    if state == "WAITING_DOCTOR":
        return await _handle_waiting_doctor(db, user_id, text, context)

    if state == "WAITING_NUMBER":
        return await _handle_waiting_number(db, user_id, text, context)

    # Default: try to match a department name for quick query
    dept_code = _match_department(text)
    if dept_code:
        return await _handle_query_dept(text, dept_code)

    return (
        "我不太理解你的意思 😅\n"
        "輸入「幫助」查看可用指令\n"
        "或直接輸入科別名稱（如「內科」）查詢看診進度"
    )


async def _handle_query_dept(dept_name: str, dept_code: str) -> str:
    """Query and return progress for a department."""
    time_code = _get_current_time_code()
    try:
        doctors = await fetch_progress(dept_code, time_code)
    except Exception:
        logger.exception("Failed to fetch progress")
        return "抱歉，目前無法取得看診進度，請稍後再試。"

    return format_progress_message(dept_name, time_code, doctors)


async def _handle_waiting_dept(db, user_id: str, text: str) -> str:
    dept_code = _match_department(text)
    if not dept_code:
        return f"找不到「{text}」這個科別。\n請重新輸入，或輸入「科別」查看所有科別。"

    dept_name = text
    # Normalize dept_name
    for name, code in DEPARTMENTS.items():
        if code == dept_code:
            dept_name = name
            break

    time_code = _get_current_time_code()
    try:
        doctors = await fetch_progress(dept_code, time_code)
    except Exception:
        logger.exception("Failed to fetch progress")
        return "抱歉，目前無法取得看診進度，請稍後再試。"

    if not doctors:
        time_label = TIME_CODE_LABELS.get(time_code, "")
        return f"{dept_name}（{time_label}）目前沒有看診資料。\n請確認是否在看診時段內。"

    # Show doctors and ask user to pick one
    context = {
        "dept_code": dept_code,
        "dept_name": dept_name,
        "time_code": time_code,
        "doctors": [
            {"name": d.doctor_name, "sub_dept": d.sub_dept, "current": d.current_number}
            for d in doctors
        ],
    }
    await _set_state(db, user_id, "WAITING_DOCTOR", context)

    lines = [f"📋 {dept_name} 目前看診的醫師：\n"]
    for i, d in enumerate(doctors, 1):
        status = f"看到第 {d.current_number} 號" if d.current_number else "尚未開始"
        lines.append(f"  {i}. {d.sub_dept} - {d.doctor_name}（{status}）")

    lines.append("\n請輸入醫師編號或姓名來選擇：")
    return "\n".join(lines)


async def _handle_waiting_doctor(db, user_id: str, text: str, context: dict) -> str:
    doctors = context.get("doctors", [])

    selected = None
    # Try matching by number
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(doctors):
            selected = doctors[idx]
    # Try matching by name
    if not selected:
        for d in doctors:
            if text in d["name"] or d["name"] in text:
                selected = d
                break

    if not selected:
        return (
            f"找不到「{text}」這位醫師。\n"
            "請輸入醫師的編號（數字）或姓名。\n"
            "輸入「取消」可以重新開始。"
        )

    context["selected_doctor"] = selected["name"]
    context["selected_sub_dept"] = selected["sub_dept"]
    await _set_state(db, user_id, "WAITING_NUMBER", context)

    return (
        f"你選擇了 {selected['sub_dept']} - {selected['name']}\n"
        f"目前看到第 {selected['current']} 號\n\n"
        f"請輸入你的看診號碼（數字）："
    )


async def _handle_waiting_number(db, user_id: str, text: str, context: dict) -> str:
    if not text.isdigit():
        return "請輸入數字的看診號碼，例如：「25」"

    appointment_number = int(text)
    if appointment_number <= 0:
        return "號碼必須大於 0，請重新輸入。"

    doctor_name = context["selected_doctor"]
    dept_code = context["dept_code"]
    dept_name = context["dept_name"]
    sub_dept = context.get("selected_sub_dept", "")

    # Save subscription
    await db.execute(
        """
        INSERT INTO subscriptions (user_id, dept_code, dept_name, doctor_name, appointment_number, last_notified_number)
        VALUES (?, ?, ?, ?, ?, 0)
        ON CONFLICT(user_id, doctor_name)
        DO UPDATE SET
            dept_code = excluded.dept_code,
            dept_name = excluded.dept_name,
            appointment_number = excluded.appointment_number,
            last_notified_number = 0,
            created_at = CURRENT_TIMESTAMP
        """,
        (user_id, dept_code, dept_name, doctor_name, appointment_number),
    )
    await db.commit()

    await _set_state(db, user_id, "IDLE", {})

    # Calculate remaining
    current = 0
    for d in context.get("doctors", []):
        if d["name"] == doctor_name:
            current = d["current"]
            break

    remaining = appointment_number - current
    if current > 0 and remaining > 0:
        remaining_text = f"目前看到第 {current} 號，前面還有 {remaining} 位。"
    elif current > 0:
        remaining_text = f"目前看到第 {current} 號，已經到你的號了！"
    else:
        remaining_text = "醫師尚未開始看診。"

    return (
        f"✅ 訂閱成功！\n\n"
        f"科別：{sub_dept}\n"
        f"醫師：{doctor_name}\n"
        f"你的號碼：{appointment_number} 號\n"
        f"{remaining_text}\n\n"
        f"看診進度有更新時會自動通知你。\n"
        f"輸入「狀態」查看訂閱，輸入「取消」取消訂閱。"
    )


async def _handle_cancel(db, user_id: str) -> str:
    cursor = await db.execute(
        "SELECT id, doctor_name, dept_name, appointment_number FROM subscriptions WHERE user_id = ?",
        (user_id,),
    )
    subs = await cursor.fetchall()

    if not subs:
        await _set_state(db, user_id, "IDLE", {})
        return "你目前沒有任何訂閱。"

    await db.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
    await db.commit()
    await _set_state(db, user_id, "IDLE", {})

    lines = ["✅ 已取消以下訂閱：\n"]
    for s in subs:
        lines.append(f"  • {s['dept_name']} - {s['doctor_name']}（{s['appointment_number']} 號）")

    return "\n".join(lines)


async def _handle_status(db, user_id: str) -> str:
    cursor = await db.execute(
        """
        SELECT s.doctor_name, s.dept_name, s.appointment_number,
               c.current_number, c.sub_dept
        FROM subscriptions s
        LEFT JOIN clinic_status c ON s.dept_code = c.dept_code AND s.doctor_name = c.doctor_name
        WHERE s.user_id = ?
        """,
        (user_id,),
    )
    subs = await cursor.fetchall()

    if not subs:
        return "你目前沒有任何訂閱。\n輸入「訂閱」開始設定看診進度通知。"

    lines = ["📋 你的訂閱狀態：\n"]
    for s in subs:
        current = s["current_number"] or 0
        appt = s["appointment_number"]
        doctor = s["doctor_name"]
        dept = s["dept_name"]
        sub_dept = s["sub_dept"] or dept

        if current > 0:
            remaining = appt - current
            if remaining > 0:
                status = f"目前第 {current} 號，前面還有 {remaining} 位"
            else:
                status = f"目前第 {current} 號，已到號！"
        else:
            status = "尚未開始看診"

        lines.append(f"🔹 {sub_dept} - {doctor}")
        lines.append(f"   你的號碼：{appt} 號")
        lines.append(f"   {status}")
        lines.append("")

    return "\n".join(lines).strip()


async def _set_state(db, user_id: str, state: str, context: dict):
    await db.execute(
        """
        INSERT INTO user_state (user_id, state, context, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id)
        DO UPDATE SET state = excluded.state, context = excluded.context, updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, state, json.dumps(context, ensure_ascii=False)),
    )
    await db.commit()


def _match_department(text: str) -> str | None:
    """Fuzzy match user input to a department code."""
    # Exact match
    if text in DEPARTMENTS:
        return DEPARTMENTS[text]

    # Partial match
    for name, code in DEPARTMENTS.items():
        if text in name or name in text:
            return code

    return None


def reply_message(reply_token: str, text: str):
    """Send a reply message using the LINE API."""
    with ApiClient(_config) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )
