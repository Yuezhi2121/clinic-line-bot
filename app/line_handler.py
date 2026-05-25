import json
import logging

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)

from app.config import LINE_CHANNEL_ACCESS_TOKEN
from app.database import get_db
from app.scrapers.base import DoctorProgress, get_current_time_code, TIME_CODE_LABELS, tw_now
from app.scrapers.registry import find_hospital, get_all_hospital_names, get_scraper

logger = logging.getLogger(__name__)

_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

_all_hospital_names = get_all_hospital_names()

def _build_hospital_list() -> str:
    from app.scrapers.registry import get_all_scrapers
    lines = ["🏥 可查詢的醫院 / 院區：\n"]
    for scraper in get_all_scrapers().values():
        branches = list(scraper.get_branches().keys())
        if len(branches) == 1:
            lines.append(f"  🔹 {branches[0]}")
        else:
            lines.append(f"  🔹 {scraper.display_name}")
            for b in branches:
                lines.append(f"      {b}")
    lines.append(f"\n共 {len(_all_hospital_names)} 個院區可查詢")
    lines.append("輸入醫院名稱即可選擇")
    return "\n".join(lines)


HOSPITAL_LIST_TEXT = _build_hospital_list()

WELCOME_TEXT = (
    "👋 嗨！我是看診進度小幫手！\n\n"
    "我可以幫你：\n"
    "1️⃣ 即時查詢各醫院看診進度\n"
    "2️⃣ 訂閱通知，快到你的號碼時自動提醒\n\n"
    "━━━━━━━━━━━━━━━\n"
    "📌 快速開始：\n\n"
    "🔍 查詢進度\n"
    "  輸入「進度查詢」\n"
    "  ➜ 選醫院 ➜ 選科別 ➜ 輸入醫師或診間篩選\n\n"
    "🔔 訂閱通知\n"
    "  輸入「訂閱」\n"
    "  ➜ 選醫院 ➜ 選科別 ➜ 選醫師 ➜ 輸入號碼\n"
    "  設定完成後，有進度更新就會通知你！\n\n"
    "━━━━━━━━━━━━━━━\n"
    "📖 所有指令：\n"
    "  「進度查詢」查詢看診進度\n"
    "  「訂閱」設定看診通知\n"
    "  「醫院」查看所有可查詢的醫院\n"
    "  「狀態」查看我的訂閱\n"
    "  「取消」取消訂閱\n"
    "  「小幫手」顯示此說明\n"
)

HELP_TEXT = WELCOME_TEXT


def _build_dept_list_text(hospital_id: str) -> str:
    scraper = get_scraper(hospital_id)
    if not scraper:
        return "請直接輸入科別名稱（如「內科」、「骨科」）"
    depts = scraper.get_departments()
    if not depts:
        return "此醫院不需選擇科別，請直接輸入科別關鍵字（如「內科」、「骨科」）"
    return "\n".join(f"  • {name}" for name in depts)


TRIGGER_KEYWORDS = frozenset({
    "幫助", "help", "？", "?", "小幫手",
    "醫院", "院區", "醫院列表",
    "取消訂閱", "取消",
    "狀態", "我的訂閱", "查詢訂閱",
    "進度查詢", "查詢進度", "查詢",
    "訂閱",
})


async def handle_text_message(user_id: str, text: str, is_group: bool = False) -> str | None:
    """Return reply text, or None when the bot should stay silent."""
    text = text.strip()
    db = await get_db()

    cursor = await db.execute(
        "SELECT state, context FROM user_state WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    state = row["state"] if row else "IDLE"
    context = json.loads(row["context"]) if row else {}

    if is_group and text not in TRIGGER_KEYWORDS and state == "IDLE":
        return None

    # --- Global commands ---

    if text in ("幫助", "help", "？", "?", "小幫手"):
        await _set_state(db, user_id, "IDLE", {})
        return WELCOME_TEXT

    if text in ("醫院", "院區", "醫院列表"):
        await _set_state(db, user_id, "IDLE", {})
        return HOSPITAL_LIST_TEXT

    if text == "取消":
        if state != "IDLE":
            await _set_state(db, user_id, "IDLE", {})
            return "已取消目前的操作。\n\n輸入「進度查詢」或「訂閱」重新開始。"
        return await _handle_cancel_sub(db, user_id)

    if text == "取消訂閱":
        return await _handle_cancel_sub(db, user_id)

    if text in ("狀態", "我的訂閱", "查詢訂閱"):
        return await _handle_status(db, user_id)

    if text in ("進度查詢", "查詢進度", "查詢"):
        await _set_state(db, user_id, "QUERY_WAITING_HOSPITAL", {})
        return "請選擇要查詢的醫院：\n\n" + HOSPITAL_LIST_TEXT

    if text == "訂閱":
        await _set_state(db, user_id, "SUB_WAITING_HOSPITAL", {})
        return "請選擇要訂閱的醫院：\n\n" + HOSPITAL_LIST_TEXT

    # --- State machine ---

    if state == "QUERY_WAITING_HOSPITAL":
        return await _handle_query_hospital(db, user_id, text)

    if state == "SUB_WAITING_HOSPITAL":
        return await _handle_sub_hospital(db, user_id, text)

    if state == "SUB_WAITING_DEPT":
        return await _handle_sub_dept(db, user_id, text, context)

    if state == "WAITING_DOCTOR":
        return await _handle_waiting_doctor(db, user_id, text, context)

    if state == "WAITING_NUMBER":
        return await _handle_waiting_number(db, user_id, text, context)

    if state == "QUERY_WAITING_DEPT":
        return await _handle_query_dept_state(db, user_id, text, context)

    if state == "QUERY_WAITING_FILTER":
        return await _handle_query_filter(db, user_id, text, context)

    return (
        "我不太理解你的意思 😅\n\n"
        "💡 試試看：\n"
        "  • 輸入「進度查詢」查詢看診進度\n"
        "  • 輸入「訂閱」設定看診通知\n"
        "  • 輸入「小幫手」查看完整說明"
    )


# ========== Quick Query ==========

async def _handle_query_hospital(db, user_id: str, text: str) -> str:
    entry = _match_hospital(text)
    if not entry:
        return f"找不到「{text}」這間醫院。\n請重新輸入，或輸入「醫院」查看所有院區。"

    scraper = entry.scraper
    hospital_code = f"{scraper.hospital_id}:{entry.branch_code}"
    ctx = {"hospital_code": hospital_code, "hospital_name": entry.branch_name, "hospital_id": scraper.hospital_id}
    await _set_state(db, user_id, "QUERY_WAITING_DEPT", ctx)

    dept_text = _build_dept_list_text(scraper.hospital_id)
    return (
        f"🏥 {entry.branch_name}\n\n"
        f"請輸入要查詢的科別：\n\n"
        f"{dept_text}"
    )


async def _handle_query_dept_state(db, user_id: str, text: str, context: dict) -> str:
    hospital_code = context["hospital_code"]
    hospital_name = context["hospital_name"]
    hospital_id = context.get("hospital_id", "")

    scraper = get_scraper(hospital_id)
    if not scraper:
        await _set_state(db, user_id, "IDLE", {})
        return "系統錯誤，請重新選擇醫院。"

    _, branch_code = hospital_code.split(":", 1)

    dept_code = _match_dept_for_scraper(scraper, text)
    dept_name = text

    if scraper.get_departments():
        if not dept_code:
            dept_text = _build_dept_list_text(hospital_id)
            return f"找不到「{text}」這個科別。\n請重新輸入：\n\n{dept_text}"
        for name, code in scraper.get_departments().items():
            if code == dept_code:
                dept_name = name
                break
    else:
        dept_code = text

    time_code = get_current_time_code()
    try:
        doctors = await scraper.fetch_progress(branch_code, dept_code, time_code)
    except Exception:
        logger.exception("Failed to fetch progress")
        ts = tw_now().strftime("%H:%M")
        return f"抱歉，目前無法取得看診進度，請稍後再試。\n🕐 {ts}"

    if not doctors:
        time_label = TIME_CODE_LABELS.get(time_code, "")
        ts = tw_now().strftime("%H:%M")
        await _set_state(db, user_id, "IDLE", {
            "hospital_code": hospital_code, "hospital_name": hospital_name, "hospital_id": hospital_id
        })
        return f"目前 {hospital_name} {dept_name}（{time_label}）沒有看診資料。\n🕐 查詢時間：{ts}"

    context.update({
        "dept_code": dept_code,
        "dept_name": dept_name,
        "time_code": time_code,
        "doctors_cache": [
            {"name": d.doctor_name, "sub_dept": d.sub_dept, "location": d.location,
             "current": d.current_number, "next": d.next_number, "status": d.status}
            for d in doctors
        ],
    })
    await _set_state(db, user_id, "QUERY_WAITING_FILTER", context)

    active = [d for d in doctors if not d.status]
    paused = [d for d in doctors if d.status]
    time_label = TIME_CODE_LABELS.get(time_code, "")

    summary = f"📋 {hospital_name} {dept_name}（{time_label}）\n"
    summary += f"共 {len(doctors)} 位醫師"
    if paused:
        summary += f"（其中 {len(paused)} 位休診/暫停）"
    summary += "\n\n"
    summary += (
        "請輸入以下任一條件來縮小範圍：\n"
        "  🔹 醫師姓名（如「王大明」）\n"
        "  🔹 門診科系（如「心臟科」）\n"
        "  🔹 診間編號（如「03診」）\n\n"
        "或輸入「全部」查看所有醫師進度"
    )
    return summary


async def _handle_query_filter(db, user_id: str, text: str, context: dict) -> str:
    hospital_code = context["hospital_code"]
    hospital_name = context["hospital_name"]
    hospital_id = context.get("hospital_id", "")
    dept_name = context.get("dept_name", "")
    time_code = context.get("time_code", "")
    doctors_cache = context.get("doctors_cache", [])

    scraper = get_scraper(hospital_id)
    if not scraper:
        await _set_state(db, user_id, "IDLE", {})
        return "系統錯誤，請重新選擇醫院。"

    await _set_state(db, user_id, "IDLE", {
        "hospital_code": hospital_code, "hospital_name": hospital_name, "hospital_id": hospital_id
    })

    if text in ("全部", "all", "ALL"):
        all_docs = _cache_to_progress(doctors_cache)
        return scraper.format_progress(hospital_name, dept_name, time_code, all_docs)

    filtered = [
        d for d in doctors_cache
        if text in d["name"] or text in d["sub_dept"]
           or text in d.get("location", "") or text in d.get("status", "")
    ]

    if not filtered:
        all_docs = _cache_to_progress(doctors_cache)
        result = scraper.format_progress(hospital_name, dept_name, time_code, all_docs)
        return f"找不到符合「{text}」的結果，以下為全部看診進度：\n\n{result}"

    matched_docs = _cache_to_progress(filtered)
    return scraper.format_progress(hospital_name, dept_name, time_code, matched_docs)


# ========== Subscribe Flow ==========

async def _handle_sub_hospital(db, user_id: str, text: str) -> str:
    entry = _match_hospital(text)
    if not entry:
        return f"找不到「{text}」這間醫院。\n請重新輸入，或輸入「醫院」查看所有院區。"

    scraper = entry.scraper
    hospital_code = f"{scraper.hospital_id}:{entry.branch_code}"
    ctx = {"hospital_code": hospital_code, "hospital_name": entry.branch_name, "hospital_id": scraper.hospital_id}
    await _set_state(db, user_id, "SUB_WAITING_DEPT", ctx)

    dept_text = _build_dept_list_text(scraper.hospital_id)
    return (
        f"✅ 已選擇 {entry.branch_name}\n\n"
        f"請輸入要訂閱的科別：\n\n"
        f"{dept_text}"
    )


async def _handle_sub_dept(db, user_id: str, text: str, context: dict) -> str:
    hospital_code = context["hospital_code"]
    hospital_name = context["hospital_name"]
    hospital_id = context.get("hospital_id", "")

    scraper = get_scraper(hospital_id)
    if not scraper:
        await _set_state(db, user_id, "IDLE", {})
        return "系統錯誤，請重新選擇醫院。"

    _, branch_code = hospital_code.split(":", 1)

    dept_code = _match_dept_for_scraper(scraper, text)
    dept_name = text

    if scraper.get_departments():
        if not dept_code:
            dept_text = _build_dept_list_text(hospital_id)
            return f"找不到「{text}」這個科別。\n請重新輸入：\n\n{dept_text}"
        for name, code in scraper.get_departments().items():
            if code == dept_code:
                dept_name = name
                break
    else:
        dept_code = text

    time_code = get_current_time_code()
    try:
        doctors = await scraper.fetch_progress(branch_code, dept_code, time_code)
    except Exception:
        logger.exception("Failed to fetch progress")
        ts = tw_now().strftime("%H:%M")
        return f"抱歉，目前無法取得看診進度，請稍後再試。\n🕐 {ts}"

    if not doctors:
        time_label = TIME_CODE_LABELS.get(time_code, "")
        ts = tw_now().strftime("%H:%M")
        return f"{hospital_name} {dept_name}（{time_label}）目前沒有看診資料。\n請確認是否在看診時段內。\n🕐 查詢時間：{ts}"

    active_doctors = [d for d in doctors if not d.status]
    if not active_doctors:
        time_label = TIME_CODE_LABELS.get(time_code, "")
        lines = [f"📋 {hospital_name} {dept_name}（{time_label}）\n"]
        lines.append("⚠️ 目前所有醫師皆休診或暫停看診：\n")
        for d in doctors:
            lines.append(f"  ⛔ {d.sub_dept} - {d.doctor_name}（{d.status}）")
        return "\n".join(lines)

    context.update({
        "dept_code": dept_code,
        "dept_name": dept_name,
        "time_code": time_code,
        "doctors": [
            {"name": d.doctor_name, "sub_dept": d.sub_dept, "current": d.current_number, "status": d.status}
            for d in active_doctors
        ],
    })
    await _set_state(db, user_id, "WAITING_DOCTOR", context)

    lines = [f"📋 {hospital_name} {dept_name} 目前看診的醫師：\n"]
    for i, d in enumerate(active_doctors, 1):
        status_text = f"看到第 {d.current_number} 號" if d.current_number else "⏳ 尚未開始"
        lines.append(f"  {i}. {d.sub_dept} - {d.doctor_name}（{status_text}）")

    lines.append("\n請輸入醫師編號或姓名來選擇：")
    return "\n".join(lines)


async def _handle_waiting_doctor(db, user_id: str, text: str, context: dict) -> str:
    doctors = context.get("doctors", [])

    selected = None
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(doctors):
            selected = doctors[idx]
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
    hospital_code = context["hospital_code"]
    hospital_name = context["hospital_name"]
    hospital_id = context.get("hospital_id", "")
    dept_code = context["dept_code"]
    dept_name = context["dept_name"]
    sub_dept = context.get("selected_sub_dept", "")

    await db.execute(
        """
        INSERT INTO subscriptions (user_id, hospital_code, hospital_name, dept_code, dept_name, doctor_name, appointment_number, last_notified_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(user_id, hospital_code, doctor_name)
        DO UPDATE SET
            dept_code = excluded.dept_code,
            dept_name = excluded.dept_name,
            appointment_number = excluded.appointment_number,
            last_notified_number = 0,
            created_at = CURRENT_TIMESTAMP
        """,
        (user_id, hospital_code, hospital_name, dept_code, dept_name, doctor_name, appointment_number),
    )
    await db.commit()

    await _set_state(db, user_id, "IDLE", {
        "hospital_code": hospital_code, "hospital_name": hospital_name, "hospital_id": hospital_id
    })

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

    ts = tw_now().strftime("%H:%M")
    return (
        f"✅ 訂閱成功！\n\n"
        f"🏥 {hospital_name}\n"
        f"科別：{sub_dept}\n"
        f"醫師：{doctor_name}\n"
        f"你的號碼：{appointment_number} 號\n"
        f"{remaining_text}\n\n"
        f"看診進度有更新時會自動通知你。\n"
        f"輸入「狀態」查看訂閱，輸入「取消」取消訂閱。\n"
        f"🕐 {ts}"
    )


# ========== Cancel / Status ==========

async def _handle_cancel_sub(db, user_id: str) -> str:
    cursor = await db.execute(
        "SELECT id, hospital_name, doctor_name, dept_name, appointment_number FROM subscriptions WHERE user_id = ?",
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
        lines.append(f"  • {s['hospital_name']} {s['dept_name']} - {s['doctor_name']}（{s['appointment_number']} 號）")

    return "\n".join(lines)


async def _handle_status(db, user_id: str) -> str:
    cursor = await db.execute(
        """
        SELECT s.hospital_name, s.doctor_name, s.dept_name, s.appointment_number,
               c.current_number, c.sub_dept
        FROM subscriptions s
        LEFT JOIN clinic_status c
            ON s.hospital_code = c.hospital_code
            AND s.dept_code = c.dept_code
            AND s.doctor_name = c.doctor_name
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
        hospital = s["hospital_name"]
        sub_dept = s["sub_dept"] or s["dept_name"]

        if current > 0:
            remaining = appt - current
            if remaining > 0:
                status = f"目前第 {current} 號，前面還有 {remaining} 位"
            else:
                status = f"目前第 {current} 號，已到號！"
        else:
            status = "尚未開始看診"

        lines.append(f"🏥 {hospital}")
        lines.append(f"🔹 {sub_dept} - {doctor}")
        lines.append(f"   你的號碼：{appt} 號")
        lines.append(f"   {status}")
        lines.append("")

    lines.append(f"🕐 查詢時間：{tw_now().strftime('%H:%M')}")
    return "\n".join(lines).strip()


# ========== Utilities ==========

def _cache_to_progress(cache: list[dict]) -> list[DoctorProgress]:
    return [
        DoctorProgress(
            sub_dept=d["sub_dept"], location=d.get("location", ""),
            doctor_name=d["name"], current_number=d["current"],
            next_number=d.get("next", ""), status=d.get("status", ""),
        )
        for d in cache
    ]


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


def _match_hospital(text: str):
    """Match user input to a HospitalEntry from the registry."""
    entry = find_hospital(text)
    if entry:
        return entry

    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(_all_hospital_names):
            return find_hospital(_all_hospital_names[idx])

    return None


def _match_dept_for_scraper(scraper, text: str) -> str | None:
    """Match user input to a department code for a specific scraper."""
    depts = scraper.get_departments()
    if not depts:
        return text

    if text in depts:
        return depts[text]

    for name, code in depts.items():
        if text in name or name in text:
            return code

    return None


def reply_message(reply_token: str, text: str):
    with ApiClient(_config) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )
