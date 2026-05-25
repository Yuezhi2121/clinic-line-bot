import logging
from playwright.async_api import async_playwright, Browser, Playwright

logger = logging.getLogger(__name__)

_playwright: Playwright | None = None
_browser: Browser | None = None


async def get_browser() -> Browser:
    """Return a shared headless Chromium instance, launching on first call."""
    global _playwright, _browser
    if _browser is None or not _browser.is_connected():
        logger.info("Launching headless Chromium…")
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ],
        )
    return _browser


async def close_browser() -> None:
    """Shut down Chromium and Playwright. Call on app exit."""
    global _playwright, _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None
    logger.info("Playwright browser closed.")
