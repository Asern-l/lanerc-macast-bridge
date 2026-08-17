from pathlib import Path

from playwright.sync_api import sync_playwright


OUT = Path(__file__).parent / "pro-dashboard.png"
TV_OUT = Path(__file__).parent / "pro-dashboard-tv.png"
MOBILE_OUT = Path(__file__).parent / "pro-dashboard-mobile.png"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    console_errors = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto("http://127.0.0.1:4380/", wait_until="networkidle")
    status_response = page.request.get("http://127.0.0.1:4380/api/status")
    assert status_response.ok
    status_payload = status_response.json()
    assert status_payload["ok"] is True
    assert status_payload["data"]["app"]["version"] == "2.0.1"
    saved_settings = {
        key: status_payload["data"][key]
        for key in ("mode", "player", "selected_tv", "tv_audio", "audio_delay", "auto_sync")
    }
    save_response = page.request.post(
        "http://127.0.0.1:4380/api/settings", data=saved_settings
    )
    assert save_response.ok
    assert save_response.json()["ok"] is True
    invalid_response = page.request.post(
        "http://127.0.0.1:4380/api/settings",
        data={**saved_settings, "mode": "invalid"},
    )
    assert invalid_response.status == 400
    assert invalid_response.json()["error"]["code"] == "invalid_settings"
    page.screenshot(path=str(OUT), full_page=True)
    assert page.get_by_role("heading", name="播放位置").is_visible()
    assert page.get_by_role("radio", name="本机播放 使用 PotPlayer 或 Macast 内置播放器").is_visible()
    page.get_by_role("radio", name="电视播放 电脑兼容转码后发送到 DLNA 电视").click()
    page.wait_for_timeout(1200)
    assert page.locator("#tv-panel").is_visible()
    assert page.locator("#devices").inner_text()
    page.locator('input[name="tv-audio"][value="computer"]').check()
    assert page.locator("#sync-panel").is_visible()
    page.locator("#auto-sync").uncheck()
    page.locator("#audio-delay").fill("2.5")
    assert page.locator("#audio-delay-value").evaluate("element => element.value") == "2.5 秒"
    assert page.locator("#save").is_enabled()
    page.screenshot(path=str(TV_OUT), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="networkidle")
    page.screenshot(path=str(MOBILE_OUT), full_page=True)
    assert page.locator("body").bounding_box()["width"] <= 390
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert not console_errors
    browser.close()
