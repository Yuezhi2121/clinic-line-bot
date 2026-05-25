import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import DoctorProgress, HospitalScraper

PROGRESS_URL = "https://www.tahsda.org.tw/Register/Call_Number.php"

BRANCHES = {
    "臺安醫院": "main",
}

TIME_LABEL_MAP = {"上午": "1", "下午": "2", "夜間": "3"}


class TAHSDAScraper(HospitalScraper):
    hospital_id = "tahsda"
    display_name = "臺安醫院"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return {}

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        """dept_code is used as keyword to filter by department name.
        If empty, all departments are returned.
        """
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(PROGRESS_URL, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()

        return self._parse(r.text, dept_code, time_code)

    def _parse(
        self, html: str, dept_filter: str, time_code: str | None
    ) -> list[DoctorProgress]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        results: list[DoctorProgress] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            dept_name = cells[0].get_text(strip=True)
            time_label = cells[1].get_text(strip=True)

            if dept_filter and dept_filter not in dept_name:
                continue

            if time_code:
                row_time = TIME_LABEL_MAP.get(time_label, "")
                if row_time != time_code:
                    continue

            raw_status = cells[4].get_text(strip=True)
            number, status = _parse_status(raw_status)
            results.append(
                DoctorProgress(
                    sub_dept=dept_name,
                    location=cells[3].get_text(strip=True),
                    doctor_name=cells[2].get_text(strip=True),
                    current_number=number,
                    next_number="",
                    status=status,
                )
            )
        return results


_STATUS_KEYWORDS = ("休診", "暫停", "停診", "請假", "額滿")


def _parse_status(raw: str) -> tuple[int, str]:
    if not raw:
        return 0, ""
    for kw in _STATUS_KEYWORDS:
        if kw in raw:
            return 0, raw
    nums = re.findall(r"\d+", raw)
    return (int(nums[0]) if nums else 0), ""
