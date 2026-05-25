import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import (
    DoctorProgress,
    HospitalScraper,
    get_current_time_code,
    tw_now,
)

PROGRESS_BASE_URL = "https://www.cch.org.tw/opd_progress.aspx"

BRANCHES = {
    "彰化基督教醫院": "main",
}

DEPARTMENTS = {
    "胸腔內科": "0103",
    "胃腸肝膽科": "0104",
    "內分泌新陳代謝科": "0107",
    "過敏免疫風濕科": "0108",
    "泌尿外科": "0205",
    "婦產部": "0400",
    "骨科": "0204",
    "神經醫學部": "0600",
    "耳鼻喉暨頭頸部": "0700",
    "口腔癌特別門診": "0701",
    "皮膚科": "0800",
    "睡眠障礙特別門診": "2321",
    "高壓氧治療中心": "7160",
    "成人精神科": "0500",
    "疾管署專案門診": "0505",
    "牙周病科": "1003",
    "假牙補綴科": "1004",
    "齒顎矯正科": "1006",
    "家庭牙醫學科": "1009",
    "中醫部": "1700",
    "中醫內科": "1705",
    "中醫家庭暨社區醫學科": "1710",
    "兒童內科": "0300",
    "兒童感染科": "0301",
    "兒童胸腔暨重症醫學科": "0303",
    "兒童腎臟科": "0305",
    "兒童內分泌科": "0307",
    "兒童過敏免疫風濕科": "0308",
    "新生兒科": "0310",
    "兒童骨科": "0316",
    "青少年門診": "0320",
}

_SHIFT_MAP = {"1": "1", "2": "2", "3": "3"}


class CCHScraper(HospitalScraper):
    hospital_id = "cch"
    display_name = "彰化基督教醫院"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return DEPARTMENTS

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        if time_code is None:
            time_code = get_current_time_code()

        shift = _SHIFT_MAP.get(time_code, "1")
        now = tw_now()
        roc_year = now.year - 1911
        opd_dat = f"{roc_year}{now.strftime('%m%d')}"

        url = f"{PROGRESS_BASE_URL}?id={dept_code}&shift={shift}&opd_dat={opd_dat}"
        async with httpx.AsyncClient(timeout=12, verify=False) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()

        return self._parse(resp.text)

    def _parse(self, html: str) -> list[DoctorProgress]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        results: list[DoctorProgress] = []
        rows = table.find_all("tr")

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            date_text = cells[0].get_text(strip=True)
            location = cells[1].get_text(strip=True)
            doctor_name = cells[2].get_text(strip=True)
            raw_status = cells[3].get_text(strip=True)

            if not doctor_name:
                continue

            number, status = _parse_status(raw_status)

            loc_str = f"第{location}診" if location else ""

            results.append(DoctorProgress(
                sub_dept="",
                location=loc_str,
                doctor_name=doctor_name,
                current_number=number,
                next_number="",
                status=status,
            ))

        return results


_STATUS_KEYWORDS = ("休診", "暫停", "停診", "代診", "請假", "異動", "額滿")


def _parse_status(raw: str) -> tuple[int, str]:
    if not raw:
        return 0, ""
    for kw in _STATUS_KEYWORDS:
        if kw in raw:
            return 0, raw
    nums = re.findall(r"\d+", raw)
    return (int(nums[-1]) if nums else 0), ""
