import logging

logger = logging.getLogger(__name__)

_playwright = None
_browser = None


async def get_browser():
    """Return a shared headless Chromium instance, launching on first call."""
    global _playwright, _browser
    from playwright.async_api import async_playwright

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
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright is not None:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None
    logger.info("Playwright browser closed.")
