import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import DoctorProgress, HospitalScraper, get_current_time_code

PROGRESS_BASE_URL = "https://www.chimei.org.tw/clinicprogress"

BRANCHES = {
    "奇美總院": "10",
    "奇美柳營": "13",
    "奇美樹林": "14",
}

DEPARTMENTS = {
    "一般內科": "731",
    "心臟血管內科": "732",
    "腦神經內科": "733",
    "腎臟科": "734",
    "胃腸肝膽科": "735",
    "內分泌新陳代謝科": "736",
    "胸腔內科": "737",
    "血液腫瘤科": "738",
    "風濕免疫科": "739",
    "感染症科": "7302",
    "一般外科": "751",
    "大腸直腸外科": "7504",
    "小兒外科": "757",
    "心臟血管外科": "758",
    "乳房醫學中心": "750G",
    "骨科": "752",
    "泌尿外科": "754",
    "神經外科": "753",
    "胸腔外科": "755",
    "整形外科": "756",
    "直腸肛門外科": "759",
    "小兒科": "761",
    "婦產科": "772",
    "耳鼻喉科": "790",
    "眼科": "791",
    "皮膚科": "792",
    "家庭醫學科": "793",
    "精神科": "794",
    "復健科": "795",
    "牙科": "796",
    "放射腫瘤科": "798",
    "麻醉科": "799",
    "急診醫學科": "797",
    "中醫部": "7A0",
}

_DEPT_TYPE = {}
for name, code in DEPARTMENTS.items():
    if any(kw in name for kw in ["外科", "骨科", "乳房"]):
        _DEPT_TYPE[code] = "2"
    elif any(kw in name for kw in ["小兒", "婦產"]):
        _DEPT_TYPE[code] = "3"
    else:
        _DEPT_TYPE[code] = "1"


class ChiMeiScraper(HospitalScraper):
    hospital_id = "chimei"
    display_name = "奇美醫療體系"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return DEPARTMENTS

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        if time_code is None:
            time_code = get_current_time_code()

        itype = _DEPT_TYPE.get(dept_code, "1")
        url = (
            f"{PROGRESS_BASE_URL}/dept.aspx"
            f"?cul=&idept={dept_code}&ihosp={branch_code}&itype={itype}"
        )
        async with httpx.AsyncClient(
            timeout=12, verify=False, follow_redirects=True
        ) as client:
            resp = await client.get(
                url,
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
        results: list[DoctorProgress] = []

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            first_cell = rows[0].find("td")
            if not first_cell:
                continue
            header_text = first_cell.get_text(strip=True)
            if "若要更新" in header_text or "請間隔" in header_text:
                continue

            doctor_name = ""
            sub_dept = ""
            m = re.match(r"^(.+?)\s+(.+)$", header_text)
            if m:
                doctor_name = m.group(1)
                sub_dept = m.group(2)
            else:
                doctor_name = header_text

            current_number = 0
            status = ""

            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)

                if "現在看到幾號" in label:
                    num, st = _parse_status(value)
                    current_number = num
                    if st:
                        status = st

            if doctor_name and ("若要更新" not in doctor_name):
                results.append(DoctorProgress(
                    sub_dept=sub_dept,
                    location="",
                    doctor_name=doctor_name,
                    current_number=current_number,
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
