import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    FollowEvent,
    JoinEvent,
    MessageEvent,
    TextMessageContent,
)
from linebot.v3.webhook import WebhookParser

from app.config import LINE_CHANNEL_SECRET
from app.database import close_db, get_db
from app.line_handler import handle_text_message, reply_message, WELCOME_TEXT
from app.scheduler import start_scheduler, stop_scheduler
from app.scrapers.browser import close_browser

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
    await close_browser()
    await close_db()


app = FastAPI(title="Clinic Progress LINE Bot", lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Clinic Progress LINE Bot is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    logger.info("Webhook received, body length=%d", len(body))

    if not signature:
        logger.warning("Missing X-Line-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.exception("Error parsing webhook: %s", e)
        return {"status": "error", "detail": str(e)}

    for event in events:
        if isinstance(event, FollowEvent):
            logger.info("New follower: %s", event.source.user_id)
            try:
                reply_message(event.reply_token, WELCOME_TEXT)
            except Exception as e:
                logger.exception("Error sending welcome: %s", e)

        elif isinstance(event, JoinEvent):
            logger.info("Bot joined group/room")
            try:
                reply_message(event.reply_token, WELCOME_TEXT)
            except Exception as e:
                logger.exception("Error sending welcome to group: %s", e)

        elif isinstance(event, MessageEvent) and isinstance(
            event.message, TextMessageContent
        ):
            user_id = event.source.user_id
            text = event.message.text
            is_group = event.source.type in ("group", "room")
            logger.info("Message from %s (group=%s): %s", user_id, is_group, text)

            try:
                reply_text = await handle_text_message(user_id, text, is_group=is_group)
                if reply_text is not None:
                    reply_message(event.reply_token, reply_text)
            except Exception as e:
                logger.exception("Error handling message: %s", e)

    return {"status": "ok"}


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
