import httpx

from app.scrapers.base import DoctorProgress, HospitalScraper

OPD_API = (
    "https://publicmobileappservice20171114025941.azurewebsites.net"
    "/api/RegService/CallLightInfo/OPD"
)

BRANCHES = {"台中榮總": "main"}


class VGHTCScraper(HospitalScraper):
    hospital_id = "vghtc"
    display_name = "台中榮民總醫院"

    def get_branches(self) -> dict[str, str]:
        return BRANCHES

    def get_departments(self) -> dict[str, str]:
        return {}

    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            section_code = await self._resolve_section(client, dept_code)
            if not section_code:
                return []

            resp = await client.post(
                OPD_API,
                json={"OPDSection": section_code, "OPDRoom": "", "OPDTimeFlag": ""},
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("SRESULT") != "TRUE":
            return []

        return self._parse(data.get("RECORDS", []))

    async def _resolve_section(self, client: httpx.AsyncClient, user_input: str) -> str | None:
        """Fetch live section list from API and fuzzy-match user input."""
        resp = await client.post(
            OPD_API,
            json={"OPDSection": "GETLIST", "OPDRoom": "", "OPDTimeFlag": ""},
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("SRESULT") != "TRUE":
            return None

        all_sections: list[tuple[str, str]] = []
        for group in data.get("RECORDS", []):
            for item in group.get("SECTIONLIST", []):
                code = item.get("OPDSECTION", "")
                name = item.get("SECTIONNMC", "")
                if code and name:
                    all_sections.append((code, name))

        if not all_sections:
            return None

        for code, name in all_sections:
            if user_input == name or user_input == code:
                return code

        for code, name in all_sections:
            if user_input in name or name in user_input:
                return code

        return None

    def _parse(self, records: list[dict]) -> list[DoctorProgress]:
        results: list[DoctorProgress] = []
        for rec in records:
            doctor = rec.get("DRNMC", "").strip()
            room = rec.get("OPDROOM", "").strip()
            section = rec.get("SECTIONNMC") or ""
            place = rec.get("OPDROOMPLACE", "").strip()
            raw_cur = str(rec.get("CURSEQ", "")).strip()
            msg = rec.get("OPDMSG", "").strip()

            if not doctor:
                continue

            try:
                current_number = int(raw_cur) if raw_cur else 0
            except ValueError:
                current_number = 0

            status = msg if msg and any(kw in msg for kw in _STATUS_KEYWORDS) else ""
            location = f"{room}" if not place else f"{room}（{place}）"

            results.append(DoctorProgress(
                sub_dept=section,
                location=location,
                doctor_name=doctor,
                current_number=current_number,
                next_number="",
                status=status,
            ))

        return results


_STATUS_KEYWORDS = ("休診", "暫停", "停診", "代診", "請假", "額滿", "停止")
