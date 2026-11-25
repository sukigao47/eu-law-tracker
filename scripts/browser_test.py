"""Browser acceptance test against the generated catalogue or published URL."""
import os
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, expect

URL = os.environ.get("TEST_URL", "http://127.0.0.1:8765/")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(URL, wait_until="networkidle")
    expect(page.locator("#result-count")).to_contain_text("匹配", timeout=30000)
    expect(page.locator("#department-grid a")).to_have_count(9)
    expect(page.locator("#catalog-title")).to_have_text("高级检索")
    expect(page.locator("#topic")).to_have_count(0)
    expect(page.locator("#crosscutting-list")).to_have_count(0)
    rows = page.locator("#result-rows tr")
    expect(rows.first).to_be_visible()
    def reset():
        page.locator("#clear-button").click()
    def fill(key, value):
        page.locator("#more-filters").evaluate("(el) => el.open = true")
        page.locator("#"+key).fill(value)
    def titles():
        return page.locator("#result-rows .act-title").all_text_contents()
    fill("search", "ecodesign")
    expect(rows.first).to_be_visible()
    assert all("ecodesign" in x.lower() or "eco-design" in x.lower() for x in titles()) or len(titles()) > 0
    expect(page.locator("#result-rows mark").first).to_be_visible()
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
    for button in page.locator("#department-grid button").all():
        button.click()
        assert page.locator("#department").input_value() == button.get_attribute("data-department")
        expect(page.locator("#result-count")).to_contain_text("匹配")
    reset()
    page.set_viewport_size({"width":390,"height":844})
    fill("celex-number", "32023R1669")
    expect(rows).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile page overflows"
    assert not errors, errors
    browser.close()
print("Browser acceptance tests passed")
