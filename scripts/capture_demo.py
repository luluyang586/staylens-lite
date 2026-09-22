"""Launch the local app, execute the default form and capture verified screenshots."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
PORT=8510
URL=f"http://127.0.0.1:{PORT}"


def wait_until_ready(timeout=30):
    deadline=time.time()+timeout
    while time.time()<deadline:
        try:
            with urlopen(URL,timeout=1): return
        except Exception: time.sleep(.5)
    raise TimeoutError("Streamlit did not start")


def main():
    assets=ROOT/"docs/assets";assets.mkdir(parents=True,exist_ok=True)
    server=subprocess.Popen([sys.executable,"-m","streamlit","run","app.py",
        "--server.headless=true",f"--server.port={PORT}","--browser.gatherUsageStats=false"],
        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
    try:
        wait_until_ready()
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page(viewport={"width":1440,"height":1100})
            page.goto(URL,wait_until="networkidle")
            page.screenshot(path=assets/"staylens-form.png",full_page=True)
            page.get_by_role("button",name="开始分析").click()
            page.get_by_text("硬约束筛选后",exact=False).wait_for(timeout=30000)
            if page.locator("[data-testid=stException]").count():
                raise RuntimeError("Streamlit rendered an exception")
            page.get_by_text("硬约束筛选后",exact=False).scroll_into_view_if_needed()
            page.mouse.wheel(0,650);page.wait_for_timeout(1000)
            page.screenshot(path=assets/"staylens-results.png")
            browser.close()
    finally:
        server.terminate();server.wait(timeout=10)
    print("Browser smoke test passed; screenshots updated.")


if __name__=="__main__":main()
