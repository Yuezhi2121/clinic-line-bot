import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import DoctorProgress, HospitalScraper, get_current_time_code

BRANCHES = {
    "大林慈濟": "DL",
    "斗六慈濟": "TL",
    "關山慈濟": "GS",
}

_BASE_URLS = {
    "DL": "https://dlappsvr2.tzuchi-healthcare.org.tw/tchw/opdreg/OpdProgress.aspx?Loc=DL",
    "TL": "https://dlappsvr2.tzuchi-healthcare.org.tw/tchw/opdreg/OpdProgress.aspx?Loc=TL",
    "GS": "https://dlappsvr2.tzuchi-healthcare.org.tw/tchw/opdreg/OpdProgress.aspx?Loc=GS",
}


class TzuChiScraper(HospitalScraper):
    hospital_id = "tzuchi"
    display_name = "慈濟醫療體系"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return {}

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        url = _BASE_URLS.get(branch_code)
        if not url:
            return []

        async with httpx.AsyncClient(
            timeout=15, verify=False, follow_redirects=True
        ) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()

        return self._parse(resp.text, dept_code)

    def _parse(self, html: str, dept_filter: str) -> list[DoctorProgress]:
        soup = BeautifulSoup(html, "html.parser")

        data_rows = []
        seen = set()
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            found_header = False
            for row in rows:
                ths = row.find_all("th")
                if len(ths) == 4:
                    th_texts = [t.get_text(strip=True) for t in ths]
                    if th_texts[0] == "科別" and th_texts[2] == "醫師":
                        found_header = True
                        continue
                if not found_header:
                    continue
                cells = row.find_all("td")
                if len(cells) != 4:
                    continue
                texts = [c.get_text(strip=True) for c in cells]
                if texts[0] and texts[2]:
                    key = (texts[0], texts[2])
                    if key not in seen:
                        seen.add(key)
                        data_rows.append(texts)
            if data_rows:
                break

        results: list[DoctorProgress] = []
        for dept_name, location, doctor_name, raw_number in data_rows:
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
