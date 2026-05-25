import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import DoctorProgress, HospitalScraper, get_current_time_code

BASE_URL = "https://reg.ntuh.gov.tw/WebReg/WebReg"

BRANCHES = {
    "台大總院": "T0",
    "台大兒童醫院": "CH",
    "台大癌醫中心": "C0",
    "台大北護分院": "T2",
    "台大金山分院": "T3",
    "台大新竹分院": "T4",
    "台大生醫分院": "T7",
    "台大雲林分院": "Y0",
}

DEPARTMENTS = {
    "內科": "MED",
    "老年醫學": "GERO",
    "家庭醫學": "FM",
    "神經部": "NEUR",
    "基因醫學": "GENE",
    "復健部": "PMR",
    "腫瘤醫學": "ONC",
    "精神部": "PSYC",
    "環境職業醫學": "EOM",
    "外科": "SURG",
    "骨科": "ORTH",
    "婦產部": "OBGY",
    "眼科": "OPH",
    "耳鼻喉部": "ENT",
    "口腔醫學": "DENT",
    "皮膚部": "DERM",
    "泌尿部": "URO",
}


class NTUHScraper(HospitalScraper):
    hospital_id = "ntuh"
    display_name = "台大醫院體系"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return DEPARTMENTS

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        if time_code is None:
            time_code = get_current_time_code()

        async with httpx.AsyncClient(timeout=15, verify=False, follow_redirects=True) as client:
            page_url = f"{BASE_URL}/ClinicCurrentLightNo?vHospCode={branch_code}"
            r1 = await client.get(page_url)
            token_match = re.findall(
                r'name="__RequestVerificationToken"[^>]*value="([^"]*)"', r1.text
            )
            if not token_match:
                return []

            r2 = await client.post(
                f"{BASE_URL}/DeptLightTable",
                data={
                    "__RequestVerificationToken": token_match[0],
                    "vHospitalCode": branch_code,
                    "DeptCode": dept_code,
                    "RegionCode": "",
                    "AmpmCode": time_code,
                },
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            r2.raise_for_status()

        return self._parse(r2.text)

    def _parse(self, html: str) -> list[DoctorProgress]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_="clinic-room-number")
        results: list[DoctorProgress] = []

        for card in cards:
            room = card.find("div", class_="room-number")
            doc_name = card.find("div", class_="clinic-doc-name")
            clinic_type = card.find("div", class_="clinic-type")
            number_div = card.find("div", class_="number")

            num_text = number_div.get_text(strip=True) if number_div else ""
            current = _parse_number(num_text)

            results.append(
                DoctorProgress(
                    sub_dept=clinic_type.get_text(strip=True) if clinic_type else "",
                    location=room.get_text(strip=True) if room else "",
                    doctor_name=doc_name.get_text(strip=True) if doc_name else "",
                    current_number=current,
                    next_number="",
                )
            )

        return results


def _parse_number(raw: str) -> int:
    if not raw:
        return 0
    nums = re.findall(r"\d+", raw)
    return int(nums[0]) if nums else 0
