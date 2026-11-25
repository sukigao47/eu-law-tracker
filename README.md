# 欧盟法规库｜终端业务法务

本项目是面向终端消费电子及相关业务的欧盟法规检索目录。网站按九大业务部门和跨部门专题建立导航，支持法规编号、CELEX、中文名称、官方名称及关键词组合检索。

## 业务分类

九大部门：智能手机产品线、智能穿戴设备产品线、平板与PC产品线、营销服、IoT产品线、智选车产品线、集成交付（含服务及采购）、硬件工程、软件工程。

跨部门专题：产品合规与市场准入、网络安全/数据保护/AI、消费者保护与营销、环境与循环经济、供应链与尽调、知识产权与竞争法、售后维修/产品责任/召回。

一部法规可关联多个部门。部门关联是法规检索导航，不构成针对具体产品、主体或交易的法律适用结论。分类规则见 `config/terminal-lifecycle.json` 和 `config/business-taxonomy.json`。

## 中文标题和搜索

- `config/titles-zh.json` 保存经人工维护的 CELEX—中文标题映射。
- 未收录中文译名的文件会显示「暂未维护中文标题」，不会自动编造翻译。
- 搜索支持中文名称、官方名称、CELEX、Cellar work ID、文件类型、EuroVoc关键词、法规主题及部门名称；多个词按 AND 关系匹配。
- 日期筛选已移除，保留发布日期展示和排序。
- 法规原文链接始终指向 EUR-Lex。

## 其他官方资料入口与后续数据源

`config/source-registry.json` 登记软法、官方公报C系列、欧盟法院判例、欧盟委员会指南/FAQ及技术标准的来源和覆盖状态。软法、C系列及欧盟法院判例已增加 CELLAR 自动采集管线：软法按 CELEX 3A/3H/3G/3C、5DC/5JC/5SC 及机构意见/报告类 5AA/5TA/5SA/5AB/5HB/5XB/5AE/5IE/5AC/5AR/5IR/5XR 描述符、滚动五年窗口检索；C系列按 CELLAR OJ-C collection、滚动180天窗口检索（包括该公报系列中具有 CELEX 标识的文件，不限于 CELEX 的 C/年份/编号子类）。软法及C系列记录经现有业务主题规则筛选后，独立写入 `site/data/related-materials.json`；欧盟法院判例按 CELLAR 的 `document_cjeu`、`case-law`、`summary_case-law` 和 `court-report` 类型识别，滚动十年窗口筛选，独立写入 `site/data/case-law.json`。判决、命令、总法律顾问意见、法院意见、判例摘要和法院报告分别标识；在 CELLAR 有明确关系数据时，同时保存该判例解释的欧盟法规 CELEX 和引用文书 CELEX，便于从判例反查法规。不并入有约束力法律文件目录。网站统一检索，但以不同资料类别标识。

**覆盖边界：** 这不是软法或C系列的全历史全量库；软法当前只覆盖上述 CELEX 描述符，C系列只覆盖最近180天且能在 CELLAR OJ-C collection 中识别并具有 CELEX 标识的记录，且仅发布匹配当前终端业务主题的记录。判例、委员会指南/FAQ和技术标准仍为官方入口参考，尚未接入自动采集。技术标准单独建模，不作为条例/指令/决定处理；应记录标准编号、版本、协调状态及其在官方公报中的引用信息。

## 当前数据源和覆盖边界

当前自动采集使用欧盟出版局 CELLAR SPARQL 数据，分别维护有约束力法律文件、软法/C系列相关资料和欧盟法院判例三个独立目录：
- CELLAR 中标记为现行有效的 CELEX 第3部门 Regulation、Directive、Decision 记录；
- 最近90天《欧盟官方公报》L系列发布的 Regulation、Directive、Decision；
- 软法候选：CELEX 描述符 3A、3H、3G、3C，以及 5DC、5JC、5SC 和机构意见/报告类 5AA、5TA、5SA、5AB、5HB、5XB、5AE、5IE、5AC、5AR、5IR、5XR，滚动五年；
- 官方公报 C 系列：CELLAR OJ-C collection 最近180天记录；
- 欧盟法院判例：CELLAR CJEU 文书类别最近十年记录，含 ECLI、案件编号、案件名称、法院、文书类型及主题（字段以来源可得性为准）；
- 英文标题、官方公报发布日期、进入效力日期、现行状态、EuroVoc主题/关键词等结构化元数据。

来源： [CELLAR知识图谱与元数据](https://op.europa.eu/en/web/cellar/cellar-data/metadata/knowledge-graph) · [EUR-Lex](https://eur-lex.europa.eu/) · [欧盟官方公报](https://eur-lex.europa.eu/oj/direct-access.html?locale=en)。

系统会在目录记录中区分 Regulation、Directive、Decision，并根据官方英文名称识别 Delegated Regulation/Directive/Decision 和 Implementing Regulation/Directive/Decision。授权/实施法案仍是相应条例、指令或决定的子类型，并非新的基本 CELEX 法律类型。

**目前不应将本目录理解为欧盟全部法律文件及判例的穷尽抓取。** 软法、C系列及欧盟法院判例已建立有限窗口自动采集，但不覆盖全部历史或所有相关文件；委员会FAQ/指南、技术标准及成员国转化措施尚未形成自动采集链路。技术标准不属于法律文件，需与法规分库管理，并通过协调标准引用/实施决定关联。现有采集范围及局限会在网站页面提示。

## 自动更新与部署

GitHub Actions 每天 UTC 11:24（北京时间19:24）运行一次，并在 `main` 分支相关文件更新时触发。工作流会先运行分类回归测试，再同步 Cellar 数据、生成静态目录并部署到 GitHub Pages。

1. 仓库 Settings → Pages，将发布来源设为 GitHub Actions。
2. 在 Actions 中运行「同步法规并发布网站」工作流。
3. 在部署任务或 Settings → Pages 查看实际发布网址。

手动运行时可勾选「重新读取每项法规的元数据」。同步失败时，已发布页面继续保留上次成功快照。GitHub 可能停用连续60天没有仓库活动的定时工作流，需在 Actions 页面重新启用。

## 本地预览和测试

需要 Python 3.10+：

```sh
python -m unittest discover -s tests -v
python scripts/sync.py
python scripts/sync_related.py
python scripts/sync_case_law.py
python -m http.server 8000 --bind 127.0.0.1 --directory site
```

打开 http://127.0.0.1:8000/。同步脚本会访问公开 CELLAR SPARQL 接口；若只想预览现有快照，可跳过 `scripts/sync.py`。

## 数据字段

法律文件记录保留 CELEX、Cellar work ID、官方英文名称、人工维护中文名称（如有）、法规类型、授权/实施类型、官方 EUR-Lex 链接、发布日期、生效日期、现行状态、EuroVoc主题/关键词、业务部门及跨部门专题。软法及C系列记录单独保留 CELEX、CELLAR work ID、官方名称、资料类别、非立法/效力性质提示、发布日期、OJ系列及官方链接；缺失元数据明确标记，不据此推断法律效力。
