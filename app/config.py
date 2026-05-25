import os
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

CGMH_PROGRESS_URL = "https://register.cgmh.org.tw/Progress/3"
HOSPITAL_CODE = "3"

SCRAPE_INTERVAL_SECONDS = 60

DEPARTMENTS = {
    "COVID-19服務": "00",
    "質子諮詢門診": "12",
    "核素治療諮詢門診": "20",
    "細胞治療諮詢門診": "17",
    "ROSA機器人手術系統諮詢門診": "18",
    "類流感暨COVID-19新冠門診": "01",
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
