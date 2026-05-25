import re
from dataclasses import dataclass
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.config import CGMH_PROGRESS_URL


@dataclass
class DoctorProgress:
    sub_dept: str
    location: str
    doctor_name: str
    current_number: int
    next_number: str


def _get_current_time_code() -> str:
    """Auto-detect time period based on current hour."""
    hour = datetime.now().hour
    if hour < 12:
        return "1"  # 上午診
    elif hour < 17:
        return "2"  # 下午診
    else:
        return "3"  # 晚間


TIME_CODE_LABELS = {"1": "上午診", "2": "下午診", "3": "晚間"}


async def fetch_progress(
    dept_code: str, time_code: str | None = None
) -> list[DoctorProgress]:
    """Fetch consultation progress for a department from CGMH Linkou."""
    if time_code is None:
        time_code = _get_current_time_code()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            CGMH_PROGRESS_URL,
            data={"dept": dept_code, "time": time_code},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": CGMH_PROGRESS_URL,
            },
        )
        resp.raise_for_status()

    return _parse_progress_html(resp.text)


def _parse_progress_html(html: str) -> list[DoctorProgress]:
    soup = BeautifulSoup(html, "html.parser")

    # The first table in divDeptResult contains the progress data
    result_div = soup.find("div", id="divDeptResult")
    if not result_div:
        tables = soup.find_all("table")
        if not tables:
            return []
        table = tables[0]
    else:
        table = result_div.find("table")
        if not table:
            return []

    rows = table.find_all("tr")
    results: list[DoctorProgress] = []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        sub_dept = cells[0].get_text(strip=True)
        location = cells[1].get_text(strip=True)
        doctor_name = cells[2].get_text(strip=True)
        current_raw = cells[3].get_text(strip=True)
        next_raw = cells[4].get_text(strip=True) if len(cells) > 4 else ""

        current_number = _parse_number(current_raw)

        results.append(
            DoctorProgress(
                sub_dept=sub_dept,
                location=location,
                doctor_name=doctor_name,
                current_number=current_number,
                next_number=next_raw,
            )
        )

    return results


def _parse_number(raw: str) -> int:
    """Extract number from strings like '43', '過號 4', or empty."""
    if not raw:
        return 0
    nums = re.findall(r"\d+", raw)
    return int(nums[-1]) if nums else 0


def format_progress_message(
    dept_name: str, time_code: str, doctors: list[DoctorProgress]
) -> str:
    """Format progress data into a readable LINE message."""
    time_label = TIME_CODE_LABELS.get(time_code, "")
    if not doctors:
        return f"目前 {dept_name}（{time_label}）沒有看診資料。"

    lines = [f"📋 林口長庚 {dept_name}（{time_label}）看診進度\n"]
    for d in doctors:
        status = f"目前第 {d.current_number} 號" if d.current_number else "尚未開始"
        next_info = f"（下一位：{d.next_number}）" if d.next_number else ""
        lines.append(f"🔹 {d.sub_dept} - {d.doctor_name}")
        lines.append(f"   {status}{next_info}")
        lines.append(f"   📍 {d.location}")
        lines.append("")

    return "\n".join(lines).strip()
