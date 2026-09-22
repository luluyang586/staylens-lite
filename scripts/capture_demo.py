"""Launch the local app, execute the default form and capture verified screenshots."""
from __future__ import annotations

import subprocess
import sys
import time
import os
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
    env=os.environ.copy()
    # Browser smoke tests must never trigger paid model calls from a local .env.
    env.update({
        "LLM_API_KEY":"",
        "OPENAI_API_KEY":"",
        "ANTHROPIC_API_KEY":"",
        "LLM_MODEL":"",
        "DUCKDB_PATH":"data/staylens_demo.duckdb",
    })
    server=subprocess.Popen([sys.executable,"-m","streamlit","run","app.py",
        "--server.headless=true",f"--server.port={PORT}","--browser.gatherUsageStats=false"],
        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT,env=env)
    try:
        wait_until_ready()
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page(viewport={"width":1440,"height":1100})
            page.goto(URL,wait_until="networkidle")
            page.get_by_text("用真实公开数据，快速比较悉尼住宿选择",exact=True).wait_for(timeout=30000)
            page.get_by_role("button",name="查看推荐").wait_for(timeout=30000)
            page.screenshot(path=assets/"staylens-form.png",full_page=True)
            page.get_by_role("button",name="查看推荐").click()
            page.get_by_text("个符合条件的房源",exact=False).wait_for(timeout=30000)
            if page.locator("[data-testid=stException]").count():
                raise RuntimeError("Streamlit rendered an exception")
            first_reason=page.get_by_text("推荐理由",exact=True).first
            first_reason.wait_for(timeout=30000)
            first_reason.scroll_into_view_if_needed()
            page.mouse.wheel(0,-250);page.wait_for_timeout(1000)
            page.screenshot(path=assets/"staylens-results.png")
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill();server.wait(timeout=5)
    print("Browser smoke test passed; screenshots updated.")


if __name__=="__main__":main()
