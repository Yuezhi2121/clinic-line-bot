import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import DoctorProgress, HospitalScraper, get_current_time_code

PROGRESS_BASE_URL = "https://www.jah.org.tw/JCHReg/Progress"

BRANCHES = {
    "大里仁愛醫院": "J",
    "台中仁愛醫院": "U",
}

DEPARTMENTS = {
    "內科": "02",
    "外科": "03",
    "牙科": "04",
    "婦產科": "05",
    "兒童專科": "06",
    "其它專科": "07",
    "聯合門診": "09",
}


class JAHScraper(HospitalScraper):
    hospital_id = "jah"
    display_name = "仁愛醫療體系"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return DEPARTMENTS

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        if time_code is None:
            time_code = get_current_time_code()

        url = f"{PROGRESS_BASE_URL}/{branch_code}"
        async with httpx.AsyncClient(
            timeout=12, verify=False, follow_redirects=True
        ) as client:
            resp = await client.get(
                url,
                params={"dept": dept_code, "time": time_code},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    ),
                },
            )
            resp.raise_for_status()

        return self._parse(resp.text)

    def _parse(self, html: str) -> list[DoctorProgress]:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) <= 1:
                continue

            header = rows[0]
            header_texts = [c.get_text(strip=True) for c in header.find_all(["td", "th"])]
            if "醫師名" not in header_texts:
                continue

            results: list[DoctorProgress] = []
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                sub_dept = cells[0].get_text(strip=True)
                location = cells[1].get_text(strip=True)
                doctor_name = cells[2].get_text(strip=True)
                raw_current = cells[3].get_text(strip=True)
                raw_next = cells[4].get_text(strip=True)

                if not doctor_name:
                    continue

                number, status = _parse_status(raw_current)
                results.append(DoctorProgress(
                    sub_dept=sub_dept,
                    location=location,
                    doctor_name=doctor_name,
                    current_number=number,
                    next_number=raw_next,
                    status=status,
                ))

            if results:
                return results

        return []


_STATUS_KEYWORDS = ("休診", "暫停", "停診", "代診", "請假", "異動", "額滿")


def _parse_status(raw: str) -> tuple[int, str]:
    if not raw:
        return 0, ""
    for kw in _STATUS_KEYWORDS:
        if kw in raw:
            return 0, raw
    nums = re.findall(r"\d+", raw)
    return (int(nums[-1]) if nums else 0), ""
