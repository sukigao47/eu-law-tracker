
const PAGE_SIZE = 15;
const TYPE_LABELS = { R: "法规", L: "指令", D: "决定" };
const STATUS_LABELS = {
  active: "现行有效",
  pending: "尚未生效",
  inactive: "非现行",
  unknown: "未标注",
};

const SUBJECT_LABELS = new Map(Object.entries({
  agriculture: "农业",
  "common agricultural policy": "共同农业政策",
  "common commercial policy": "共同商业政策",
  "common foreign and security policy": "共同外交与安全政策",
  competition: "竞争",
  "consumer protection": "消费者保护",
  "customs union": "关税同盟",
  energy: "能源",
  environment: "环境",
  fisheries: "渔业",
  "free movement of goods": "货物自由流通",
  "free movement of persons": "人员自由流动",
  "internal market": "内部市场",
  "international agreements": "国际协定",
  "public health": "公共卫生",
  "social policy": "社会政策",
  taxation: "税收",
  transport: "交通运输",
}));

const dateParts = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Brussels",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const chinaTimeParts = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const BUSINESS_BOARDS = {
  consumer: {
    label: "消费者与产品合规",
    topics: ["devices", "conformity", "materials", "service", "circular"]
  },
  privacy: {
    label: "数据隐私与网络安全",
    topics: ["digital"]
  },
  commercial: {
    label: "商事合规与竞争",
    topics: ["retail", "advertising"]
  },
  trade: {
    label: "出口管制与贸易合规",
    topics: ["trade"]
  },
  ip: {
    label: "专利与知识产权",
    topics: ["design-ip"]
  },
  telecom: {
    label: "电信、频谱与连接",
    topics: ["conformity"]
  },
  sustainability: {
    label: "可持续与供应链",
    topics: ["ecodesign", "sourcing", "factory", "circular"]
  },
  all: {
    label: "综合与其他",
    topics: []
  },
};

const topicOrder = new Intl.Collator("zh-CN");
const numbers = new Intl.NumberFormat("zh-CN");

const ui = Object.fromEntries(
  Array.from(
    document.querySelectorAll("[id]"),
    (element) => [element.id, element]
  ),
);

const dateButtons = Array.from(
  document.querySelectorAll("[data-days]")
);

let snapshot = null;
let records = [];
let page = 1;
let refreshError = false;
let refreshing = false;
let rangeDays = 0;
let activeBoard = "";

function todayInBrussels() {
  const parts = Object.fromEntries(
    dateParts.formatToParts(new Date())
      .map(({ type, value }) => [type, value])
  );

  return [
    parts.year,
    parts.month,
    parts.day
  ].join("-");
}

function labelSubject(subject) {
  return SUBJECT_LABELS.get(subject.toLowerCase()) ?? subject;
}

function formatDateZh(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value || "未标注";
  }

  const [year, month, day] = value.split("-");

  return `${year}年${month}月${day}日`;
}

function formatBeijingDateTime(value) {
  const parts = Object.fromEntries(
    chinaTimeParts.formatToParts(new Date(value))
      .map(({ type, value: part }) => [type, part])
  );

  return `${parts.year}年${parts.month}月${parts.day}日 ${parts.hour}:${parts.minute}`;
}

function parseDateInput(value) {
  const text = value.trim();

  if (!text) return "";

  let match = text.match(
    /^(\d{4})年(\d{1,2})月(\d{1,2})日?$/
  );

  if (!match) {
    match = text.match(
      /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/
    );
  }

  if (!match) return null;

  const [, y, m, d] = match;

  const date = new Date(
    Date.UTC(Number(y), Number(m) - 1, Number(d))
  );

  if (
    date.getUTCFullYear() !== Number(y) ||
    date.getUTCMonth() !== Number(m) - 1 ||
    date.getUTCDate() !== Number(d)
  ) {
    return null;
  }

  return `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
}

function setDateField(id, isoDate) {
  ui[id].value = isoDate ? formatDateZh(isoDate) : "";

  const native = ui[`${id}-native`];

  if (native) {
    native.value = isoDate || "";
  }
}

function dateRangeValues() {
  const since = parseDateInput(ui.since.value);
  const until = parseDateInput(ui.until.value);

  return {
    since,
    until,
    invalid:
      since === null ||
      until === null ||
      (since && until && since > until)
  };
}

function updateOverview() {
  const total = records.length;
  const today = todayInBrussels();

  const active = records.filter(
    (record) => statusFor(record, today) === "active"
  ).length;

  const cutoff = new Date(`${today}T00:00:00Z`);

  cutoff.setUTCDate(cutoff.getUTCDate() - 89);

  const cutoffDate = cutoff.toISOString().slice(0, 10);

  const recent = records.filter(
    (record) =>
      record.published &&
      record.published >= cutoffDate &&
      record.published <= today
  ).length;

  const topicCount = snapshot?.profile?.topics?.length ?? 0;

  ui["stat-total"].textContent = numbers.format(total);
  ui["stat-active"].textContent = numbers.format(active);
  ui["stat-recent"].textContent = numbers.format(recent);
  ui["stat-topics"].textContent = numbers.format(topicCount);

  for (const [id, board] of Object.entries(BUSINESS_BOARDS)) {
    const count = id === "all"
      ? total
      : records.filter(
          (record) =>
            record.topicIds.some(
              (topic) => board.topics.includes(topic)
            )
        ).length;

    const target = document.querySelector(
      `[data-board-count="${id}"]`
    );

    if (target) {
      target.textContent = numbers.format(count);
    }
  }
}

function renderLatest() {
  const container = ui["latest-list"];
  if (!container) return;

  const latest = records
    .filter((record) => record.published)
    .sort(newestFirst)
    .slice(0, 5);

  if (latest.length === 0) {
    const empty = document.createElement("p");
    empty.className = "latest-placeholder";
    empty.textContent = "当前目录暂无可展示的近期发布日期记录。";
    container.replaceChildren(empty);
    return;
  }

  const items = latest.map((record) => {
    const item = document.createElement("article");
    item.className = "latest-item";

    const main = document.createElement("div");
    main.className = "latest-item-main";

    const link = document.createElement("a");
    link.href = "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A"
      + encodeURIComponent(record.id);
    link.target = "_blank";
    link.rel = "noopener";
    link.lang = "en";
    link.textContent = record.title || "在 EUR-Lex 查看法规";

    const meta = document.createElement("p");
    meta.className = "latest-meta";
    meta.textContent = "CELEX " + record.id;

    main.append(link, meta);

    const date = document.createElement("time");
    date.className = "latest-date";
    date.dateTime = record.published;
    date.textContent = formatDateZh(record.published);

    item.append(main, date);
    return item;
  });

  container.replaceChildren(...items);
}

function applyBoard(boardId, clearTopic = true) {
  activeBoard = boardId;

  if (clearTopic) {
    ui.topic.value = "";
  }

  const board = BUSINESS_BOARDS[boardId];

  ui["active-board"].hidden = !boardId;

  if (boardId) {
    ui["active-board-label"].textContent =
      `当前板块：${board.label}`;
  }

  document.querySelectorAll("[data-board-id]").forEach(
    (button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.boardId === boardId)
      );
    }
  );

  page = 1;
  render();
}

function statusFor(record, today) {
  if (record.inForce === true) return "active";

  if (record.entry && record.entry > today) {
    return "pending";
  }

  return record.inForce === false ? "inactive" : "unknown";
}

function loadTopics() {
  const chosen = ui.topic.value;
  let options;

  if (snapshot.profile) {
    options = snapshot.profile.topics.map(
      ({ id, label }) => new Option(label, id)
    );
  } else {
    const subjects = new Set(
      records.flatMap((record) => record.subjects)
    );

    options = Array.from(
      subjects,
      (subject) => new Option(labelSubject(subject), subject)
    );

    options.sort(
      (left, right) => topicOrder.compare(left.text, right.text)
    );

    if (
      records.some((record) => record.subjects.length === 0)
    ) {
      options.push(
        new Option("未标注主题", "__unlabelled")
      );
    }
  }

  ui.topic.replaceChildren(
    new Option("全部主题", ""),
    ...options
  );

  ui.topic.value = Array.from(ui.topic.options).some(
    (option) => option.value === chosen
  ) ? chosen : "";
}

function renderNotice() {
  let message = "";

  if (refreshError) {
    message = snapshot
      ? "暂时无法读取最新快照。下方仍显示上次载入的数据。"
      : "暂时无法读取法规数据。可重试查最新发布，或到欧盟官方公报核对。";
  } else if (
    snapshot &&
    Date.now() - Date.parse(snapshot.checkedAt) > 36 * 60 * 60 * 1000
  ) {
    message = "法规数据已超过 36 小时未同步。若需确认最新发布，请到官方公报核对。";
  }

  ui.notice.textContent = message;
  ui.notice.hidden = !message;
}

async async function loadSnapshot(manual = false) {
  if (refreshing) return;

  refreshing = true;

  ui["recent-button"].disabled = true;
  ui["recent-button"].textContent = manual
    ? "正在检查"
    : "查看近 7 天发布";

  try {
    const url = new URL(
      "./data/catalog.json",
      import.meta.url
    );

    const response = await fetch(url, {
      cache: manual ? "no-cache" : "default"
    });

    if (!response.ok) {
      throw new Error("Catalogue HTTP " + response.status);
    }

    const data = await response.json();

    if (
      data.version !== 1 ||
      !Array.isArray(data.documents) ||
      !Number.isFinite(Date.parse(data.checkedAt))
    ) {
      throw new Error("Invalid catalogue data");
    }

    if (!snapshot || data.checkedAt > snapshot.checkedAt) {
      snapshot = data;

      const businessLabels = new Map(
        (data.profile?.topics ?? []).map(
          ({ id, label }) => [id, label]
        )
      );

      records = data.documents.map((doc) => {
        const topicIds = data.profile
          ? doc.businessTopics
          : doc.subjects;

        const topicNames = data.profile
          ? topicIds.map((id) => businessLabels.get(id))
          : doc.subjects.map(labelSubject);

        return {
          ...doc,
          topicIds,
          topicNames,
          searchText: [
            doc.id,
            doc.title,
            ...topicNames,
            ...doc.subjects,
            ...doc.subjects.map(labelSubject),
            ...doc.keywords
          ]
            .join(" ")
            .normalize("NFKC")
            .toLowerCase(),
        };
      });

      loadTopics();
      updateOverview();
      renderLatest();

      ui["sync-time"].dateTime = data.checkedAt;

      ui["sync-time"].textContent =
        formatBeijingDateTime(data.checkedAt);

      ui["sync-note"].textContent =
        "北京时间 · 公报数据截至 " +
        formatDateZh(data.through);

      const scope = data.recentOnly
        ? `《欧盟官方公报》自 ${formatDateZh(data.recentSince)} 起发布的法规、指令和决定`
        : "智能终端相关欧盟法规 · 按业务主题、法规类型及效力状态检索";

      ui["catalog-scope"].textContent = data.profile
        ? `${data.profile.label} · ${scope}`
        : scope;
    }

    refreshError = false;

  } catch (error) {
    console.warn("Unable to load the catalogue:", error);

    refreshError = true;

    if (!snapshot) {
      ui["sync-time"].textContent = "暂不可用";
    }

  } finally {
    refreshing = false;

    ui["recent-button"].disabled = false;
    ui["recent-button"].textContent = "查看近 7 天发布";

    renderNotice();
    render();
  }
}

function tag(text, className) {
  const element = document.createElement("span");

  element.className = "tag " + className;
  element.textContent = text;

  return element;
}

function resultRow(record, today) {
  const row = document.createElement("tr");

  const type = record.id[5];
  const status = statusFor(record, today);

  row.insertCell().append(
    tag(TYPE_LABELS[type] ?? "其他", "type-" + type)
  );

  const link = document.createElement("a");

  link.className = "act-title";

  link.href =
    "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A" +
    encodeURIComponent(record.id);

  link.target = "_blank";
  link.rel = "noopener";
  link.lang = record.title ? "en" : "zh-CN";
  link.textContent = record.title || "在 EUR-Lex 查看法规";

  const celex = document.createElement("span");

  celex.className = "celex";
  celex.textContent = "CELEX " + record.id;

  row.insertCell().append(link, celex);

  const topics = row.insertCell();

  topics.className = "topics";

  const labels = record.topicNames;

  topics.textContent = labels.slice(0, 2).join(" · ") || "未标注";

  if (labels.length > 2) {
    topics.textContent += " +" + (labels.length - 2);
    topics.title = labels.join(" · ");
  }

  const date = row.insertCell();

  date.className = "pub-date";

  if (record.published) {
    const time = document.createElement("time");

    time.dateTime = record.published;
    time.textContent = formatDateZh(record.published);

    date.append(time);
  } else {
    date.textContent = "未标注";
  }

  row.insertCell().append(
    tag(STATUS_LABELS[status], "status-" + status)
  );

  return row;
}

function matches(record, today, terms, range) {
  const topicMatch = activeBoard
    ? (
        activeBoard === "all" ||
        record.topicIds.some(
          (topic) =>
            BUSINESS_BOARDS[activeBoard].topics.includes(topic)
        )
      )
    : (
        !ui.topic.value ||
        (
          ui.topic.value === "__unlabelled"
            ? record.topicIds.length === 0
            : record.topicIds.includes(ui.topic.value)
        )
      );

  return (
    (!ui.type.value || record.id[5] === ui.type.value) &&
    (!ui.status.value ||
      statusFor(record, today) === ui.status.value) &&
    topicMatch &&
    (!range.since ||
      (record.published && record.published >= range.since)) &&
    (!range.until ||
      (record.published && record.published <= range.until)) &&
    terms.every(
      (term) => record.searchText.includes(term)
    )
  );
}

function newestFirst(left, right) {
  if (left.published === right.published) {
    return right.id.localeCompare(left.id);
  }

  return (right.published ?? "").localeCompare(
    left.published ?? ""
  );
}

function render() {
  const range = dateRangeValues();
  const invalidRange = range.invalid;

  ui.until.setCustomValidity(
    invalidRange
      ? "请检查日期格式，并确保结束日等于或晚于起始日。"
      : ""
  );

  dateButtons.forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      Number(button.dataset.days) === rangeDays
    );
  });

  if (!snapshot || invalidRange) {
    ui["result-table"].hidden = true;
    ui.pagination.hidden = true;
    ui.empty.hidden = !invalidRange;

    ui["empty-title"].textContent = "请调整发布日期";

    ui["empty-detail"].textContent =
      "请输入有效日期（例如 2026年11月25日），并确保结束日等于或晚于起始日。";

    ui["result-count"].textContent = invalidRange
      ? "发布日期范围有误"
      : refreshError
        ? "法规数据暂不可用"
        : "正在载入法规数据";

    return;
  }

  const today = todayInBrussels();

  const terms = ui.search.value
    .trim()
    .normalize("NFKC")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);

  const filtered = records.filter(
    (record) => matches(record, today, terms, range)
  );

  if (ui.sort.value === "oldest") {
    filtered.sort((left, right) => {
      if (
        Boolean(left.published) !== Boolean(right.published)
      ) {
        return left.published ? -1 : 1;
      }

      return newestFirst(right, left);
    });
  }

  const lastPage = Math.max(
    1,
    Math.ceil(filtered.length / PAGE_SIZE)
  );

  page = Math.min(page, lastPage);

  const start = (page - 1) * PAGE_SIZE;

  const visible = filtered.slice(
    start,
    start + PAGE_SIZE
  );

  ui["result-rows"].replaceChildren(
    ...visible.map(
      (record) => resultRow(record, today)
    )
  );

  ui["result-table"].hidden = visible.length === 0;
  ui.empty.hidden = visible.length > 0;

  ui["empty-title"].textContent = "没有符合条件的法规";

  ui["empty-detail"].textContent = rangeDays
    ? "当前快照的所选时间内没有匹配记录。可调整日期或到官方公报核对。"
    : "试试其他关键词，或放宽效力层级、主题和日期条件。";

  ui.pagination.hidden = lastPage === 1;

  ui["result-count"].textContent =
    "匹配 " + numbers.format(filtered.length) +
    " 项 · 全库 " + numbers.format(records.length) + " 项";

  ui["page-count"].textContent =
    "第 " + page + " / " + numbers.format(lastPage) + " 页";

  ui.previous.disabled = page === 1;
  ui.next.disabled = page === lastPage;
}

function chooseRange(days) {
  const today = todayInBrussels();

  const start = new Date(today + "T00:00:00Z");

  start.setUTCDate(
    start.getUTCDate() - days + 1
  );

  setDateField(
    "since",
    start.toISOString().slice(0, 10)
  );

  setDateField("until", today);

  rangeDays = days;
  page = 1;

  render();
}

ui.filters.addEventListener("submit", (event) => {
  event.preventDefault();
});

ui.filters.addEventListener("input", (event) => {
  if (
    event.target === ui.since ||
    event.target === ui.until
  ) {
    rangeDays = 0;

    const native = ui[`${event.target.id}-native`];

    const parsed = parseDateInput(event.target.value);

    if (native && parsed) {
      native.value = parsed;
    }
  }

  page = 1;
  render();
});

ui.sort.addEventListener("change", () => {
  page = 1;
  render();
});

ui["clear-button"].addEventListener("click", () => {
  ui.filters.reset();

  setDateField("since", "");
  setDateField("until", "");

  rangeDays = 0;

  applyBoard("");

  page = 1;
  render();

  ui.search.focus();
});

for (const field of ["since", "until"]) {
  const native = ui[`${field}-native`];

  document.querySelector(
    `[data-open-date="${field}"]`
  ).addEventListener("click", () => {
    if (typeof native.showPicker === "function") {
      native.showPicker();
    } else {
      native.focus();
    }
  });

  native.addEventListener("change", () => {
    setDateField(field, native.value);

    rangeDays = 0;
    page = 1;

    render();
  });
}

document.querySelectorAll("[data-board-id]").forEach(
  (button) => {
    button.addEventListener("click", () => {
      applyBoard(
        button.dataset.boardId === activeBoard
          ? ""
          : button.dataset.boardId
      );

      ui.catalog.scrollIntoView({
        block: "start",
        behavior: "smooth"
      });
    });
  }
);

ui["clear-board"].addEventListener("click", () => {
  applyBoard("");
});

ui.topic.addEventListener("change", () => {
  if (ui.topic.value) {
    applyBoard("", false);
  }
});

dateButtons.forEach((button) => {
  button.addEventListener("click", () => {
    chooseRange(Number(button.dataset.days));
  });
});

ui["recent-button"].addEventListener("click", async () => {
  ui.filters.reset();
  ui.sort.value = "newest";

  chooseRange(7);

  ui.catalog.scrollIntoView({
    block: "start"
  });

  await loadSnapshot(true);
});

ui.previous.addEventListener("click", () => {
  page -= 1;
  render();

  ui["result-count"].scrollIntoView({
    block: "nearest"
  });
});

ui.next.addEventListener("click", () => {
  page += 1;
  render();

  ui["result-count"].scrollIntoView({
    block: "nearest"
  });
});

loadSnapshot();
