"""Browser acceptance test against the generated catalogue or published URL."""
import os
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, expect

HOME_URL = os.environ.get("TEST_URL", "http://127.0.0.1:8765/")
URL = urljoin(HOME_URL, "#laws")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(HOME_URL, wait_until="networkidle")
    expect(page.locator("#home-view")).to_be_visible()
    expect(page.locator("#catalog")).to_be_hidden()
    expect(page.locator("#latest-list .latest-item")).to_have_count(2)
    latest_dates=page.locator("#latest-list .latest-item").evaluate_all("(rs) => rs.map(r => r.dataset.published)")
    assert latest_dates == sorted(latest_dates, reverse=True)
    expect(page.locator(".home-links a")).to_have_count(6)
    expect(page.locator("#topics-title")).to_have_text("最新专题")
    page.evaluate("window.__moduleNavigationMarker = true")
    page.locator("#nav-laws").click()
    assert page.evaluate("window.__moduleNavigationMarker === true"), "Navigation reloaded the document"
    page.locator("#nav-search").click()
    expect(page.locator("#departments")).to_be_hidden()
    expect(page.locator("#catalog")).to_be_visible()
    page.locator("#nav-favorites").click()
    expect(page.locator("#favorites-panel")).to_be_visible()
    page.locator("#nav-laws").click()
    expect(page.locator("#catalog")).to_be_visible()
    expect(page.locator("#result-count")).to_contain_text("匹配", timeout=30000)
    expect(page.locator("#department-grid a")).to_have_count(9)
    expect(page.locator("#catalog-title")).to_have_text("高级检索")
    expect(page.locator("#topic")).to_have_count(0)
    expect(page.locator("#material")).to_have_count(0)
    expect(page.locator("#crosscutting-list")).to_have_count(0)
    rows = page.locator("#result-rows tr")
    expect(rows.first).to_be_visible()
    expect(page.locator("#sort")).to_have_value("newest")
    dates=rows.evaluate_all("(rs) => rs.map(r => r.dataset.published)")
    assert dates == sorted(dates, reverse=True), dates
    page.locator("#department").select_option("smartphone")
    page.locator("#sort").select_option("relevance")
    expect(rows.first).to_contain_text("32023R1670")
    expect(rows.nth(1)).to_contain_text("32023R1669")
    expect(rows.nth(2)).to_contain_text("32023R1542")
    page.locator("#clear-button").click()
    expect(page.locator("#sort")).to_have_value("newest")
    def reset():
        page.locator("#clear-button").click()
    def fill(key, value):
        page.locator("#more-filters").evaluate("(el) => el.open = true")
        page.locator("#"+key).fill(value)
    def titles():
        return page.locator("#result-rows .act-title").all_text_contents()
    for query, celex in [("人工智能法案","32024R1689"),("AI Act","32024R1689"),("Artificial Intelligence Act","32024R1689"),("GDPR","32016R0679"),("网络韧性法案","32024R2847"),("CRA","32024R2847"),("2024/1689","32024R1689")]:
        reset()
        fill("search", query)
        expect(rows.first).to_contain_text(celex)
    reset()
    fill("search", "ecodesign")
    expect(rows.first).to_be_visible()
    assert all("ecodesign" in x.lower() or "eco-design" in x.lower() for x in titles()) or len(titles()) > 0
    expect(page.locator("#result-rows .act-title mark")).to_have_count(0)
    reset()
    page.locator("#more-filters").evaluate("(el) => el.open = true")
    fill("celex-number", "32023R1669")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("32023R1669")
    expect(rows.first.locator(".title-zh")).not_to_contain_text("暂无中文参考译名")
    reset()
    fill("act-number", "2023/1669")
    expect(rows.first).to_contain_text("32023R1669")
    reset()
    page.locator("#more-filters").evaluate("(el) => el.open = true")
    page.locator("#search-scope").select_option("english")
    fill("search", "smartphone energy")
    expect(rows.first).to_be_visible()
    assert all("smartphone" in t.lower() and "energy" in t.lower() for t in titles())
    reset()
    page.locator("#more-filters").evaluate("(el) => el.open = true")
    page.locator("#search-scope").select_option("english")
    fill("any-terms", "battery charging")
    expect(rows.first).to_be_visible()
    assert all("battery" in t.lower() or "charging" in t.lower() for t in titles())
    fill("exclude-terms", "vehicle")
    assert all("vehicle" not in t.lower() for t in titles())
    reset()
    page.locator("#more-filters").evaluate("(el) => el.open = true")
    page.locator("#search-scope").select_option("english")
    fill("exact-phrase", "energy labelling")
    expect(rows.first).to_be_visible()
    assert all("energy labelling" in t.lower() for t in titles())
    reset()
    fill("search", "能效标签")
    expect(rows.first).to_be_visible()
    reset()
    core = {
        "smartphone": ["32023R1670", "32023R1669", "32023R1542"],
        "wearables": ["32014L0053", "32023R1542"],
        "tablet-pc": ["32023R1670", "32023R1669", "32023R1542"],
        "marketing-services": ["32005L0029", "32006L0114"],
        "iot": ["32014L0053", "32024R2847"],
        "smart-vehicle": ["32018R0858", "32019R2144"],
        "integrated-delivery": ["32019R1020", "32013R0608"],
        "hardware-engineering": ["32014L0053", "32014L0030"],
        "software-engineering": ["32024R2847", "32016R0679", "32024R1689"],
    }
    links = [(a.get_attribute("href"), a.get_attribute("data-department")) for a in page.locator("#department-grid a").all()]
    assert set(d for _, d in links) == set(core)
    for href, department in links:
        page.goto(href, wait_until="networkidle")
        expect(page.locator("#result-count")).to_contain_text("匹配")
        expect(page.locator("#department")).to_have_value(department)
        expect(page.locator("#department")).to_be_disabled()
        expect(page.locator("#sort")).to_have_value("relevance")
        for index, celex in enumerate(core[department]):
            expect(rows.nth(index)).to_contain_text(celex)
        if department == "smartphone":
            fill("search", "人工智能法案")
            expect(rows.first).to_contain_text("32024R1689")
            reset()
            expect(rows.first).to_contain_text("32023R1670")
    page.goto(URL, wait_until="networkidle")
    reset()
    page.set_viewport_size({"width":390,"height":844})
    fill("celex-number", "32023R1669")
    expect(rows).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile page overflows"
    assert not errors, errors
    browser.close()
print("Browser acceptance tests passed")
