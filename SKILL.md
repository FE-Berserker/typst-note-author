---
name: typst-note-author
description: 用 Typst 排中文学习笔记：笔记头（日期/标签/状态/来源）、右侧旁注栏、提示框与编号环境、三线表、图表公式，单篇导出与汇总成册两个出口共用一份内容；关键词与笔记结构可一键存入 SQLite，并生成 vis-network 交互式知识图谱（关键词共现网络）与 markmap 思维导图。当用户要做笔记、记学习笔记、整理笔记、把 Markdown 笔记排成 PDF，或提到 Typst 笔记、笔记模板、旁注、marginalia、笔记成册，或想看知识图谱、关键词图谱、思维导图、笔记知识结构时使用——即使用户只说「帮我把这些笔记排一下」「看看我的知识图谱」也应触发。
---

# Typst 中文笔记（笔记模板）

一套为「给自己看、一直在长」的中文笔记调校的 Typst 模板：笔记头、右侧旁注栏、
提示框与编号环境、三线表、图表公式、交叉引用均已配置就绪。每篇笔记有一种自己的
主题色。同一篇笔记文件既可以单独导出，也可以汇总成册——汇总册的总目录自动生成，
增删笔记不用手工维护目录。

配套的 `scripts/notes_db.py` 把笔记的关键词与结构存入 SQLite（`sync` 子命令），
再用现成的开源渲染器生成交互视图：**知识图谱**（`graph`，vis-network 力导向图：
关键词为节点、共现为边，可拖动/缩放/点击高亮/搜索）为主打，树状思维导图
（`mindmap`，markmap）为补充。

与书籍样板（`typst-book-author`）的关系：配色、提示框、图形样式、中文字体规则
从那边原样继承，骨架则换掉了——笔记不装订、不分篇、不做切口色标，
右侧的宽边不是留给订口的，是留给旁注的。两者不是同一套东西的两个尺寸。

## 工作流程

### 1. 搭脚手架

把本技能的 `template/` 整个目录复制到用户项目里（不要改动技能目录本身）。
结构很简单，只有三个文件需要认识：

- `note.typ` — 核心：版式参数、字体、行内样式、笔记头、旁注。**改版式只改这里**；
- `single.typ` — 单篇出口；
- `collection.typ` — 汇总出口。

**笔记存到哪里（第一次要问，之后自动记住）**：第一次为用户建笔记项目时，
先问清楚要存到哪个目录，然后登记一次：

```bash
python <技能目录>/scripts/notes_db.py root <用户选择的路径>
```

之后所有子命令**不带 `--root` 就默认用这个位置**（存于
`~/.typst-note-author/state.json`；用户设了 `TYPST_NOTES_HOME` 环境变量
则环境变量优先）。`notes_db.py root`（不带参数）随时可查当前位置；
没登记过时它会以退出码 3 提示 NOT_SET——那就再问一次用户。

### 2. 写笔记

每篇笔记是 `notes/` 下的一个文件，固定是「笔记头 + 正文」两段：

```typst
#import "../note.typ": *

#note-header(
  title: "ANSYS 拓扑优化",
  date: "2026-09-20",
  tags: ("仿真", "ANSYS"),
  status: "待复习",           // 草稿 / 待复习 / 待验证 / 持续更新 / 已定稿
  source: "https://…",        // 可选
  summary: "一两句说清这篇讲什么、为什么记它。",  // 可选
  theme: note-themes.indigo,   // 可选：不写就按篇序自动取色板里的一种
)

== 背景与目标                 // 正文从二级标题起，一级标题留给笔记头
```

**每篇笔记有一种主题色**，默认按篇序从 `colors.typ` 的 `note-themes` 色板里
顺序取（第一篇总是主题红，单篇导出的观感和以前一样），所以新建一篇拿到的是
新颜色，不用写任何东西。它决定四处：笔记头短标、节标题竖标、摘要竖线、旁注竖线。
想固定某篇的颜色就把 `theme:` 显式写出来。代价是**往中间插一篇，后面各篇的
颜色会整体后移一位**——想躲开这个就给你在意的那几篇都写上 `theme:`。

需要旁注的段落交给 `#pnote`：

```typst
#pnote(note: [旁注写在这里])[
  正文段落…………
]
#pnote-warn(note: […])[…]     // 提醒（橙）
#pnote-tip(note: […])[…]      // 技巧（青）
```

针对某一句话的即时反应用 `#mnote`，直接写在句子中间——旁注跟着当前位置走，
同页多条自动上下避让：

```typst
这句话是关键#mnote[补充一句我的理解]后面照常继续。
#mnote-warn[这条容易记错]        // 提醒（橙）
#mnote-tip[一个更快的手法]      // 技巧（青）
```

一条注解针对一整段时仍然用 `#pnote`：它不依赖外部包，行为也更可预期。
完整分工见 `references/design.md`「旁注」一节。

宽的示意图、表格、代码用 `#wide` 包一层，让它横跨正文栏与旁注栏——
版心只有 14.0cm，从别处搬来的图常常放不下：

```typst
#wide[
  #figure(sketch(…), caption: […]) <fig:x>
]
```

标签要写在 `#wide[…]` **里面**、紧跟 figure——写在外面会挂到那个块上，
`@fig:x` 就指不到图了。

### 3. 编译

```bash
typst compile single.typ 笔记.pdf          # 单篇（改 single.typ 里 include 的那一行）
typst watch single.typ 笔记.pdf            # 单篇：存盘即重编译，调版式时挂着看
typst compile collection.typ 我的笔记.pdf   # 汇总成册
```

拿去打印 / 复习时改两个开关再编译（`note.typ` 的 `note-hide-notes = true`
隐藏全部旁注，`colors.typ` 的 `note-monochrome = true` 换成灰阶配色），
屏幕细读记得改回来。细节见 `references/customization.md`「打印稿」一节。

要求 Typst 0.13+（用到的最新语法是 0.13 引入的 `first-line-indent` 配置；
实测 0.15.1）。首次编译需联网拉取 `@preview` 依赖
（showybox、heroic、cetz、fletcher、lilaq、tiptoe、marginalia）。
字体依赖：Noto Serif SC（正文）、SimHei + Arial（标题）、KaiTi/STKaiti（强调）、
New Computer Modern（西文与数学）、DejaVu Sans Mono（代码）——非 Windows 系统
需要思源黑体/思源宋体兜底（字体链已配好）。

### 4. 加笔记 / 编册（每 20 篇自动出合集）

在 `collection.typ` 末尾按顺序 `#include "notes/….typ"` 即可，
总目录、页码、书眉自动跟上。笔记文件建议带日期前缀
（`20260920-ANSYS-拓扑优化.typ`）：目录顺序由 include 的先后决定、与文件名
无关，前缀能让文件管理器里的排序和册内顺序对上。

**新建一篇笔记后跑一次计数**（写完文件、include 进 collection.typ 之后）：

```bash
python <技能目录>/scripts/notes_db.py bump
```

- 计数器存在 `~/.typst-note-author/state.json`，每次 bump +1；
- 满 **20 篇**时自动创建合集：调 `typst compile collection.typ` 生成
  `合集-日期.pdf`（在登记的笔记位置），计数归零。编译失败会把原因带出来，
  处理后手动跑 `collect` 重试；
- 不想等 20 篇、立即出合集：直接跑 `collect` 子命令；
- 计数只认 bump 的次数（即「自上次合集以来新建了几篇」），与笔记总数
  无关——忘了 bump 不会多出合集，只会晚出。

### 5. 关键词库与知识图谱

用户想看知识图谱、关键词之间的关系、笔记知识结构时，用技能目录里的
`scripts/notes_db.py`（纯标准库，Python 3.8+）对**用户笔记项目**执行：

```bash
# 1) 入库：扫描 notes/*.typ 的 note-header（标题/日期/标签/状态/来源/摘要）
#    与节标题（== / ===），全量重建 <项目>/notes.db
python <技能目录>/scripts/notes_db.py --root <用户项目> sync

# 2) 图谱：从 notes.db 生成 graph.html 并在浏览器打开
python <技能目录>/scripts/notes_db.py --root <用户项目> graph --open
```

- `graph.html` 是**交互式知识图谱**（vis-network 力导向图，CDN 加载需联网）：
  关键词为节点，**同一篇笔记出现过的关键词互相关联**（共现边，边越粗同现
  越多），节点大小 = 关联笔记数；拖动节点重排、滚轮缩放、点击节点高亮它的
  关联、搜索框定位关键词；「显示笔记节点」开关把每篇笔记也放进图里
  （虚线连向它的标签）。
- SQLite 是四张表：`notes` / `sections` / `keywords` / `note_keywords`，
  想自己写查询（比如「哪些笔记还是待复习」）直接用 sqlite3 读 `notes.db`。
- 层级视角的补充：`mindmap` 子命令生成树状思维导图（markmap 渲染，
  「关键词图谱」与「笔记库」两个视图，附 mindmap.md 大纲备份）。
- sync 是全量重建：改了笔记、增删标签之后重新跑一次 sync 再 graph；
  生成物（notes.db / graph.html / mindmap.html / mindmap.md）落在用户项目里，
  模板自带的 .gitignore 已覆盖它们，不会误提交。

## 模板文件一览

| 文件 | 职责 |
| --- | --- |
| `note.typ` | 核心：版式参数、字体、行内样式、笔记头 `note-header`、旁注 `pnote` / `mnote`、通栏 `wide` |
| `colors.typ` | 全部配色唯一来源：`note-colors-base` 是全局色，`note-themes` 是每篇笔记的主题色板；末尾两个开关（打印灰阶） |
| `boxes.typ` | 提示框 / 编号环境 / 加框公式，Heroicons 图标 |
| `figstyle.typ` | CeTZ 示意图、Fletcher 流程图、Lilaq 数据图的统一样式 |
| `single.typ` | 单篇出口：一篇笔记一个 PDF |
| `collection.typ` | 汇总出口：首页标题 + 自动总目录，之后每篇各起一页 |
| `notes/` | 笔记正文；随附的两篇既是示例也是用法文档 |
| `.gitignore` | 编译产物与 notes_db 生成物，随模板一起复制 |

技能目录里还有两个不随模板复制的脚本：

| 文件 | 职责 |
| --- | --- |
| `scripts/notes_db.py` | 笔记位置登记（`root`，跨会话记住）、关键词/结构入库 SQLite（`sync`）、知识图谱（`graph`）、思维导图（`mindmap`）、合集计数与自动编译（`bump` / `collect`） |
| `scripts/check_sync.py` | 校验本模板与书籍样板（typst-book-author）的色值、图形样式同步；改 `colors.typ` / `figstyle.typ` 后跑 |

## 四条必须记住的约定

1. **正文从 `==` 起**。一级标题是笔记头的（版面上隐掉，只在汇总册目录里出现），
   正文里再写一级标题会和笔记头抢位置、把目录搅乱。
2. **两种旁注，按锚点选**。`#pnote` 的旁注顶边对齐所在段落顶边（锚在段落上，
   一条注解概括一整段最自然）；`#mnote` 写在句子中间，跟着当前位置走、多条
   自动避让（锚在位置上）。早期只有 `pnote`——`place` 在段落里不按行定位，
   这是 Typst 的限制；`mnote` 后来用 marginalia 的 state 机制补上了这一条，
   但它每来一条就多一轮排版，别整篇都用它。
3. **一篇笔记只有一个 `#note-header`**。它负责新建一页、埋目录用的隐形标题、
   把定理编号归零，跳过它直接写正文会得到一篇没有标题、编号接着上一篇数的笔记。
4. **主题色按篇序自动排，插一篇会顺移**。每篇一种，默认从色板顺序取；往中间
   插一篇，后面各篇的颜色会后移一位。在意某篇的颜色就在它的 `note-header`
   里显式写 `theme: note-themes.xxx`，写死之后不受影响。

## 从别处搬内容进来

把已有的书稿 / Markdown 笔记迁到这套模板时，要过一遍这四件事：

1. 一级标题（`= …`）改成 `#note-header(title: …)`，正文的各级标题相应降一级
   或保持（模板里 `==` 是节、`===` 是小节）；
2. 版心从 16cm 缩到 14.0cm，**原来放得下的宽图、宽表会溢出到页边距里**
   （左边被切掉一截）——用 `#wide[… ]` 包一层；
3. 图表的编号会变：原来按章编号（`图 1.1`），现在是全文连续（`图 1`）；
4. `@sec:…` 这类交叉引用照旧能用，但默认印出的是**标题文字**而不是编号
   （笔记的节标题默认不编号），见下节。

## 深入阅读（按需）

- 改样式模块、动版面结构之前：读 `references/design.md`（模块接线与设计意图）；
- 常见定制（换主题色、每篇的主题色怎么排、调旁注栏宽、行级旁注参数、打印稿开关、
  换开本、扩提示框、开章节编号）：读 `references/customization.md`；
- 排版异常（旁注位置不对、缩进丢了、表格线不对、页码不出现）：先查
  `references/pitfalls.md`，那里是踩过的坑与修法。

## 注意

- 不要用 `#show heading` 给一级标题加装饰——一级标题是隐形的，改了没意义；
  要改笔记头的版式，去 `note.typ` 的 `note-header` 里改；
- 不要往字体链里放只装了单一粗字重的字体族，会导致正文整体变特粗；
- 不要用字符串替换做本地化（如 `#show "Figure": [图]`），会误伤代码块与引文；
  模板已设 `lang: "zh"`，图表的「图 / 表」由 Typst 自己本地化。
