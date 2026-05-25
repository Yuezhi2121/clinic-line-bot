from dataclasses import dataclass

from app.scrapers.base import HospitalScraper
from app.scrapers.cgmh import CGMHScraper
from app.scrapers.mmh import MMHScraper
from app.scrapers.ntuh import NTUHScraper
from app.scrapers.tahsda import TAHSDAScraper

_scrapers: dict[str, HospitalScraper] = {}


@dataclass
class HospitalEntry:
    scraper: HospitalScraper
    branch_code: str
    branch_name: str


_hospital_lookup: dict[str, HospitalEntry] = {}


def _register(scraper: HospitalScraper) -> None:
    _scrapers[scraper.hospital_id] = scraper
    for branch_name, branch_code in scraper.get_branches().items():
        _hospital_lookup[branch_name] = HospitalEntry(
            scraper=scraper,
            branch_code=branch_code,
            branch_name=branch_name,
        )


_register(CGMHScraper())
_register(NTUHScraper())
_register(MMHScraper())
_register(TAHSDAScraper())


def get_all_hospital_names() -> list[str]:
    return list(_hospital_lookup.keys())


_CHAR_VARIANTS = {"臺": "台", "臺": "台"}


def _normalize(text: str) -> str:
    for old, new in _CHAR_VARIANTS.items():
        text = text.replace(old, new)
    return text


def find_hospital(name: str) -> HospitalEntry | None:
    """Exact or fuzzy match a hospital name to a HospitalEntry."""
    if name in _hospital_lookup:
        return _hospital_lookup[name]

    norm = _normalize(name)
    for key, entry in _hospital_lookup.items():
        norm_key = _normalize(key)
        if norm == norm_key or norm in norm_key or norm_key in norm:
            return entry

    return None


def get_scraper(hospital_id: str) -> HospitalScraper | None:
    return _scrapers.get(hospital_id)


def get_all_scrapers() -> dict[str, HospitalScraper]:
    return dict(_scrapers)
