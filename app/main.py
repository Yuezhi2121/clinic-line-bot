import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
)
from linebot.v3.webhook import WebhookParser

from app.config import LINE_CHANNEL_SECRET
from app.database import close_db, get_db
from app.line_handler import handle_text_message, reply_message
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

parser = WebhookParser(channel_secret=LINE_CHANNEL_SECRET)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    await get_db()
    start_scheduler()
    yield
    logger.info("Shutting down...")
    stop_scheduler()
    await close_db()


app = FastAPI(title="Clinic Progress LINE Bot", lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Clinic Progress LINE Bot is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    body = (await request.body()).decode("utf-8")

    try:
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(
            event.message, TextMessageContent
        ):
            user_id = event.source.user_id
            text = event.message.text
            logger.info("Message from %s: %s", user_id, text)

            reply_text = await handle_text_message(user_id, text)
            reply_message(event.reply_token, reply_text)

    return {"status": "ok"}


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
