# 欧盟法规库｜终端业务法务

本项目是面向终端消费电子及相关业务的欧盟法规检索目录。网站按九大业务部门和跨部门专题建立导航，支持法规编号、CELEX、中文标题、英文标题及关键词组合检索。

## 业务分类

九大部门：智能手机产品线、智能穿戴设备产品线、平板与PC产品线、营销服、IoT产品线、智选车产品线、集成交付（含服务及采购）、硬件工程、软件工程。

跨部门专题：产品合规与市场准入、网络安全/数据保护/AI、消费者保护与营销、环境与循环经济、供应链与尽调、知识产权与竞争法、售后维修/产品责任/召回。

一部法规可关联多个部门。部门关联是法规检索导航，不构成针对具体产品、主体或交易的法律适用结论。分类规则见 `config/terminal-lifecycle.json` 和 `config/business-taxonomy.json`。

## 中文标题和搜索

- `config/titles-zh.json` 保存经人工维护的 CELEX—中文标题映射。
- 未收录中文译名的文件会显示「暂未维护中文标题」，不会自动编造翻译。
- 搜索支持中文标题、英文标题、CELEX、Cellar work ID、文件类型、EuroVoc关键词、法规主题及部门名称；多个词按 AND 关系匹配。
- 日期筛选已移除，保留发布日期展示和排序。
- 法规原文链接始终指向 EUR-Lex。

## 当前数据源和覆盖边界

当前自动采集核心为欧盟出版局 CELLAR SPARQL 数据：
- CELLAR 中标记为现行有效的 CELEX 第3部门 Regulation、Directive、Decision 记录；
- 最近90天《欧盟官方公报》L系列发布的 Regulation、Directive、Decision；
- 英文标题、官方公报发布日期、进入效力日期、现行状态、EuroVoc主题/关键词等结构化元数据。

来源： [CELLAR知识图谱与元数据](https://op.europa.eu/en/web/cellar/cellar-data/metadata/knowledge-graph) · [EUR-Lex](https://eur-lex.europa.eu/) · [欧盟官方公报](https://eur-lex.europa.eu/oj/direct-access.html?locale=en)。

系统会在目录记录中区分 Regulation、Directive、Decision，并根据官方英文标题识别 Delegated Regulation/Directive/Decision 和 Implementing Regulation/Directive/Decision。授权/实施法案仍是相应条例、指令或决定的子类型，并非新的基本 CELEX 法律类型。

**目前不应将本目录理解为欧盟全部法律文件的穷尽抓取。** 软法（如 Recommendation、Opinion、Communication）、C系列文件、欧盟法院判例、成员国转化措施、委员会FAQ/指南及技术标准尚未形成完整的自动采集链路；技术标准也不属于法律文件，需与法规分库管理，并通过协调标准引用/实施决定关联。对这些资料应通过 EUR-Lex、CURIA、委员会及相关标准组织官方页面另行核验。现有采集范围及局限会在网站页面提示。

## 自动更新与部署

GitHub Actions 每天 UTC 11:24（北京时间19:24）运行一次，并在 `main` 分支相关文件更新时触发。工作流会先运行分类回归测试，再同步 Cellar 数据、生成静态目录并部署到 GitHub Pages。

1. 仓库 Settings → Pages，将发布来源设为 GitHub Actions。
2. 在 Actions 中运行「同步法规并发布网站」工作流。
3. 在部署任务或 Settings → Pages 查看实际发布网址。

手动运行时可勾选「重新读取每项法规的元数据」。同步失败时，已发布页面继续保留上次成功快照。GitHub 可能停用连续60天没有仓库活动的定时工作流，需在 Actions 页面重新启用。

## 本地预览和测试

需要 Python 3.9+：

```sh
python -m unittest discover -s tests -v
python scripts/sync.py
python -m http.server 8000 --bind 127.0.0.1 --directory site
```

打开 http://127.0.0.1:8000/。同步脚本会访问公开 CELLAR SPARQL 接口；若只想预览现有快照，可跳过 `scripts/sync.py`。

## 数据字段

每条已收录记录保留 CELEX、Cellar work ID、官方英文标题、人工维护中文标题（如有）、法规类型、授权/实施类型、官方 EUR-Lex 链接、发布日期、生效日期、现行状态、EuroVoc主题/关键词、业务部门及跨部门专题。
