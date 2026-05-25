from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DoctorProgress:
    sub_dept: str
    location: str
    doctor_name: str
    current_number: int
    next_number: str


def get_current_time_code() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "1"
    elif hour < 17:
        return "2"
    else:
        return "3"


TIME_CODE_LABELS = {"1": "上午診", "2": "下午診", "3": "晚間"}


class HospitalScraper(ABC):
    """Base class for all hospital scrapers."""

    @property
    @abstractmethod
    def hospital_id(self) -> str:
        """Unique identifier for this hospital system."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Display name shown to users."""

    @abstractmethod
    def get_branches(self) -> dict[str, str]:
        """Return {branch_display_name: branch_code} for multi-branch hospitals.
        Single-branch hospitals return a single entry.
        """

    @abstractmethod
    def get_departments(self) -> dict[str, str]:
        """Return {dept_display_name: dept_code}."""

    @abstractmethod
    async def fetch_progress(
        self, branch_code: str, dept_code: str, time_code: str | None = None
    ) -> list[DoctorProgress]:
        """Fetch real-time progress data."""

    def format_progress(
        self, branch_name: str, dept_name: str, time_code: str, doctors: list[DoctorProgress]
    ) -> str:
        time_label = TIME_CODE_LABELS.get(time_code, "")
        if not doctors:
            return f"目前 {branch_name} {dept_name}（{time_label}）沒有看診資料。"

        lines = [f"📋 {branch_name} {dept_name}（{time_label}）看診進度\n"]
        for d in doctors:
            status = f"目前第 {d.current_number} 號" if d.current_number else "尚未開始"
            next_info = f"（下一位：{d.next_number}）" if d.next_number else ""
            lines.append(f"🔹 {d.sub_dept} - {d.doctor_name}")
            lines.append(f"   {status}{next_info}")
            if d.location:
                lines.append(f"   📍 {d.location}")
            lines.append("")

        return "\n".join(lines).strip()
