# 常见定制任务

按任务找对应小节。所有路径以 `template/` 为根。改之前若涉及模块接线，
先读 `design.md` 对应小节。

## 换主题色

只改 `colors.typ`：`primary`（主题红）与其浅底 `tint`。笔记头红标、节标题竖标、
旁注左侧竖线、提示框配色、插图取色全部从这里取，一处改完全文同步。
各模块文件顶部的 `box-colors` / `palette` / `note-colors` 只是别名，不用动。

## 每篇笔记的主题色

每篇笔记一种，默认按篇序从 `colors.typ` 的 `note-themes` 顺序取，
**第一篇总是主题红**，所以单篇导出的观感和全局主题色版没区别。
不需要为新建的笔记写任何东西——拿到的就是没用过的下一种。

某一篇想固定颜色，在它的 `note-header` 里显式写：

```typst
#note-header(
  title: "ANSYS 拓扑优化",
  …
  theme: note-themes.indigo,   // 键名见 colors.typ 的 note-themes-base
)
```

注意传值用 `note-themes.<键名>`，不要图直观写成 `note-themes-base.<键名>`——
后者绕过了黑白开关，`note-monochrome = true` 时这篇的颜色不会跟着变灰。

要注意的两件事：

- *往中间插一篇，后面各篇的颜色会整体后移一位*。在意哪篇就给哪篇写上
  `theme:`，写死之后不受影响。全册都写也可以，只是繁琐。
- *色板只有六种*，第七篇起开始第二轮（同色相隔六篇，不容易混）。
   想扩就往 `note-themes-base` 里加一行，索引和篇序一起自动往后走。

改色板时的硬条件是**颜色要够深**：3pt 的笔记头短标、`lighten(65%)` 的旁注竖线
都从主题色算出来，浅色经这两道工序会淡到看不见。色相上刻意避开提示框的语义色
（蓝=提示、橙=提醒、青=技巧），免得一篇青色主题的笔记里分不清哪个是框。

主题色只决定四处：笔记头短标、节标题竖标、摘要竖线、旁注竖线。
**插图的数据系列色不跟它走**（`figstyle.typ` 的 `series` 第一色固定用主题红），
因为那个文件与书籍样板同源；想让某张图跟主题色一致，在图里直接写
`color: note-themes.indigo` 之类的字面量。

## 调旁注栏宽度 / 去掉旁注栏

`note.typ` 顶部：

```typst
#let note-note-width = 3.4cm   // 旁注栏宽度
#let note-gutter = 0.6cm       // 正文与旁注栏之间的空隙
#let note-margin-outer = 1.0cm // 旁注栏外侧到纸边的距离
```

改这三个值即可，右侧页边距与版心宽度会自动跟着算——不用动 `set page`。

`note-margin-outer` 别设成 0：那样旁注栏右缘正好落在纸的切边上，旁注和通栏图
都会顶到纸边。它同时决定了「靠边排」的所有元素离纸张边缘的距离。

旁注栏调宽的代价是版心变窄（两者相加是定值）：3.4cm 时旁注每行约 9 个汉字，
再窄就不好读了；想更宽就得接受正文断行变密。

*完全不想要旁注栏*：把 `note-note-width` 调小（例如 `0.1cm`），正文里就
不要再写 `#pnote`。这样版心会变宽，页面接近单栏笔记。更彻底的做法是把
`note-margin-left` 与 `note-margin-right` 设成相等，得到对称边距的普通版式。

## 行级旁注 mnote：参数与适用场合

`mnote` 是 `pnote` 的可选升级，用 `@preview/marginalia` 实现，**锚在句子里的
位置**上，同页多条自动上下避让：

```typst
这句话是关键#mnote[补充一句我的理解]后面照常继续。
#mnote(dy: -6pt)[往上挪一点]    // 落点与通栏块冲突时手工微调
#mnote-warn[这条容易记错]        // 提醒（橙）
#mnote-tip[一个更快的手法]      // 技巧（青）
```

可以传的参数（其余原样转交 marginalia）：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `fill` | 主题灰 | 旁注文字颜色，`mnote-warn` / `mnote-tip` 预设了橙与青 |
| `dy` | `0pt` | 垂直偏移，正向下负向上 |
| `side` | `auto` | 只接受 `auto` / `"outer"` / `"right"`；模板左边距只有 2.0cm，传 `"left"` / `"inner"` 会在编译期被断言拦下 |
| `counter` | `none` | 不编号。要编号 + 交叉引用就写 `#mnote(counter: marginalia.notecounter)[…]<mn:x>`，然后 `@mn:x` 引用（印出的是符号锚点 ●○◆…） |

两条使用建议：

- **一条注解针对一整段时，仍然用 `pnote`**。`mnote` 每来一条就参与一轮
  state 循环，整篇笔记每条都用它的话，排版轮次会明显变多，极端文档上可能
  报 `document did not converge within five attempts`（见 `pitfalls.md`）。
- 长旁注（五行以上）靠近 `#wide` 通栏块时会压到块上——marginalia 只避让
  自己创建的 `wideblock`，与模板的 `wide` 互不知情。用 `dy` 挪开，或那条
  改用 `pnote`。

## 打印稿：隐藏旁注 + 黑白配色

两个 Boolean 开关，都为复习纸和打印机服务，改完重新编译即可，不用动笔记：

```typst
// note.typ：为 true 时 pnote 与 mnote 全部消失，正文照常流动
#let note-hide-notes = false

// colors.typ：为 true 时整套配色换成同亮度的灰阶
#let note-monochrome = false
```

`note-hide-notes` 打开后版式**不动**：`pnote` 退化成普通段落而不是留空，
`mnote` 连锚点一起消失，页面不会塌出空洞。反过来，屏幕上细读记得改回 `false`。

`note-monochrome` 保留等量的明暗层次（红标仍是深色、提示框仍是浅底），
因为它是按亮度逐色换算的，不是另挑的一套灰。见 `design.md` 的同名小节。

*这两个开关没有做成命令行可传参*。Typst 的 `--input key=value` 拿到的是
字符串，要当布尔值用得再套一层 `json.decode`，读起来比改一行 `let` 更绕；
要一条命令出两种 PDF，就在两次编译之间改这一行。

## 换开本

`note.typ` 里 `note-paper` 改成 `"a5"` 或 `"b5"`，右边距与版心自动跟着走
（纸张宽度表 `note-paper-widths` 里已含 a4 / a5 / b5）。表里没有的开本，
往 `note-paper-widths` 里补一行即可。`note-paper` 取了表里没有的值会在编译期
直接报错——早先是静默按 a4 兜底，纸张换了、边距还按旧宽度算，版面错位且
没有任何提示，所以这里选择让它喊出来。

a5 上旁注栏 3.4 cm 会显得过宽，建议同时把 `note-note-width` 调到 3.0 cm 左右。

## 改版面密度

| 想要的效果 | 改哪里 |
| --- | --- |
| 正文字号 | `note.typ` 的 `note-body-size`（10.5pt） |
| 旁注字号 | `note.typ` 的 `note-note-size`（8.5pt） |
| 行距 | `note-setup` 里的 `set par(leading: 0.85em)` |
| 首行缩进量 | `note.typ` 的 `note-par-indent`（2em） |
| 页边距 | `note.typ` 的 `note-margin-left` / `note-margin-top` / `note-margin-bottom` |

## 改字体

| 用途 | 位置 |
| --- | --- |
| 正文 / 西文 / 数学 / 代码 | `note.typ` 顶部的 `note-font-body` / `note-font-math` / `note-font-mono` |
| 标题、笔记头、旁注以内的标签、图内文字 | `note-font-head`、`figstyle.typ` 的 `fig-font` |
| 强调（楷体） | `note-font-kai` |

字体链原则：链尾放非当前系统的兜底（SimHei 是 Windows 字体，链尾补
Noto Sans SC；KaiTi 缺失时宁可退回正文宋体）。**不要放只装了单一粗字重
的字体族**（如仅 Heavy 的思源宋体）——找不到常规字重会退到粗字重，
正文整体变特粗。

## 扩充提示框类型

`boxes.typ` 里加一个 `callout.with(...)` 偏应用：

```typst
#let exercise-box = callout.with(
  title: [练习],
  icon: "pencil",        // 图标名见 https://heroicons.com/
  color: box-colors.green,
)
```

编号环境同理（`thm-env.with`，supplement 换「习题」「注记」等）。
新类型记得在 `notes/note-format.typ` 的提示框一节里补一行展示。

## 改状态标记

`note.typ` 的 `status-colors` 是「状态名 → 圆点颜色」的表，键名就是笔记头里
`status:` 要填的字符串。加状态往这里加一行即可，没登记的字符串会退回灰色。

## 加一篇笔记

1. 在 `notes/` 下新建文件，照抄 `notes/note-format.typ` 的开头（`#import` +
   `#note-header(…)`），正文从 `==` 起；
2. 只想单独导出它，把 `single.typ` 末尾那行 `#include` 指过去。

汇总册不用管：`collection.typ` 的 include 列表由 `collect` 自动维护
（AUTO-INCLUDE 段），`sync` 检测到未收录的笔记攒满 20 篇会自动编一卷。
只有删了 BEGIN/END 标记进入手工维护模式后，才需要自己往 `collection.typ`
里加 include——注意手工模式下 `collect` 只编译出 PDF、不记收录账。

总目录、页码、书眉都会自己跟上，没有需要手工维护的清单。

## 交叉引用印编号还是印标题

默认印**标题文字**：`@sec:process` → 「一般流程：三阶段九步骤」。
原因是笔记的节标题默认不编号，而 Typst 对「无编号标题」的引用会直接报错
（`cannot reference heading without numbering`），模板用一条 `show ref`
规则把它接管成了印标题。

想要编号式引用，在 `note-setup` 里加一行：

```typst
set heading(numbering: "1.1.1")
```

`@sec:process` 就变回「2.2」。这时那条 `show ref` 规则会自动让位
（有编号时 `it` 照常渲染成编号）。

两种写法各有场景：单篇导出时没有目录可查，「见 2.2 节」其实没法查，
印标题更有用；但如果正文句子里已经提到了那一节的名称，
「（一般流程：三阶段九步骤 节）」读起来就重复了，编号更利落。

## 宽的图 / 表：通栏

版心只有 14.0cm（书籍样板是 16cm），从别处搬来的示意图和表格常常放不下，
直接放会溢出到页边距里、左边被切掉一截。用 `#wide` 包一层：

```typst
#wide[
  #figure(table(…), caption: […]) <tab:x>
]
```

通栏宽度 = 正文栏 + 间隙 + 旁注栏 = 18.0cm，把旁注栏在需要时借给正文用。
块内是左对齐的，所以不满格的图不会被推到右边去。

**标签必须写在 `#wide[…]` 里面**（紧跟 figure），写在外面会挂到那个块上，
`@fig:x` 就指不到图了。

判断标准很简单：图的横向刻度跨度 × `length` 超过 13cm，或者表格用
`columns: (auto, auto, 1fr)` 而第三列折行超过三行，就该通栏。

## 开章节编号

模板默认不给节标题编号（笔记通常不需要，且一级标题是给笔记头的）。
编号的开关与影响见上面「交叉引用印编号还是印标题」一节。

注意编号图案的第一段会落在**隐形的一级标题**上，所以 `==` 节会显示成
`1.1`、`1.2`——每篇笔记内部从 `1.` 起；汇总结册时第二篇的节会显示成
`2.1`、`2.2`（这正是「单篇导出与汇总成册编号不同」的来源之一）。
用三段的图案 `"1.1.1"` 才能让 `===` 小节也带上编号，两段的图案
在更深一级上会退化成编号重复。

## 改汇总册首页

`collection.typ` 的 `collection-title(...)`：标题、副标题、作者、日期，
以及 `toc-depth`（默认 1，只列笔记标题；改成 2 会连节标题一起列）。

## 单篇也想要页眉 / 页码

页码是全自动的（多于一页就印）。书眉只在「笔记的续页」出现，这是设计决定；
若某篇单页笔记也想要页眉，在 `note-setup` 的 `set page(header: …)` 里
把那个 `heads.last().location().page() < pg` 条件去掉即可。

## 让链接显色

模板不改链接的默认外观（可点击，但颜色与正文一致）——这样汇总册目录里的
条目链接不会变成一片蓝。想要正文里的链接显色，自己加一条定向规则：

```typst
#show link.where(..): set text(fill: note-colors.blue)
```

注意这条会连同目录条目一起染色，加之前先看一眼汇总册的效果。
