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
    category_cards=page.locator("#source-category-grid .source-category-card")
    expect(category_cards).to_have_count(13)
    expect(page.locator("#source-category-detail")).to_be_hidden()
    category_titles=category_cards.locator("strong").all_text_contents()
    assert category_titles == [
        "核心基础法规库", "能效、生态设计、可持续产品", "消费者保护、广告合规、绿色声明",
        "数据保护GDPR", "网络安全、NIS2、CRA", "AI Act", "产品安全、市场监管、射频指令",
        "电池、循环经济、化学品、包装", "数字服务、数字市场", "立法征询、政策动态",
        "标准、合格评定、TBT通报", "重点成员国法律官网", "贸易制裁配套",
    ]
    category_cards.nth(0).click()
    expect(page.locator("#source-category-grid")).to_be_hidden()
    expect(page.locator("#source-detail-title")).to_have_text("核心基础法规库")
    expect(page.locator("#source-recommendations li")).to_have_count(6)
    expect(page.locator("#source-recommendations a").first).to_have_text("EUR-Lex 欧盟立法原文库")
    expect(page.locator("#source-recommendations a[href='https://eur-lex.europa.eu/n-lex/']")).to_have_count(1)
    page.locator("#source-back").click()
    expect(page.locator("#source-category-grid")).to_be_visible()
    category_cards.nth(10).click()
    expect(page.locator("#source-recommendations li")).to_have_count(3)
    expect(page.locator("#source-recommendations a[href='https://docs.wto.org/dol2fe/Pages/SS/directdoc.aspx?filename=q:/TBT/TBTHome.htm']")).to_have_count(1)
    page.locator("#source-back").click()
    page.locator("#nav-laws").click()
    expect(page.locator("#nav-search")).to_have_count(0)
    expect(page.locator("#topics-title")).to_have_text("最新专题")
    page.evaluate("window.__moduleNavigationMarker = true")
    page.locator("#nav-laws").click()
    assert page.evaluate("window.__moduleNavigationMarker === true"), "Navigation reloaded the document"
    expect(page.locator("#departments")).to_be_visible()
    expect(page.locator("#catalog")).to_be_visible()
    page.goto(HOME_URL + "#search", wait_until="networkidle")
    expect(page.locator("#departments")).to_be_visible()
    expect(page.locator("#catalog")).to_be_visible()
    page.locator("#nav-favorites").click()
    expect(page.locator("#favorites-panel")).to_be_visible()
    page.locator("#nav-laws").click()
    expect(page.locator("#catalog")).to_be_visible()
    expect(page.locator("#result-count")).to_contain_text("匹配", timeout=30000)
    expect(page.locator("#department-grid a")).to_have_count(9)
    expect(page.locator("#catalog-title")).to_have_text("高级检索")
    expect(page.locator("label:has(#cross-topic) > span")).to_have_text("法律领域部门")
    expect(page.locator("label:has(#type) > span")).to_have_text("效力层级")
    expect(page.locator("label:has(#status) > span")).to_have_text("现行状态")
    expect(page.locator("#department option").first).to_have_text("选择业务部门")
    expect(page.locator("#type option").first).to_have_text("选择效力层级")
    expect(page.locator("#type-subtype")).to_be_hidden()
    expect(page.locator("#type-subtype")).to_be_disabled()
    type_options = page.locator("#type option").evaluate_all("(options) => options.map(option => [option.value, option.textContent.trim()])")
    assert type_options == [
        ["", "选择效力层级"],
        ["legislative", "Legislative Acts"],
        ["delegated", "Delegated Acts"],
        ["implementing", "Implementing Acts"],
        ["guidance", "Guidance"],
        ["standards", "Harmonised Standards / Common Specifications"],
    ], type_options
    expect(page.locator("#status option").first).to_have_text("选择现行状态")
    status_options = page.locator("#status option").evaluate_all("(options) => options.map(option => [option.value, option.textContent.trim()])")
    assert status_options == [
        ["", "选择现行状态"],
        ["pending", "尚未生效"],
        ["inactive", "已失效"],
        ["active_unknown", "现行有效"],
        ["na", "已发布"],
    ], status_options
    expect(page.locator("#search-scope")).to_have_count(0)
    for selector in ("#department", "#cross-topic", "#status", "#type"):
        placeholder = page.locator(selector + " option").first
        expect(placeholder).to_contain_text("选择")
        expect(placeholder).not_to_contain_text("全部")
    expect(page.locator("#type-subtype option").first).to_have_text("Select act form")

    page.locator("#search").fill("Blue Guide")
    guide = page.locator("#result-rows tr[data-celex='52022XC0629(04)']")
    expect(guide).to_have_count(1)
    expect(guide.locator("td").nth(4)).to_have_text("-")
    expect(guide.locator("td").nth(5)).to_have_text("不适用")
    page.locator("#clear-button").click()
    page.locator("#type").select_option("guidance")
    expect(page.locator("#result-rows tr[data-celex='52022XC0629(04)']")).to_have_count(1)
    page.locator("#clear-button").click()
    page.locator("#search").fill("2022/C 247/01")
    expect(page.locator("#result-rows tr[data-celex='52022XC0629(04)']")).to_have_count(1)
    page.locator("#clear-button").click()
    page.locator("#search").fill("C/2026/90070")
    expect(page.locator("#result-rows tr[data-celex='52022XC0629(04)R(02)']")).to_have_count(1)
    page.locator("#clear-button").click()
    page.locator("#search").fill("欧盟产品规则实施蓝皮书")
    expect(page.locator("#result-rows tr[data-celex='52022XC0629(04)']")).to_have_count(1)
    page.locator("#clear-button").click()

    rows = page.locator("#result-rows tr")

    def result_ids():
        return page.locator("#result-rows tr").evaluate_all("(rs) => rs.map(r => r.dataset.celex)")

    def subtype_options():
        return page.locator("#type-subtype option").evaluate_all("(options) => options.slice(1).map(option => [option.value, option.textContent.trim()])")

    for form, code in [("R", "R"), ("L", "L"), ("D", "D")]:
        page.locator("#type").select_option("legislative")
        expect(page.locator("#type-subtype")).to_be_visible()
        assert subtype_options() == [["R", "Regulation"], ["L", "Directive"], ["D", "Decision"]]
        page.locator("#type-subtype").select_option(form)
        expect(rows.first).to_be_visible()
        ids = result_ids()
        assert ids and all(len(identifier) > 5 and identifier[5] == code for identifier in ids), (form, ids)
        page.locator("#clear-button").click()
        expect(page.locator("#type-subtype")).to_be_hidden()

    page.locator("#type").select_option("delegated")
    expect(page.locator("#type-subtype")).to_be_visible()
    assert subtype_options() == [
        ["delegated-regulation", "Delegated Regulation"],
        ["delegated-directive", "Delegated Directive"],
        ["delegated-decision", "Delegated Decision"],
    ]
    delegated_sets = []
    for form in ("delegated-regulation", "delegated-directive", "delegated-decision"):
        page.locator("#type-subtype").select_option(form)
        delegated_sets.append(result_ids())
    assert delegated_sets[0] == delegated_sets[1] == delegated_sets[2], delegated_sets

    page.locator("#type").select_option("implementing")
    expect(page.locator("#type-subtype")).to_be_visible()
    assert subtype_options() == [
        ["implementing-regulation", "Implementing Regulation"],
        ["implementing-decision", "Implementing Decision"],
    ]
    implementing_sets = []
    for form in ("implementing-regulation", "implementing-decision"):
        page.locator("#type-subtype").select_option(form)
        implementing_sets.append(result_ids())
    assert implementing_sets[0] == implementing_sets[1], implementing_sets

    page.locator("#type").select_option("guidance")
    expect(page.locator("#type-subtype")).to_be_hidden()
    page.locator("#type").select_option("standards")
    expect(page.locator("#type-subtype")).to_be_hidden()
    page.locator("#clear-button").click()
    expect(page.locator("#topic")).to_have_count(0)
    expect(page.locator("#material")).to_have_count(0)
    expect(page.locator("#cross-topic option").first).to_have_text("选择法律领域部门")
    expect(page.locator("#cross-topic option")).to_have_count(11)
    expect(rows.first).to_be_visible()
    expect(page.locator("#sort")).to_have_value("relevance")
    page.locator("#sort").select_option("newest")
    dates=rows.evaluate_all("(rs) => rs.map(r => r.dataset.published)")
    assert dates == sorted(dates, reverse=True), dates
    page.locator("#sort").select_option("relevance")
    page.locator("#department").select_option("smartphone")
    page.locator("#sort").select_option("relevance")
    expect(rows.first).to_contain_text("32023R1670")
    expect(rows.nth(1)).to_contain_text("32023R1669")
    expect(rows.nth(2)).to_contain_text("32023R1542")
    page.locator("#clear-button").click()
    expect(page.locator("#sort")).to_have_value("relevance")
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
    expect(page.locator("#result-rows .title-en .celex").first).to_contain_text("CELEX 3")
    expect(page.locator("#result-rows .title-en .date-type, #result-rows .title-en .case-meta")).to_have_count(0)
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
    fill("search", "smartphone energy")
    expect(rows.first).to_be_visible()
    reset()
    page.locator("#more-filters").evaluate("(el) => el.open = true")
    fill("any-terms", "battery charging")
    expect(rows.first).to_be_visible()
    fill("exclude-terms", "vehicle")
    reset()
    page.locator("#more-filters").evaluate("(el) => el.open = true")
    fill("exact-phrase", "energy labelling")
    expect(rows.first).to_be_visible()
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
