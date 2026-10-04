"""
Capture docs/screenshots/*.png from the running stack, with a headless browser in Docker.

    docker compose --profile app up -d          # Airflow + dashboard must be running
    docker run --rm --network nomadhub_default --user "$(id -u)" -e HOME=/tmp \\
      -v "$PWD:/work" -w /work mcr.microsoft.com/playwright/python:v1.63.0-noble \\
      bash -c "pip install -q --user --break-system-packages playwright==1.63.0 && python scripts/take_screenshots.py"

(The image ships the browsers but not the Python package, hence the pip install.)

The container reaches the services by their compose names (dashboard, airflow-apiserver).
The two AI pages make real Gemini calls (one RAG question, one text-to-SQL question).
"""

import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DASHBOARD = os.getenv("DASHBOARD_URL", "http://dashboard:8501")
AIRFLOW = os.getenv("AIRFLOW_URL", "http://airflow-apiserver:8080")
OUT = Path("docs/screenshots")
VIEWPORT = {"width": 1440, "height": 900}

PAGES = [  # file name, dashboard path
    ("01_overview", ""),
    ("02_airline_reliability", "airlines"),
    ("03_city_revenue", "cities"),
    ("04_forward_occupancy", "occupancy"),
    ("05_review_insights", "reviews"),
]


def wait_for_charts(page: Page) -> None:
    page.wait_for_selector(".js-plotly-plot", timeout=180_000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)          # let Plotly finish its transitions


def shoot(page: Page, name: str, fit_content: bool = True) -> None:
    """Streamlit scrolls inside its main container, so a browser "full page" shot would
    cut long pages off. Grow the viewport to the content height instead, then shoot."""
    if fit_content:
        height = page.evaluate(
            "() => { const m = document.querySelector('[data-testid=stMain]');"
            " return m ? m.scrollHeight : document.body.scrollHeight; }")
        page.set_viewport_size({"width": VIEWPORT["width"], "height": max(VIEWPORT["height"], height + 24)})
        page.wait_for_timeout(1500)       # Plotly re-renders on resize
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    page.set_viewport_size(VIEWPORT)
    print(f"✓ {path}")


def dashboard(page: Page) -> None:
    for name, path in PAGES:
        page.goto(f"{DASHBOARD}/{path}", wait_until="networkidle")
        wait_for_charts(page)
        shoot(page, name)

    # RAG: ask one question, wait for the cited answer
    page.goto(f"{DASHBOARD}/chat", wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.get_by_role("textbox").last.fill("Is it noisy at night in Tokyo? Can I sleep well?")
    page.keyboard.press("Enter")
    page.wait_for_selector("[data-testid=stChatMessage] >> nth=1", timeout=180_000)
    page.wait_for_timeout(2000)
    shoot(page, "06_chat_with_reviews")      # sources stay collapsed: the answer is the point

    # Text-to-SQL: one example question → SQL + chart
    page.goto(f"{DASHBOARD}/ask", wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Top 5 cities by platform revenue in 2024").click()
    wait_for_charts(page)
    shoot(page, "07_ask_the_warehouse")


def airflow(page: Page) -> None:
    page.goto(f"{AIRFLOW}/auth/login/", wait_until="networkidle")
    page.fill("input[name=username]", "admin")
    page.fill("input[name=password]", "admin")
    page.keyboard.press("Enter")
    page.wait_for_url(lambda url: "/auth/login" not in url, timeout=60_000)
    page.goto(f"{AIRFLOW}/dags/nomad_hub_daily", wait_until="networkidle")
    page.wait_for_timeout(4000)
    graph = page.get_by_role("button", name="Graph")
    if graph.count():
        graph.first.click()
        page.wait_for_timeout(3000)
    shoot(page, "08_airflow_dag", fit_content=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, color_scheme="light", device_scale_factor=1)
        dashboard(page)
        airflow(page)
        browser.close()


if __name__ == "__main__":
    main()
