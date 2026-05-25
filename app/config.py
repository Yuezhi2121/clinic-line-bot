import os
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

CGMH_PROGRESS_BASE_URL = "https://register.cgmh.org.tw/Progress"

SCRAPE_INTERVAL_SECONDS = 60

HOSPITALS = {
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

HOSPITAL_CODE_TO_NAME = {v: k for k, v in HOSPITALS.items()}

# Common departments across all CGMH branches
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

DEPT_CODE_TO_NAME = {v: k for k, v in DEPARTMENTS.items()}

DB_PATH = os.getenv("DB_PATH", "clinic_bot.db")
