import logging
import re

from app.scrapers.base import DoctorProgress, HospitalScraper
from app.scrapers.browser import get_browser

logger = logging.getLogger(__name__)

BASE_URL = "https://sysint.csh.org.tw/Register/CshVRProgressA.aspx"

BRANCHES = {
    "中山醫大慶院區": "A",
    "中山中興分院": "G",
}

DEPARTMENTS = {
    "內科": "內科",
    "肝膽腸胃內科": "肝膽腸胃內科",
    "心臟血管內科": "心臟血管內科",
    "胸腔內科": "胸腔內科",
    "腎臟內科": "腎臟內科",
    "血液腫瘤科": "血液腫瘤科",
    "內分泌科": "內分泌科",
    "感染科": "感染科",
    "過敏免疫風濕科": "過敏免疫風濕科",
    "外科": "外科",
    "心臟血管外科": "心臟血管外科",
    "消化外科": "消化外科",
    "小兒科": "小兒科",
    "婦產科": "婦產科",
    "家庭醫學科": "家庭醫學科",
    "骨科": "骨科",
    "神經外科": "神經外科",
    "泌尿科": "泌尿科",
    "耳鼻喉科": "耳鼻喉科",
    "眼科": "眼科",
    "皮膚科": "皮膚科",
    "神經內科": "神經內科",
    "身心科": "身心科",
    "復健科": "復健科",
    "整形外科": "整形外科",
    "口腔顎面外科": "口腔顎面外科",
    "中西整合醫療科": "中西整合醫療科",
    "放射腫瘤科": "放射腫瘤科",
}


class CSMUScraper(HospitalScraper):
    hospital_id = "csmu"
    display_name = "中山醫學大學附設醫院"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return DEPARTMENTS

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        browser = await get_browser()
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        try:
            page = await context.new_page()
            await page.goto(BASE_URL, wait_until="networkidle", timeout=20000)

            await page.click(f'input[name="rblZone"][value="{branch_code}"]')
            await page.wait_for_timeout(500)

            # Click 看診進度查詢 to enter progress mode
            await page.click('input[name="Button2"]')
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Click the department link (cross-page PostBack to CshVRProgressA2)
            link = page.locator('a[href*="ProgressA2"]').filter(has_text=dept_code).first
            if not await link.count():
                logger.warning("Department link not found: %s", dept_code)
                return []

            async with page.expect_navigation(timeout=20000):
                await link.click()

            html = await page.content()
            return self._parse(html, time_code)
        except Exception:
            logger.exception("CSMU Playwright scrape failed for %s / %s", branch_code, dept_code)
            return []
        finally:
            await context.close()

    def _parse(self, html: str, time_code: str | None = None) -> list[DoctorProgress]:
        from bs4 import BeautifulSoup
        from app.scrapers.base import get_current_time_code

        if time_code is None:
            time_code = get_current_time_code()

        col_idx = {"1": 1, "2": 2, "3": 3}.get(time_code, 1)

        soup = BeautifulSoup(html, "html.parser")
        dl3 = soup.find(id="DataList3")
        if not dl3:
            return []

        results: list[DoctorProgress] = []
        for row in dl3.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            cell = cells[col_idx] if col_idx < len(cells) else None
            if not cell:
                continue

            cell_html = cell.decode_contents().strip()
            if not cell_html:
                continue

            results.extend(self._parse_cell(cell))

        return results

    def _parse_cell(self, cell) -> list[DoctorProgress]:
        """Extract doctor progress entries from a single time-slot cell."""
        results: list[DoctorProgress] = []

        tables = cell.find_all("table")
        if tables:
            for t in tables:
                for row in t.find_all("tr"):
                    tds = row.find_all("td")
                    texts = [td.get_text(strip=True) for td in tds]
                    texts = [t for t in texts if t]
                    if len(texts) >= 2:
                        doctor = texts[0]
                        raw = texts[-1]
                        location = texts[1] if len(texts) >= 3 else ""
                        number, status = _parse_status(raw)
                        results.append(DoctorProgress(
                            sub_dept="",
                            location=location,
                            doctor_name=doctor,
                            current_number=number,
                            next_number="",
                            status=status,
                        ))
            return results

        divs = cell.find_all("div")
        if divs:
            for div in divs:
                txt = div.get_text(strip=True)
                if not txt:
                    continue
                parts = re.split(r"[\s/|]+", txt)
                parts = [p for p in parts if p]
                if len(parts) >= 2:
                    doctor = parts[0]
                    raw = parts[-1]
                    number, status = _parse_status(raw)
                    results.append(DoctorProgress(
                        sub_dept="",
                        location="",
                        doctor_name=doctor,
                        current_number=number,
                        next_number="",
                        status=status,
                    ))
            return results

        raw_text = cell.get_text("\n", strip=True)
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
        for line in lines:
            parts = re.split(r"[\s/|]+", line)
            parts = [p for p in parts if p]
            if len(parts) >= 2:
                doctor = parts[0]
                raw = parts[-1]
                number, status = _parse_status(raw)
                results.append(DoctorProgress(
                    sub_dept="",
                    location="",
                    doctor_name=doctor,
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
