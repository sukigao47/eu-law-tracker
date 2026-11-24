# 欧盟法规库

这个中文法规目录面向在欧盟市场投放和销售手机、平板、智能穿戴及其他智能终端的企业。可以按关键词、CELEX 编号、效力层级、业务主题、有效状态和公报发布日期搜索，结果链接到 EUR-Lex 英文原文。

## 数据范围

目录从 Cellar 标为现行有效的法规、指令和决定，以及最近 90 天在《欧盟官方公报》L 系列发布的这三类文件中，选出命中智能终端业务主题的条目。发布日期来自公报元数据，缺失时页面显示「未标注」。 [Cellar 查询文档](https://op.europa.eu/en/web/cellar/cellar-data/metadata/knowledge-graph) · [官方公报](https://eur-lex.europa.eu/oj/direct-access.html?locale=en)

访问网站后，点「查最新发布」即可重新载入已经发布的快照，并筛选近 7 天。页面显示最近同步时间和公报数据截止日。需要在当天的同步之前核对最新公报时，可以打开网站里的「到官方公报核对」。

## 维护业务主题

[主题规则](config/terminal-lifecycle.json)覆盖研发和知识产权、生态设计和能效、网络安全和数据、采购尽调、材料电池、生产与职业安全、CE 和产品安全、进出口及税费、销售电商、广告、售后维修、回收及终端配件。条目可以同时命中多个主题。工厂运营、医疗用途、出口管制等主题下的文件可供相应业务情形核对适用范围。

每次同步都会重新生成仅含命中条目的公开快照。同步工作缓存和网站使用不同路径，便于复用上次核对过的官方元数据。调整配置后，可以推送到 `main` 或手动运行工作流来重建目录。

| 配置项 | 匹配规则 |
| --- | --- |
| `acts` | 按 CELEX 编号纳入指定文件 |
| `follow` | 纳入指定文件及标题中明确引用其法规编号的文件 |
| `concepts` / `labels` | 匹配 EuroVoc 概念 ID 或指定的官方主题和描述词 |
| `phrases` | 在标题和官方主题字段中匹配明确的法规或业务短语 |
| `context` | 产品词和业务短语同时出现时纳入 |
| `product_title` | 纳入标题直接提及配置中任一终端或配件的条目 |

## 同步和部署

1. 将项目推送到 GitHub 仓库的默认分支。GitHub Free 支持在公开仓库使用 Pages。
2. 打开仓库的 **Settings → Pages**，将发布来源选为 **GitHub Actions**。
3. 在 **Actions → 同步法规并发布网站 → Run workflow** 手动跑一次。成功后在部署任务或 Pages 设置页查看公开网址。

定时任务设为每天北京时间 19:24，由 GitHub 排队运行。推送网站、同步脚本或工作流的修改到 `main` 也会触发更新。任务会更新最近发布和现行状态。需要重取历史条目的标题、日期或主题时，可在手动运行时勾选「重新读取每项法规的元数据」。同步失败时，已发布的网站继续提供上次成功的快照。

GitHub 会停用连续 60 天没有仓库活动的公开仓库的定时工作流。日常维护可提交并推送实际修改。GitHub 的文档没有说明单独点「Run workflow」会重置倒计时。停用后在工作流页面选择 **Enable workflow**，再运行一次更新。 [GitHub 定时规则](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) · [启用工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)

## 本地预览

使用 Python 3.9 或更新版本，在项目根目录运行以下命令。

```sh
python3 scripts/sync.py
python3 -m http.server 8000 --bind 127.0.0.1 --directory site
```

打开 [本地预览](http://127.0.0.1:8000/)。如果项目目录里已经有快照，直接启动第二条命令也能预览。

页面适合部署在 GitHub Pages 的项目子路径。同步脚本使用公开 Cellar 接口，GitHub Actions 的部署权限由仓库自动提供。
