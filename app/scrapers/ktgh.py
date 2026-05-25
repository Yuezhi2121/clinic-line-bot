import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import DoctorProgress, HospitalScraper

PROGRESS_URL = "https://register.ktgh.com.tw/ktgh/Medical/ClinicProgress"

BRANCHES = {
    "光田沙鹿": "sha-lu",
    "光田大甲": "da-jia",
}


class KTGHScraper(HospitalScraper):
    hospital_id = "ktgh"
    display_name = "光田綜合醫院"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return {}

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        async with httpx.AsyncClient(
            timeout=15, verify=False, follow_redirects=True
        ) as client:
            resp = await client.get(
                PROGRESS_URL,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
                },
            )
            resp.raise_for_status()

        return self._parse(resp.text, dept_code)

    def _parse(self, html: str, dept_filter: str) -> list[DoctorProgress]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        results: list[DoctorProgress] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            location = cells[0].get_text(strip=True)
            doctor_name = cells[1].get_text(strip=True)
            dept_name = cells[2].get_text(strip=True)
            raw_number = cells[3].get_text(strip=True)

            if not doctor_name:
                continue
            if dept_filter and dept_filter not in dept_name:
                continue

            number, status = _parse_status(raw_number)
            results.append(DoctorProgress(
                sub_dept=dept_name,
                location=location,
                doctor_name=doctor_name,
                current_number=number,
                next_number="",
                status=status,
            ))

        return results


_STATUS_KEYWORDS = ("休診", "暫停", "停診", "代診", "請假", "額滿")


def _parse_status(raw: str) -> tuple[int, str]:
    if not raw:
        return 0, ""
    for kw in _STATUS_KEYWORDS:
        if kw in raw:
            return 0, raw
    nums = re.findall(r"\d+", raw)
    return (int(nums[0]) if nums else 0), ""
