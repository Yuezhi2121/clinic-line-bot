import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import DoctorProgress, HospitalScraper, get_current_time_code

PROGRESS_URL = "https://www.hc.mmh.org.tw/progress.php"

BRANCHES = {
    "馬偕醫院": "all",
}

DEPARTMENTS = {
    "內分泌科": "12",
    "胃腸肝膽科": "13",
    "心臟內科": "14",
    "胸腔內科": "15",
    "腎臟內科": "16",
    "血液腫瘤科": "18",
    "過敏免疫風濕科": "19",
    "感染科": "26",
    "老年醫學科": "1G",
    "神經內科": "20",
    "精神科": "21",
    "皮膚科": "24",
    "疼痛科": "28",
    "眼科": "70",
    "耳鼻喉科": "71",
    "牙科": "72",
    "復健科": "73",
    "家庭醫學科": "75",
    "一般外科": "50",
    "小兒外科": "51",
    "骨科": "52",
    "神經外科": "53",
    "泌尿科": "54",
    "整形外科": "55",
    "大腸直腸外科": "56",
    "乳房外科": "57",
    "心臟血管外科": "67",
    "胸腔外科": "68",
    "婦產科": "60",
    "小兒科": "40",
}

TIME_MAP = {"1": "1", "2": "2", "3": "3"}


class MMHScraper(HospitalScraper):
    hospital_id = "mmh"
    display_name = "馬偕醫院"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return DEPARTMENTS

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        if time_code is None:
            time_code = get_current_time_code()

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                PROGRESS_URL,
                data={"dept": dept_code, "ap": time_code},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()

        return self._parse(r.text)

    def _parse(self, html: str) -> list[DoctorProgress]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        results: list[DoctorProgress] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            raw_status = cells[3].get_text(strip=True)
            number, status = _parse_status(raw_status)
            results.append(
                DoctorProgress(
                    sub_dept=cells[0].get_text(strip=True),
                    location=cells[1].get_text(strip=True),
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
