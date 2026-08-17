from pathlib import Path

from playwright.sync_api import sync_playwright


OUT = Path(__file__).parent / "pro-dashboard.png"
TV_OUT = Path(__file__).parent / "pro-dashboard-tv.png"
MOBILE_OUT = Path(__file__).parent / "pro-dashboard-mobile.png"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("http://127.0.0.1:4380/", wait_until="networkidle")
    page.screenshot(path=str(OUT), full_page=True)
    assert page.get_by_role("heading", name="输出方式").is_visible()
    assert page.get_by_role("tab", name="本机播放").is_visible()
    page.get_by_role("tab", name="电视中转").click()
    page.wait_for_timeout(1200)
    assert page.locator("#tv-panel").is_visible()
    assert page.locator("#devices").inner_text()
    page.locator("#tv-audio").select_option("computer")
    assert page.locator("#tv-audio").input_value() == "computer"
    page.screenshot(path=str(TV_OUT), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="networkidle")
    page.screenshot(path=str(MOBILE_OUT), full_page=True)
    assert page.locator("body").bounding_box()["width"] <= 390
    browser.close()
