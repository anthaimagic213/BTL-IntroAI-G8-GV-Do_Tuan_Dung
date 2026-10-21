"""Kiểm thử tùy chọn: python tests/browser_smoke.py (cần playwright).

Dùng Chrome/Edge có sẵn; hoặc chạy `python -m playwright install chromium`.
Tự mở server local cổng tạm và luôn đóng server/trình duyệt khi kết thúc.
"""

from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urlopen(url, timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError("Không khởi động được server kiểm thử.")
        with sync_playwright() as p:
            executable = next((str(path) for path in (
                Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            ) if path.exists()), None)
            browser = p.chromium.launch(headless=True, executable_path=executable)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            cells = page.locator(".cell")
            expect(cells).to_have_count(81)
            cells.nth(0).fill("a")
            expect(cells.nth(0)).to_have_value("")
            cells.nth(0).fill("5")
            expect(cells.nth(0)).to_have_value("5")
            page.locator("#algorithm").select_option("min_conflicts")
            expect(page.locator("#local-warning")).to_be_visible()
            page.locator("#algorithm").select_option("fc_mrv")
            expect(page.locator("#local-warning")).to_be_hidden()
            page.locator("#sample").click()
            expect(cells.nth(0)).to_have_value("5")
            page.locator("#speed").evaluate("e => { e.value = '1000'; e.dispatchEvent(new Event('input')); }")
            # Border bên trong 1px; cạnh block 3px.
            assert cells.nth(1).evaluate("e => getComputedStyle(e).borderRightWidth") == "1px"
            assert cells.nth(2).evaluate("e => getComputedStyle(e).borderRightWidth") == "3px"
            with page.expect_response("**/api/solve") as pending:
                page.locator("#play").click()
            response = pending.value.json()
            assert response["status"] == "success"
            expect(page.locator("#pause")).to_be_visible()
            assert cells.nth(0).evaluate("e => e.readOnly"), page.locator("#status").inner_text()
            page.locator("#pause").click()
            index = page.locator("#step-label").inner_text()
            page.wait_for_timeout(150)
            assert page.locator("#step-label").inner_text() == index
            page.locator("#speed").evaluate("e => { e.value = '1'; e.dispatchEvent(new Event('input')); }")
            page.locator("#pause").click()
            expect(page.locator("#phase-label")).to_have_text("THÀNH CÔNG", timeout=15000)
            assert cells.evaluate_all("es => es.map(e => Number(e.value))") == [v for row in response["history"][-1]["board_snapshot"] for v in row]
            assert "board-success" in page.locator("#board").get_attribute("class")
            assert int(page.locator("#assignments").inner_text().replace(".", "")) == response["metrics"]["assignments"]
            scroll = page.locator("#console").evaluate("e => ({height: e.scrollHeight, top: e.scrollTop, client: e.clientHeight})")
            assert scroll["height"] - scroll["top"] - scroll["client"] <= 2, scroll
            expect(page.locator("#play")).to_have_text("↻ Giải lại đề gốc")

            # Giải lại phải gửi lại đề gốc, không gửi bảng đã giải.
            page.locator("#algorithm").select_option("mac")
            with page.expect_request("**/api/solve") as request:
                page.locator("#play").click()
            assert request.value.post_data_json["board"][0][2] == 0
            expect(page.locator("#phase-label")).to_have_text("THÀNH CÔNG", timeout=15000)

            # Clear đang replay phải hủy timer, không cho snapshot cũ ghi đè.
            page.locator("#sample").click()
            page.locator("#speed").evaluate("e => { e.value = '50'; e.dispatchEvent(new Event('input')); }")
            page.locator("#play").click()
            expect(page.locator("#pause")).to_be_visible()
            page.locator("#clear").click()
            page.wait_for_timeout(150)
            assert cells.evaluate_all("es => es.every(e => e.value === '')")
            expect(page.locator("#play")).to_be_enabled()
            expect(page.locator("#pause")).to_be_hidden()

            # Backend 422 phải hiển thị thông báo chứ không replay dữ liệu sai.
            cells.nth(0).fill("5")
            cells.nth(1).fill("5")
            page.locator("#play").click()
            expect(page.locator("#phase-label")).to_have_text("LỖI")
            expect(page.locator("#status")).to_contain_text("trùng")
            page.locator("#sample").click()

            for width in (1440, 900, 390):
                page.set_viewport_size({"width": width, "height": 1000})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            page.set_viewport_size({"width": 1440, "height": 1000})
            artifacts = ROOT / "docs" / "screenshots"
            artifacts.mkdir(exist_ok=True)
            page.screenshot(path=str(artifacts / "desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(artifacts / "mobile.png"), full_page=True)
            assert not errors, errors
            browser.close()
            print("PASS: real HTTP, input, borders, warning, replay, pause/resume, metrics, autoscroll, rerun, clear, 422, responsive; no JS page errors.")
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    main()