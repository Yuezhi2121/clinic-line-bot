from dataclasses import dataclass

from app.scrapers.base import HospitalScraper
from app.scrapers.cch import CCHScraper
from app.scrapers.cgmh import CGMHScraper
from app.scrapers.chimei import ChiMeiScraper
from app.scrapers.jah import JAHScraper
from app.scrapers.ktgh import KTGHScraper
from app.scrapers.mmh import MMHScraper
from app.scrapers.ntuh import NTUHScraper
from app.scrapers.tahsda import TAHSDAScraper
from app.scrapers.tzuchi import TzuChiScraper
from app.scrapers.vghtc import VGHTCScraper

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
_register(ChiMeiScraper())
_register(CCHScraper())
_register(KTGHScraper())
_register(TzuChiScraper())
_register(JAHScraper())
_register(VGHTCScraper())


def get_all_hospital_names() -> list[str]:
    return list(_hospital_lookup.keys())


_CHAR_VARIANTS = {"臺": "台", "臺": "台"}

_ALIASES: dict[str, str] = {
    "彰基": "彰化基督教醫院",
    "台安": "臺安醫院",
    "台安醫院": "臺安醫院",
    "北醫": "台大總院",
    "台大醫院": "台大總院",
    "林口長庚醫院": "林口長庚",
    "高雄長庚醫院": "高雄長庚",
    "基隆長庚醫院": "基隆長庚",
    "桃園長庚醫院": "桃園長庚",
    "嘉義長庚醫院": "嘉義長庚",
    "雲林長庚醫院": "雲林長庚",
    "台北長庚醫院": "台北長庚",
    "光田醫院": "光田沙鹿",
    "奇美醫院": "奇美總院",
    "慈濟醫院": "大林慈濟",
    "大林慈濟醫院": "大林慈濟",
    "斗六慈濟醫院": "斗六慈濟",
    "關山慈濟醫院": "關山慈濟",
    "馬偕紀念醫院": "馬偕醫院",
    "仁愛醫院": "大里仁愛醫院",
    "大里仁愛": "大里仁愛醫院",
    "台中仁愛": "台中仁愛醫院",
    "榮總": "台中榮總",
    "台中榮民總醫院": "台中榮總",
    "臺中榮總": "台中榮總",
    "中榮": "台中榮總",
}


def _normalize(text: str) -> str:
    for old, new in _CHAR_VARIANTS.items():
        text = text.replace(old, new)
    return text


def find_hospital(name: str) -> HospitalEntry | None:
    """Exact or fuzzy match a hospital name to a HospitalEntry."""
    if name in _hospital_lookup:
        return _hospital_lookup[name]

    if name in _ALIASES:
        canonical = _ALIASES[name]
        if canonical in _hospital_lookup:
            return _hospital_lookup[canonical]

    norm = _normalize(name)

    norm_alias = _normalize(norm)
    for alias, canonical in _ALIASES.items():
        if _normalize(alias) == norm_alias:
            if canonical in _hospital_lookup:
                return _hospital_lookup[canonical]

    for key, entry in _hospital_lookup.items():
        norm_key = _normalize(key)
        if norm == norm_key or norm in norm_key or norm_key in norm:
            return entry

    return None


def get_scraper(hospital_id: str) -> HospitalScraper | None:
    return _scrapers.get(hospital_id)


def get_all_scrapers() -> dict[str, HospitalScraper]:
    return dict(_scrapers)
