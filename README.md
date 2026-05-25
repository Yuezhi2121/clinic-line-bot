# 林口長庚看診進度 LINE Bot

自動監控林口長庚醫院看診進度，透過 LINE 推播通知讓你掌握看診號碼。

## 功能

- **查詢看診進度** - 輸入科別名稱即可查看該科所有醫師的看診進度
- **訂閱通知** - 輸入你的看診號碼，系統每 60 秒自動檢查，有更新就推播通知
- **智慧提醒** - 剩 3 位以內時加強提醒，已到號時立即通知
- **自動清理** - 過號太久自動取消訂閱

## 指令

| 指令 | 說明 |
|------|------|
| `內科` / `中醫` / `外科` ... | 查詢該科看診進度 |
| `科別` | 顯示所有可查詢的科別 |
| `訂閱` | 開始訂閱看診進度（互動式引導） |
| `狀態` | 查看你的訂閱狀態 |
| `取消` | 取消所有訂閱 |
| `幫助` | 顯示指令說明 |

## 設定步驟

### 1. 建立 LINE Channel

1. 前往 [LINE Developers Console](https://developers.line.biz/)
2. 登入你的 LINE 帳號
3. 點選 **Create a new provider**（或選擇已有的 Provider）
4. 點選 **Create a Messaging API channel**
5. 填寫 Channel 基本資料（名稱、描述等）
6. 建立完成後，進入 Channel 設定頁面
7. 在 **Basic settings** 中找到 **Channel secret**，複製備用
8. 在 **Messaging API** 分頁中：
   - 點選 **Issue** 產生 **Channel access token (long-lived)**，複製備用
   - 關閉 **Auto-reply messages**（自動回覆）
   - 關閉 **Greeting messages**（加好友歡迎訊息）

### 2. 本地開發

```bash
# 安裝套件
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env 填入你的 LINE Channel Secret 和 Access Token

# 啟動伺服器
python -m app.main
```

伺服器會在 `http://localhost:8000` 啟動。

### 3. 使用 ngrok 測試（本地開發用）

```bash
# 安裝 ngrok 後
ngrok http 8000
```

將 ngrok 產生的 HTTPS 網址 + `/callback` 設定到 LINE Channel 的 Webhook URL。
例如：`https://xxxx.ngrok-free.app/callback`

### 4. 部署到 Railway（24/7 不休眠）

**方法 A：透過 GitHub**

1. 將專案推送到 GitHub
2. 前往 [Railway](https://railway.com)，點選 **New Project** -> **Deploy from GitHub repo**
3. 選擇你的 repo，Railway 會自動偵測 `railway.json` 並部署
4. 在 **Variables** 中設定環境變數：
   - `LINE_CHANNEL_SECRET`
   - `LINE_CHANNEL_ACCESS_TOKEN`
5. 在 **Settings** -> **Networking** -> **Public Networking** 中產生一個公開網域
6. 將該網域 + `/callback` 設定到 LINE Channel 的 Webhook URL

**方法 B：透過 CLI**

```bash
# 安裝 Railway CLI
npm install -g @railway/cli

# 登入
railway login

# 初始化專案
railway init

# 設定環境變數
railway variables --set "LINE_CHANNEL_SECRET=你的secret"
railway variables --set "LINE_CHANNEL_ACCESS_TOKEN=你的token"

# 部署
railway up

# 取得公開網址
railway domain
```

部署完成後，將 Railway 給你的網址 + `/callback` 設定到 LINE Webhook URL。

## 技術架構

- **Python 3.11+** / **FastAPI**
- **line-bot-sdk** v3
- **httpx** + **BeautifulSoup4** - 爬取長庚看診進度
- **APScheduler** - 定時排程（每 60 秒檢查一次）
- **aiosqlite** - SQLite 非同步資料庫

## 專案結構

```
app/
  main.py           # FastAPI 入口 + LINE webhook
  config.py         # 環境變數與常數
  database.py       # SQLite 資料庫管理
  scraper.py        # 長庚看診進度爬蟲
  line_handler.py   # LINE 訊息處理與對話流程
  notifier.py       # LINE 推播通知
  scheduler.py      # 定時排程任務
```
