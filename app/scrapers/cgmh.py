import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import DoctorProgress, HospitalScraper, get_current_time_code

PROGRESS_BASE_URL = "https://register.cgmh.org.tw/Progress"

BRANCHES = {
    "基隆長庚": "2",
    "情人湖院區": "E",
    "台北長庚": "1",
    "長庚診所": "B",
    "土城醫院": "V",
    "林口長庚": "3",
    "桃園長庚": "5",
    "雲林長庚": "M",
    "嘉義長庚": "6",
    "高雄長庚": "8",
    "鳳山醫院": "T",
}

DEPARTMENTS = {
    "內科": "02",
    "外科": "03",
    "牙科": "04",
    "婦產科": "05",
    "兒童專科": "06",
    "其它專科": "07",
    "中醫": "08",
    "聯合門診": "09",
    "癌症中心": "10",
    "自費門診": "13",
    "預防保健": "16",
}


class CGMHScraper(HospitalScraper):
    hospital_id = "cgmh"
    display_name = "長庚醫療體系"

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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                data={"dept": dept_code, "time": time_code},
                headers={"User-Agent": "Mozilla/5.0", "Referer": url},
            )
            resp.raise_for_status()

        return self._parse(resp.text)

    def _parse(self, html: str) -> list[DoctorProgress]:
        soup = BeautifulSoup(html, "html.parser")
        result_div = soup.find("div", id="divDeptResult")
        table = (result_div.find("table") if result_div else None) or (
            soup.find("table") if not result_div else None
        )
        if not table:
            return []

        results: list[DoctorProgress] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            raw_status = cells[3].get_text(strip=True)
            number, status = _parse_status(raw_status)
            results.append(DoctorProgress(
                sub_dept=cells[0].get_text(strip=True),
                location=cells[1].get_text(strip=True),
                doctor_name=cells[2].get_text(strip=True),
                current_number=number,
                next_number=cells[4].get_text(strip=True) if len(cells) > 4 else "",
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
