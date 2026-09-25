# 版式架构与设计意图

改样式模块或版面结构之前先读这份文档。这里讲清楚模板各模块如何接线、
为什么这样设计；具体的「改法」见 customization.md，出问题查 pitfalls.md。

## 总体结构

```
note.typ                     核心：版式参数 + 字体 + 行内样式 + 笔记头 + 旁注
├── colors.typ               全部配色唯一来源
└── boxes.typ                提示框 / 编号环境
figstyle.typ                 CeTZ / Fletcher / Lilaq 统一图形样式
single.typ                   单篇出口
collection.typ               汇总出口
notes/                       笔记正文（一篇一个文件）
```

与书籍样板（`typst-book-author`）的关系，用一句话说：**继承了它的排版资产，
换掉了它的骨架**。

| 书籍样板的东西 | 笔记模板的处理 | 原因 |
| --- | --- | --- |
| `colors.typ` | 原样继承 | 配色与「书」无关 |
| `boxes.typ` 的框体 | 继承，去掉 Bookly 依赖 | 提示框是笔记的骨干 |
| `figstyle.typ` | 原样继承 | 图形样式与「书」无关 |
| `main.typ` 的字体 / 行内样式 / 表格 / 题注规则 | 搬进 `note.typ` | 纯中文排版资产 |
| Bookly 骨架 | 换成自写的轻骨架 | 见下 |

`figstyle.typ` 与 typst-book-author 的同名文件**内容相同**（文件头有 `SYNC`
标记，改的时候会看到）。`colors.typ` 则是**色值相同、文件不同**：`note-colors-base`
那份字典与书籍样板逐行一致，改色值要同步改两个技能，否则两套模板的配色会慢慢
漂移；末尾的灰阶开关是笔记独有的，不用往那边搬。
| 封面 / 版权页 / 封底 / 前置罗马页码 | 砍掉 | 单篇笔记不需要 |
| 篇章页、切口色标、装订边距、奇偶书眉 | 砍掉 | 都建立在「双面印刷 + 装订」上 |
| 目录 | 只保留汇总出口的总目录 | 单篇不需要目录 |

### 为什么不再依赖 Bookly

书籍样板的三类接管（theme 替换、页面背景装饰、定向 show/set 规则）全都围着
Bookly 转，其中最难受的一条约束是：**不能用 `#show heading` 给标题加装饰**，
因为 Bookly 的标题整块由主题的渲染规则生成，外面再加一条就会把它整个顶掉。
书籍样板绕开了这件事（装饰一律画在 `set page(background:)` 层），
但笔记模板不需要为了一份书籍骨架而接受这个约束。

去掉 Bookly 的代价只有三处：框体用的 `showybox` 要直接引入（原先是 Bookly
转手的），`box-title` 这个三行小工具要就地重写，以及「接管内置提示框」那条
路径整体删掉。收益是编译更快、依赖更少、标题与页面样式完全可控。

## 版面几何

```
┌──────────────────────────────────────────────┐
│                                              │
│  ┌──────────────────────┐  ┌────────┐        │
│  │                      │←0.6→│ 旁注栏  │←1.0cm→│
│  │      版心 14.0cm      │  │ 3.4cm  │  纸边   │
│  │                      │  │        │        │
│  └──────────────────────┘  └────────┘        │
│  ↑ 2.0cm                                     │
└──────────────────────────────────────────────┘
                                        a4 = 21cm
```

左侧 2.0 cm 是翻阅余量；右侧 = 旁注栏 3.4 cm + 间隙 0.6 cm + **纸边 1.0 cm**。
右侧边距不是直接给的，而是由这三段倒推出来的：

```typst
#let note-margin-right = note-note-width + note-gutter + note-margin-outer
#let note-column-width = note-paper-width - note-margin-left - note-margin-right
```

这样调旁注栏宽度时，版心与右边距会自动跟着变，不会出现「旁注栏改了、
正文还按旧宽度断行」的错位。换开本同理，只改 `note-paper`。

**纸边那 1.0 cm 不能省。** 早先的版本没有它，右边距正好等于「旁注栏 + 间隙」，
于是旁注栏的右缘落在 `2.0 + 版心 + 0.6 + 3.4 = 21.0cm`——正好是纸的切边。
旁注和通栏图全都顶到纸边，宽的图还会被裁掉一截。凡是「靠边排」的版式都要
留这一道，它决定的是内容离纸张边缘的距离。

## 笔记头与「隐形标题」

`note-header` 除了画版面，还在同一处埋了一枚**隐形的一级标题**：

```typst
{
  show heading: none
  heading(level: 1, outlined: true)[#title]
}
```

标题体被 `show heading: none` 隐掉，在版面上不占位置，但元素仍在文档树里——
于是 `outline` 和 `query` 都取得到它。一举两得：

- 汇总册的 `#outline(depth: 1)` 列出的就是这枚标题，所以目录里是笔记标题；
- 续页的书眉靠 `query` 找「本页之前最后出现的一级标题」，也是在找它。

书籍样板判断「篇行」用的是同一招（隐形标题 + 状态）。这也是**正文必须从
二级标题起**的原因：一级标题的位置已经被笔记头占用了。

## 旁注：为什么是 grid 而不是 place

这是这套模板里唯一一处「因为做不到，所以换个做法」的地方，值得写清楚。

一开始的写法是直觉式的：在句子里插一枚 `#mnote[…]`，用 `place` 把它推到
右边那一栏，指望它跟着当前行走。**实测这件事用 `place` 做不到**：

| 试过的写法 | 结果 |
| --- | --- |
| `place(left + horizon, …)` 直接写在段落里 | 落在整页版心的垂直中心，同页几条旁注全叠在一处 |
| `place(left + top, …)` | 落在版心顶部，与所在行无关 |
| 内容从块级的 `block` 换成行内的 `box` | 同上，没有区别 |
| 外面包一层 `context`（想顺便 `measure` 出行高） | 定位基准从「行」进一步降级成「所在块的垂直中心」 |

结论：Typst 的 `place` 写在段落里时，定位基准是**外层容器**，不是当前行。
只靠 `place`，「跟着某一行走」的旁注在这个版本里做不出来。

于是 `pnote` 改成用 `grid` 把正文与旁注并排，旁注顶边对齐段落顶边：

```typst
grid(
  columns: (note-column-width, note-note-width),
  column-gutter: note-gutter,
  align: (left + top, left + top),
  note-par(body),        // 正文格
  note-style(note),      // 旁注格
)
```

这个 grid 比版心宽出「间隙 + 旁注栏宽」，向右溢出到页边距里——那正是旁注栏的
所在。所以带旁注的段落与不带旁注的段落，正文断行宽度完全一致，版面不会
一页宽一页窄。

代价有两条，都是真实存在的，改版式时要知道：

1. **旁注锚在段落上，不锚在句子上**。要对准某个句子，把段落拆短；
   或者换用下面的 `mnote`。
2. **一行的高度取正文与旁注的较大者**。旁注比正文长时，正文那侧会留出一段
   空白。把旁注写短（三五行为宜）就不明显。

### 行级旁注：marginalia 补上了「锚在位置上」

后来发现 `@preview/marginalia` 用另一条路绕开了上面那张表：它不靠 `place`，
而是用 **state** 记录每条旁注已经占了哪一段垂直空间，排版时按 `clearance`
互相推开。这恰好是 `place` 给不了的——「已经占了」是全局信息，只有 state
能在一个 layout pass 里传递。

于是模板把它作为 `pnote` 的**可选升级**接进来，两套并存：

| | `pnote` | `mnote` |
| --- | --- | --- |
| 写法 | `#pnote(note: […])[段落]` | 句子里插 `#mnote[…]` |
| 锚点 | 段落顶边 | 当前这个位置 |
| 多条避让 | 不需要（一条配一段） | 自动上下推开 |
| 依赖 | 无（纯 Typst） | `@preview/marginalia:0.3.1` |

保留 `pnote` 而不是替换掉，理由有三条：它不依赖外部包；一条注解概括一整段时
它反而更稳（不参与 state 循环，排版轮次少）；两个入口的零回归基线就是它。

接线只做在 `note.typ` 里，三个注意点：

```typst
#import "@preview/marginalia:0.3.1" as marginalia

// 必须放在 set page(...) 之前：marginalia.setup 自己会调 set page，
// 且默认值是 a4 + 四边 2.5cm，晚一步就会被我们的版式盖掉
show: marginalia.setup.with(
  inner: (far: note-margin-left, width: 0cm, sep: 0cm),
  outer: (far: note-margin-outer, width: note-note-width, sep: note-gutter),
  top: note-margin-top,
  bottom: note-margin-bottom,
)
```

`outer` 的三个数必须凑成右边距 5.0cm（1.0 纸边 + 3.4 旁注栏 + 0.6 气口），
`top` / `bottom` 必须显式传（模板的 2.4cm 和它的默认 2.5cm 不一致）。
另外它会装一条 `show ref:` 规则，模板里已有的 ref 规则要能与之共存——
目前互不干扰，但以后再加 ref 装饰要记得这件事。

### 顺带一个坑：网格单元格里的首行缩进

Typst 不给网格单元格内的第一个段落加首行缩进，在单元格里写
`set par(first-line-indent: …)` 也不生效（两种写法都实测过）。
只有用 `par` 函数显式包一层才行，这就是 `note-par` 存在的原因：

```typst
#let note-par(body) = par(first-line-indent: (amount: note-par-indent, all: true))[#body]
```

注意 `body` 只能用尾随内容块的形式传：`par` 的 `body` 是位置参数，
写成 `par(body: …)` 会被拒，写成 `par(…, body)` 又会落到 `leading` 上。

## 两个打印向的开关

两个布尔开关都只做一件事：**同一个源文件，两种用途**——屏幕细读 / 拿去
打印复习。不是两套模板，不复制笔记文件。

- `note-hide-notes`（`note.typ`）：为 `true` 时 `pnote` 与 `mnote` 全部消失。
  `pnote` 不是留个空盒子，而是整段退化成普通段落，正文断行宽度不变；
  `mnote` 连锚点一起消失（`return none`），正文照常流动。所以隐藏旁注后
  页面不会塌掉，也不会多出空洞。
- `note-monochrome`（`colors.typ`）：把整套配色换成**同亮度的灰阶**。
  用 `luma(color.luma(c))` 逐色换算而不是手挑一套灰色，层级关系才保得住——
  红标仍是深色、提示框仍是浅底，不会糊成一片。彩打的彩色底复印出来会发灰
  发脏，灰阶版没有这个问题。

两个模块 import 的都是 `colors.typ` 末尾的 `note-colors`，所以改开关那一行
`note.typ` / `boxes.typ` / `figstyle.typ` 一起跟上，不存在漏网的模块。

`note-grayscale` 写成**带花括号的函数体**而不是 lambda 链，是被坑过的：
Typst 的 lambda 体到换行就结束，`d => d.pairs()` 后面接 `.map(…)` 的几行
会被静默丢掉，函数退化成返回「键值对数组」，报错点跑到很远的地方
（`cannot access fields on type array`，在 `boxes.typ` 里才炸）。同理，
传参时**展开字典要放在最后**：`f(a: 1, ..(a: 2))` 得到的是 `a = 2`。

## 每篇笔记一种主题色

汇合成册之后，「我现在翻到哪了」不能只靠标题——书眉里已经有一个标题了。
所以每篇笔记有一种主题色，颜色先认出来，标题是第二眼的事。

它决定四处，别的地方一概不跟：**笔记头短标、节标题竖标、摘要竖线、旁注竖线**。
提示框、数据系列、状态点、页码这些是语义色，和主题色无关，一篇青色主题的
笔记里提醒框仍然是橙色——这是有意的，颜色一旦身兼多职就不叫语义了。

机制上是两个 Typst 原语配合：

```typst
#let note-theme-index = counter("note-theme-index")   // 第几篇
#let note-theme-state = state("note-theme", …)        // 当前这一篇的颜色

// note-header 里：
context {
  note-theme-state.update(note-themes.values().at(calc.rem(i, note-themes.values().len())))
}
note-theme-index.step()
```

`state` 负责「跨篇传递」：主题色要在文档一半时换，而所有用它的地方都在 show
规则和函数里，那些代码排版时才求值，那时候读到的必须是当前这一篇的颜色——
编译期常量做不到这件事。`counter` 负责「第几篇」，`step` 写在普通代码里，
每轮排版只应用一次，和页码一样稳。

**为什么不用「记下已挑走哪些色」的 state。** 那个方案要在 `context` 里一边读
一边写：`used.get()` 挑色、`used.update(…)` 记账。Typst 会把 context 里的
update 重复应用，于是每轮排版都有新颜色冒出来，九篇笔记的测试文档报
`state("note-theme-used") did not converge`，最后一页的颜色和第一轮算的
已经完全无关。换成 counter 后写回 state 的值只由篇序决定，重复应用结果相同，
就收敛了。代价是往中间插一篇、后面各篇颜色后移一位——这是顺序取色的固有
性质，所以才有 `theme:` 参数用来钉死某一篇。

顺带一个反直觉的点：`context { … }` 会把表达式的值**显示**出来，不是返回它。
所以 `#let theme() = context state.get()` 拿到的是内容而不是颜色，
接着写 `4pt + theme()` 会报 `cannot add length and content`。取色必须直接写
`state.get()`，并且人待在 `context` 里。

## 书眉与页码

- **书眉只出现在笔记的续页上**。笔记标题已经在笔记头里了，首页再印一遍是
  重复；续页上它才是「我在读哪一篇」的唯一线索。判断用物理页号比较：
  取「本页及之前」最后出现的一级标题，若它不在本页，说明本页是续页。
  不能用 `query(…before(here()))`——页面页眉的 `here()` 解析在页面内容之前，
  会漏掉本页开头的那一篇。这一招是从书籍样板的切口色标那里学来的。
- **页码贴右**，不做奇偶区分（不装订，没有内外侧之分）。
- **只有一页的笔记不印页码**：单页文档上的「1」是纯噪音。总页数要用
  `counter(page).final()` 才拿得到，所以整段包在 `context` 里。

## 三线表

中文技术文档通行的三线表：顶线、表头下条线、底线，其余不画。
默认的 Typst 表格是一张满格的网，与这套模板「安静」的调子相反。

实现分两半：

- `set table(stroke: (x, y) => …)` 画顶线（`y == 0`，即表头行）与表头下条线；
- 底线由 `show table` 规则往表格末尾**追加一条 `table.hline(position: top)`**
  ——因为 `stroke` 函数只会收到整数坐标，「最后一行」没有对应的标记
  （`"first"` / `"last"` 实测收不到）。hline 是表格内部元素，随表宽收缩，
  窄表的底线不会比表格长出一截。

底线必须追加在表格**内部**而不是外面：早先用 `block(stroke: (bottom: …))`
把表格包起来补底线，结果 block 破坏了跨页时的表头重复（续页直接从数据行
继续，见 pitfalls「跨页表格续页没有表头」）。另外 `show` 规则对重建的同类型
元素会再次触发，规则里有守卫——末尾已挂着 hline 的表原样放行，否则无限
递归（maximum show rule depth exceeded）。

跨页断口处没有封口线是 Typst 三线表的普遍现状（续表惯例只要求重印表头）。

## 两个出口如何共用一份内容

`notes/` 下的每一篇都是「笔记头 + 正文」，自己不设置页面，也不知道会被谁引用。
_页面设置由入口负责_：`single.typ` 与 `collection.typ` 都在开头写
`#show: note-setup`，然后 `include` 笔记文件。

于是同一份内容有两种装配方式：

- `single.typ` include 一篇 → 一篇一个 PDF，没有封面没有目录；
- `collection.typ` include 全部 → 首页是标题加总目录，之后每篇各起一页。

`note-header` 里的 `pagebreak(weak: true)` 是这件事的关键：单篇导出时文档
刚开始，weak 换页不产生空白页；汇总成册时它保证每篇笔记都从新的一页开始。

## 中文创排决策

| 位置 | 决策 | 原因 |
| --- | --- | --- |
| 正文 | 思源宋体 + NCM 西文，10.5pt | 中文书籍惯例；西文衬线与宋体协调 |
| 标题 | SimHei + Arial（兜底 Noto Sans SC） | Typst 标题自带 bold，西文走 NCM 会落到粗衬线上，与黑体不搭 |
| 强调 | 楷体（KaiTi/STKaiti，兜底思源宋） | 汉字无斜体字形，套斜体只得正体；楷体是中文强调传统 |
| 加粗 | 思源宋粗体字重，兜底 SimHei | 「换黑体」是换字体不是加粗，删字重后会失效 |
| 首行缩进 | 2em 全段 | 中文惯例 |
| 代码/公式 | 显式补思源宋回退 | 这两处字体纯西文，否则 Typst 在系统里乱挑（实测落到隶书） |
| 代码块 | syntect 高亮（`code-theme.tmTheme`）+ 块级浅灰底板 | 高亮色值与调色板同源；tmTheme 的 background Typst 不渲染，底板由 `show raw.where(block: true)` 画 |
| 题注 | 「图 1　标题」全角空格分隔 | Typst 默认西文连接号 |
| 表格 | 列默认左对齐、格内禁两端对齐、三线表 | 对齐规矩混用曾是实际翻过车的点 |
| 语言 | `lang: "zh"` | 让 Typst 自己负责断行与「图 / 表」本地化，不必手工改写 supplement |

## 提示框体系（boxes.typ）

统一框体：所有框共用一种极浅的中性底（`#f7f7f8`），颜色只出现在标题牌与一道
细边上——类型靠 Heroicons 图标与标题文字区分，版面安静。三处共用
`box-frame()`（callout / thm-env / proof），改一处即全改。

- `callout`：通用框，任意 icon/color；`keypoint-box` 等是它的偏应用；
- `thm-env`：编号环境，定义 / 定理 / 引理 / 推论 / 命题 / 例共用一套编号，
  可交叉引用。**编号在每篇笔记内从 1 重新开始**——书籍样板是全书连续编号
  （书只有一个计数轴），笔记每篇自成一体，接着上一篇往下数反而不好引用。
  `note-header` 会调用 `reset-thm-counter()`；
- 框默认 `breakable: false`（短框整体不跨页），内容确实超过一页时显式传
  `breakable: true`。
