// ============================================================
// 笔记模板核心（note.typ）
// ------------------------------------------------------------
// 提供四样东西，单篇出口与汇总出口共用：
//   #show: note-setup      页面、字体、行内样式（放在文件最前面）
//   #note-header(…)        笔记头：标题、日期、标签、状态、来源、摘要
//   #pnote(note: […])[…]   段级旁注：一条注解配一个段落
//   #mnote[…]              行级旁注：注解跟着句子里的某个位置走（marginalia）
//
// 每篇笔记有一种主题色（色板在 colors.typ 的 note-themes）：note-header 不指定
// theme 时自动挑还没用过的第一种。它决定笔记头短标、节标题竖标、摘要竖线、
// 旁注竖线四处，其余颜色（提示框、数据系列、状态点）与主题色无关，保持语义固定。
//
// 设计取向（与书籍样板的差别）：
//   · 笔记是屏幕阅读与单面打印为主，页面默认左右不对称但*不装订*——
//     右侧宽边是留给旁注的，不是留给订口的；
//   · 每篇笔记自成一体：新建一页、定理环境从 1 重新编号，不做全书连续；
//   · 不做封面、篇章页、切口色标。笔记的价值在内容密度，不在装帧。
//
// 改版式只改下面「版式参数」一段；改笔记头与旁注的具体画法，
// 改 note-header / note-style / pnote 三个函数。
// ============================================================

#import "colors.typ": note-colors, note-themes
#import "boxes.typ": *
// 行级旁注 #mnote 的能力来源：用 state 记录每条旁注的落点来互相避让，
// 这正是 Typst 的 place 做不到的（见下面 mnote 一段的说明）。
#import "@preview/marginalia:0.3.1" as marginalia

// 模板版本：notes_db.py doctor 用它判断项目里的这份拷贝是否落后于技能模板。
// 旧拷贝可能缺已修复的规则（如「表题在表格上方」），开工前先跑 doctor 体检。
#let template-version = "2026-09-25"

// ---- 版式参数 ----
#let note-paper = "a4"
#let note-margin-left = 2.0cm
#let note-margin-top = 2.4cm
#let note-margin-bottom = 2.4cm
#let note-note-width = 3.4cm // 旁注栏宽度
#let note-gutter = 0.6cm // 正文与旁注栏之间的空隙
// 旁注栏外侧还要留一道纸边（note-margin-outer）。
// 不留的话，右边距正好等于「旁注栏 + 间隙」，旁注栏右缘会落在纸的切边上——
// 旁注和通栏图全都顶到纸边，看着像溢出了版面。
#let note-margin-outer = 1.0cm
#let note-body-size = 10.5pt
#let note-note-size = 8.5pt // 旁注字号：比正文小两号
#let note-par-indent = 2em // 正文首行缩进：中文惯例两个汉字宽
// 打印 / 复习稿：改成 true 时隐藏全部旁注（pnote 与 mnote 都隐），
// 正文自动占满整栏，不受影响。屏幕阅读改回 false。
#let note-hide-notes = false

// 纸张宽度表：右侧边距由「旁注栏宽 + 间隙 + 纸边」倒推，版心宽度随之而定。
// 换开本时只改 note-paper，右边距自动跟着走。表里没有的开本往表里补一行
// （Typst 的 paper 参数只认命名开本，传字典会直接报错，没有别的写法）。
// 忘了补不会静默出错：note-paper 不在表里时编译期直接 assert——早先是静默
// 按 a4 兜底，纸张换了、边距还按旧宽度算，版面错位且没有任何提示。
#let note-paper-widths = (a4: 21cm, a5: 14.8cm, b5: 17.6cm)
#let note-paper-width = {
  let w = note-paper-widths.at(note-paper, default: none)
  assert(
    w != none,
    message: "note-paper 是「" + note-paper + "」，note-paper-widths 里没有这个开本——往表里补一行",
  )
  w
}
#let note-margin-right = note-note-width + note-gutter + note-margin-outer
#let note-column-width = note-paper-width - note-margin-left - note-margin-right

// ---- 字体链 ----
// 与书籍样板同一套：正文思源宋体、标题黑体、强调楷体。
// 链尾放非 Windows 的兜底（Noto Serif SC / Noto Sans SC）。
// 注意不要放只装了单一粗字重的字体族，否则正文整体变特粗。
#let note-font-body = ("New Computer Modern", "Noto Serif SC", "SimSun")
#let note-font-head = ("Arial", "SimHei", "Noto Sans SC")
#let note-font-kai = ("New Computer Modern", "KaiTi", "STKaiti", "Noto Serif SC")
#let note-font-math = ("New Computer Modern Math", "Noto Serif SC")
#let note-font-mono = ("DejaVu Sans Mono", "Noto Serif SC")

// ---- 颜色与字号别名（色值见 colors.typ）----

// ---- 当前主题色（每篇笔记一种）----
// 为什么用 state 而不是普通 let：主题色要在文档进行到一半时换（每篇笔记
// 开头换一次），而下面所有用到它的地方——节标题竖标、笔记头短标、旁注竖线——
// 都在 show 规则和函数里，那些代码在排版时才求值，那时候读到的必须是
// 「当前这一篇的颜色」。let 是编译期常量，读不到；只有 state 能跨篇传递。
//
// 颜色怎么定：按篇序从 colors.typ 的 note-themes 里顺序取，取完一轮从头再来
// （第一篇总是主题红，所以单篇导出的观感不变）。用 counter 记篇序，不用
// 「记下已经挑走哪些色」的 state——那个方案要在 context 里一边读一边写，
// Typst 会把 update 重复应用，每轮排版都有新颜色冒出来，最后报
// "state("note-theme-used") did not converge"。counter 的 step 写在普通代码里，
// 每轮只应用一次，和页码一样稳；写回 state 的值只由篇序决定，
// 重复应用结果也相同。
// 代价：往中间插一篇笔记，后面各篇的颜色会后移一位。某篇想固定颜色，
// 给它显式传 theme: note-themes.ochre。
//
// 注意取色必须直接写 state.get() 且自身在 context 里：
// context { … } 会把表达式的值**显示**出来，所以
//   #let theme() = context …get()
// 拿到的是内容不是颜色，4pt + 主题色 会报 cannot add length and content。
#let note-theme-index = counter("note-theme-index")
#let note-theme-state = state("note-theme", note-colors.primary)

// ---- 笔记状态：小圆点的颜色 ----
// 状态是笔记特有的东西——书籍一次成稿，笔记一直在长。
#let status-colors = (
  "草稿": note-colors.gray,
  "待复习": note-colors.orange,
  "待验证": note-colors.orange,
  "持续更新": note-colors.blue,
  "已定稿": note-colors.green,
)

// ============================================================
// 页面与行内样式：在文件最前面写 #show: note-setup
// ============================================================

#let note-setup(body) = {
  // ---- 行级旁注的版面登记 ----
  // marginalia 自己也算一份页面几何（它据此判断旁注往哪放、会不会撞上别的
  // 旁注），所以要把本模板的边距参数翻译成它的语言：
  //   右侧 = note-margin-outer(1.0) + note-note-width(3.4) + note-gutter(0.6)
  // 三项加起来正好等于 note-margin-right，与下面 set page 的右边距是同一个数。
  // 左侧 2.0cm 不设旁注栏（width: 0cm）：那点宽度放不下注解，注解一律走右侧。
  //
  // 两处顺序不能反：
  //  1. 必须放在 set page 之前——marginalia.setup 自己会 set page，晚一步
  //     它的页边距（默认 a4 2.5cm）就会盖掉本模板的不对称边距；
  //  2. 必须放在 note-setup 的 show ref 之前——它的 ref 规则处理「引用旁注」
  //     （@mn:x），模板的 ref 规则处理「引用标题」，两条各管一种，
  //     且模板的规则对不是标题的引用一律放行，所以谁先谁后都能工作；
  //     marginalia 的对非旁注引用也一律放行。目前这样放两者都验证过。
  show: marginalia.setup.with(
    inner: (far: note-margin-left, width: 0cm, sep: 0cm),
    outer: (
      far: note-margin-outer,
      width: note-note-width,
      sep: note-gutter,
    ),
    top: note-margin-top,
    bottom: note-margin-bottom,
  )

  set page(
    paper: note-paper,
    margin: (
      left: note-margin-left,
      right: note-margin-right, // = 旁注栏宽 + 间隙 + 纸边，由上面三个参数倒推
      top: note-margin-top,
      bottom: note-margin-bottom,
    ),
    // 书眉只在「笔记的续页」上出现：笔记标题已经在笔记头里了，
    // 首页再印一遍是重复；续页上则是「我在读哪一篇」的唯一线索。
    // 判断方法与书籍样板的切口色标同一招——用物理页号比较，
    // 不能只查 here() 之前的一级标题（那样会漏掉本页开头的那一篇）。
    header: context {
      let pg = here().page()
      let heads = query(selector(heading.where(level: 1))).filter(h => (
        h.location().page() <= pg
      ))
      if heads.len() > 0 and heads.last().location().page() < pg {
        set text(font: note-font-head, size: 8.5pt, fill: note-colors.muted)
        set par(first-line-indent: 0em, justify: false)
        heads.last().body
      }
    },
    // 页码贴右（不装订，没有奇偶之分）。只有一页的笔记不印页码：
    // 单页文档上的「1 / 1」是纯噪音。总页数要用 final() 才拿得到，
    // 所以整段包在 context 里。
    footer: context {
      if counter(page).final().first() > 1 {
        set align(right)
        set text(font: note-font-head, size: 9pt, fill: note-colors.muted)
        counter(page).display()
      }
    },
  )

  // lang: "zh" 让 Typst 自己负责中文的断行与「图 / 表」本地化，
  // 不必像书籍样板那样手工改写 supplement。
  set text(font: note-font-body, size: note-body-size, lang: "zh", fill: note-colors.ink)

  // 中文排版惯例：正文首行缩进两个汉字宽度、行距略紧
  set par(
    first-line-indent: (amount: note-par-indent, all: true),
    justify: true,
    leading: 0.85em,
  )

  // ---- 标题 ----
  // 笔记标题（一级）由 note-header 自绘并隐掉，这里只管节标题。
  // 节标题用黑体；西文单独走 Arial——若让西文走 NCM，bold 会落在衬线粗体上，
  // 挨着黑体像两个年代的字。
  set heading(numbering: none)
  show heading: set text(font: note-font-head, fill: note-colors.ink, weight: "bold")
  show heading.where(level: 2): set text(size: 13pt)
  show heading.where(level: 3): set text(size: 11.5pt)
  // 节标题左缘挂一道竖标（与笔记头的短标同一套语言，颜色跟当前这一篇的主题色），
  // 悬在版心之外，不占正文的宽度。
  // 整条包在 context 里：主题色来自 state，只有排版时才读得到当前值。
  show heading.where(level: 2): it => context block(above: 1.7em, below: 0.6em)[
    #place(
      left + horizon,
      dx: -1.05em,
      rect(width: 3pt, height: 0.95em, fill: note-theme-state.get()),
    )
    #it
  ]
  // 小节标题用同一招，但矮一档、淡一档——不这么标一下，三级标题会整个
  // 混进正文里（10.5pt 宋体正文 vs 11.5pt 黑体标题的差别太小了）。
  show heading.where(level: 3): it => context block(above: 1.45em, below: 0.5em)[
    #place(
      left + horizon,
      dx: -0.95em,
      rect(width: 2pt, height: 0.7em, fill: note-theme-state.get().lighten(50%)),
    )
    #it
  ]

  // ---- 行内样式：中文与西文分别按各自惯例处理 ----
  // 加粗：中文用思源宋体的粗体字重（笔画加粗、字形不变），系统没有该字体时回退黑体。
  // 不要用「换成黑体」冒充加粗——那是换字体，不是加粗，删掉黑体字重后会失效。
  show strong: set text(font: ("New Computer Modern", "Noto Serif SC", "SimHei"))

  // 强调：汉字没有斜体字形，直接套斜体只会得到正体，因此中文改用楷体
  // （中文书籍的强调传统），西文仍用斜体。
  show emph: set text(font: note-font-kai)

  // 下划线：抬高与字身的距离，并在标点、下伸笔画处自动避让
  show underline: set underline(offset: 0.13em, evade: true, stroke: 0.7pt)
  show strike: set strike(offset: 0.22em, stroke: 0.7pt)

  // 代码与公式里的中文：必须显式补中文字体回退，否则这两处的字体是纯西文的，
  // Typst 会在系统字体里随机挑（实测会落到隶书 LiSu）。
  show raw: set text(font: note-font-mono)
  show math.equation: set text(font: note-font-math)

  // ---- 代码块：语法高亮 + 底板 ----
  // Typst 自带 syntect 高亮（语言标记的代码块默认就有颜色），这里换成与
  // 调色板同源的 tmTheme（色值见 code-theme.tmTheme 头部注释）。主题的
  // background 不会被渲染（0.15 实测），底板由下面这条规则单独画。
  set raw(theme: "code-theme.tmTheme")
  // 块级代码铺一层极浅的灰底、圆角，行内代码不铺。breakable: true：
  // 长清单跨页断得开，不会被整块推到下一页留下半页空白。
  show raw.where(block: true): it => block(
    fill: note-colors.tint-gray,
    radius: 3pt,
    inset: (x: 0.8em, y: 0.6em),
    width: 100%,
    breakable: true,
    it,
  )

  // ---- 表格：统一列对齐，禁止单元格两端对齐 ----
  // 列默认左对齐，需要居中的列在各 table 里单独指定。不统一的话，
  // 同一份笔记里的几张表会各用一套对齐规矩。
  set table(align: (left, left, left))
  // 用单元格内边距留气口，不用 column-gutter：Typst 会把 stroke 画进 gutter，
  // 一加就多出竖线，三线表就破了。首列不加左内边距，表左缘仍与正文对齐。
  show table.cell: set table.cell(inset: (x: 0.5em, y: 0.15em))
  show table.cell.where(x: 0): set table.cell(inset: (left: 0pt, right: 0.5em, y: 0.15em))
  // 窄格里两端对齐会把最后一行撑开，逐格关掉。
  show table.cell: set par(justify: false)

  // ---- 三线表 ----
  // 默认表格是一张满格的网（每条行、列都画线），与「安静」的整体调子相反。
  // 这里改成中文技术文档通行的三线表：顶线（表头行上边）、表头下条线
  // （表头行下边），其余一律不画。
  // stroke 传函数时，x/y 是单元格坐标，且只会收到整数——表头行是 y == 0，
  // 而「最后一行」没有对应的标记（"first"/"last" 实测收不到），
  // 所以底线只能靠外面包一层 block 补上，见下面那条 show 规则。
  set table(stroke: (x, y) => (
    top: if y == 0 { 0.9pt + note-colors.ink } else { 0pt },
    bottom: if y == 0 { 0.6pt + note-colors.ink } else { 0pt },
    left: 0pt,
    right: 0pt,
  ))
  // 底线：往表格末尾追加一条 hline（表格内部元素，随表宽收缩）。
  // 不要包 block 补底线——block 会破坏跨页时的表头重复（实测续页直接从
  // 数据行继续）；也不要用 block(width: 100%) 的底线——窄表的底线会比表长。
  show table: it => {
    // 守卫：末尾已挂着底线的表原样放行——show 规则对重建的同类型元素
    // 会再次触发，没有这一条就是无限递归（maximum show rule depth exceeded）
    let kids = it.children
    if kids.len() > 0 and kids.last().func() == table.hline { return it }
    table(
      columns: it.columns,
      rows: it.rows,
      // 不透传的话，单张表显式设的 gutter 会被这条规则静默丢掉。
      // （table 元素没有 gutter 字段，只有分列/分行两个，0.15 实测）
      column-gutter: it.column-gutter,
      row-gutter: it.row-gutter,
      align: it.align,
      inset: it.inset,
      stroke: it.stroke,
      fill: it.fill,
      ..kids,
      table.hline(position: top, stroke: 0.9pt + note-colors.ink),
    )
  }

  // ---- 插图：不需要额外规则 ----
  // Typst 自身就把「自然尺寸超过所在容器」的图夹到容器宽度（正文栏或 #wide
  // 通栏），小于容器的图保持原尺寸、不会被放大——实测 300px 到 6000px 的图
  // 在 裸段落 / figure / box / wide 四种位置都如此，且不溢出。
  //
  // 这里曾经有一条 show image 规则，把过宽的图用 scale() 缩一遍。它是错的：
  // scale 的百分比是相对「已经被容器夹过之后的宽度」算的，而比例却按自然宽度
  // 求，于是缩了两次——实际宽度 = 版心² ÷ 自然宽。越宽的图缩得越狠，
  // 6000px 的图只剩版心的 7%，字小到看不清。显式写了 width 的图不受影响，
  // 所以这个毛病只出现在「随手插图、没写 width」的笔记里。
  // 教训：容器已经做过的约束不要再用 scale 补一遍；要改宽度就写 width。

  // ---- 题注 ----
  // 中文题注惯例是「图 1　标题」，用全角空格，不是西文的连接号。
  show figure: set figure.caption(separator: [　])
  // 表题在上、图题在下（中文技术文档惯例）。表格的 auto 默认虽已是 top
  // （Typst 0.12 起），仍显式写死——不依赖版本默认，也不给外部包留改默认的空间；
  // 图题保持 Typst 默认的 bottom，不走这条规则。
  show figure.where(kind: table): set figure.caption(position: top)
  // 图注文字比正文小一号，与旁注同级
  show figure.caption: set text(size: 9pt, fill: note-colors.ink.lighten(20%))

  // ---- 交叉引用 ----
  // 对「没有编号的标题」写 @标签 会直接编译报错（cannot reference heading
  // without numbering）——笔记的节标题默认不编号，所以只要正文里引用了节标题，
  // 就必须有个说法。这里把标题类引用改成直接印出标题文字：
  // 单篇导出时压根没有目录可查，「见 2.2 节」不如「见 〈那一节的标题〉 节」有用。
  // 想要编号式引用（「见 2.2 节」），在下面加一行 set heading(numbering: "1.1.1")，
  // 这条 show 规则会自动让位——有编号时 it 会照常渲染成编号。
  show ref: it => {
    if it.element != none and it.element.func() == heading {
      link(it.element.location(), it.element.body)
    } else {
      it
    }
  }

  body
}

// ============================================================
// 笔记头
// ------------------------------------------------------------
// 每篇笔记正文的最前面调用一次。它在版面上的样子：
//
//   ────                      ← 主题色短标（每篇一种）
//   ANSYS 拓扑优化             ← 标题（黑体）
//   2026-09-20  #仿真 #ANSYS          ● 待复习
//   ──────────────────────    ← 细分隔线
//   一句话摘要（可选）
//
// 除版面之外它还做三件事：新建一页、埋一枚供汇总册目录使用的隐形标题、
// 把定理环境编号归零。所以**不要**跳过它直接写正文。
//
// 主题色（theme 参数）：每篇笔记一种，默认按篇序从 colors.typ 的 note-themes
// 色板里顺序取（第一篇总是主题红，和以前一样），所以新建一篇笔记拿到的是
// 新颜色。想让某篇固定用某个色就显式传：theme: note-themes.indigo。
// 注意往中间插一篇会让后面各篇的颜色后移一位——这是顺序取色的代价，
// 换来的是一定不撞车。
// ============================================================

#let note-header(
  title: none,
  date: none,
  tags: (),
  status: none,
  source: none,
  summary: none,
  theme: none,
) = {
  // tags 必须是字符串数组：写成字符串时下面 len() 照样返回长度、for 逐字符
  // 渲染，全程不报错，只是标签变成一串单字。
  assert(type(tags) == array, message: "tags 要写成数组：tags: (\"仿真\", \"ANSYS\")")
  assert(
    tags.all(t => type(t) == str),
    message: "tags 的每个元素要是字符串",
  )
  assert(status == none or type(status) == str, message: "status 要写成字符串")
  assert(
    theme == none or type(theme) == color,
    message: "theme 要传颜色，比如 theme: note-themes.indigo；拿到的是 "
      + repr(theme),
  )

  // 每篇笔记从新的一页开始。用 weak 换页：单篇出口时文档刚开始，
  // 这里不会凭空多出一张空白页。
  pagebreak(weak: true)

  // 定下这一篇的主题色，并通知后面所有读 state 的地方。
  // 顺序取色板里的第 note-theme-index 种；显式传了 theme 就用传的。
  // 整段包在 context 里是因为要读 counter（counter.get() 只在 context 里
  // 拿得到），写回 state 的值只由篇序决定，不读别的 state，所以重复应用
  // 结果相同、排版轮次再多也收敛（上面注释里那段踩坑记录）。
  context {
    let i = note-theme-index.get().first()
    let pick = if theme != none {
      theme
    } else {
      note-themes.values().at(calc.rem(i, note-themes.values().len()))
    }
    note-theme-state.update(pick)
  }
  // 篇序前进一位。写在普通代码里：每轮排版只应用一次。
  note-theme-index.step()

  // 供汇总册目录用的隐形一级标题。show heading: none 让它在版面上不出现，
  // 但元素仍在文档树里，outline 与 query 都取得到——书眉判断「本页属于
  // 哪一篇」靠的就是 query 它。书籍样板判断「篇行」用的是同一招。
  {
    show heading: none
    heading(level: 1, outlined: true)[#title]
  }

  // 定理环境在每篇笔记内从 1 重新编号
  reset-thm-counter()

  // ---- 以下是可见版面 ----
  // 笔记头里不该有首行缩进（正文的 2em 会漏进来）
  set par(first-line-indent: 0em, justify: false)

  block(above: 0em, below: 1.6em)[
    // 主题色短标：与书籍样板的篇章页同一个开头。
    // 取色要包在 context 里（见上面 note-theme-state 的说明）
    #context {
      let theme = note-theme-state.get()
      rect(width: 1.6cm, height: 3pt, fill: theme)
    }
    #v(0.85em)
    #text(font: note-font-head, size: 1.6em, weight: "bold", fill: note-colors.ink)[#title]
    #v(0.55em)

    // 元信息行：左端「日期 + 标签」，右端「状态」
    #grid(
      columns: (1fr, auto),
      column-gutter: 0.8em,
      align: (left + horizon, right + horizon),
      {
        if date != none {
          text(font: note-font-head, size: 0.85em, fill: note-colors.muted)[#date]
        }
        if date != none and tags.len() > 0 { h(0.8em) }
        for t in tags {
          // 标签用字符串拼出，不能直接写 #标记——# 在 Typst 里是代码起始符
          box(
            fill: note-colors.tint-gray,
            radius: 2pt,
            inset: (x: 0.5em, y: 0.1em),
          )[#text(font: note-font-head, size: 0.82em, fill: note-colors.gray)[#("#" + t)]]
          h(0.35em)
        }
      },
      {
        if status != none {
          let col = status-colors.at(status, default: note-colors.gray)
          box(baseline: 0.12em)[
            #circle(radius: 0.24em, fill: col)
            #h(0.45em)
            #text(font: note-font-head, size: 0.85em, weight: "bold", fill: col)[#status]
          ]
        }
      },
    )

    // 来源：笔记多半整理自别处，出处和笔记本身一样重要
    #if source != none {
      v(0.4em)
      text(font: note-font-head, size: 0.8em, fill: note-colors.muted)[
        来源　#underline(
          offset: 0.16em,
          stroke: 0.5pt + note-colors.muted.lighten(30%),
          link(source)[#source],
        )
      ]
    }

    #v(0.6em)
    #line(length: 100%, stroke: 0.75pt + note-colors.hairline)

    // 摘要：两三句说清这篇讲什么、为什么记它。可选。
    #if summary != none {
      v(0.7em)
      context {
        let theme = note-theme-state.get()
        block(
          stroke: (left: 2pt + theme),
          inset: (left: 0.8em),
          width: 100%,
        )[#text(size: 0.92em, fill: note-colors.ink.lighten(15%))[#summary]]
      }
    }
  ]
}

// ============================================================
// 旁注（pnote：段级）
// ------------------------------------------------------------
// 用法：把要带旁注的段落交给 #pnote，旁注写在 note 参数里
//
//   #pnote(note: [这里写补充])[
//     正文段落…………
//   ]
//
// 为什么用「段落 + 旁注」而不是在句子里插一枚旁注：
// Typst 的 place 放在段落里时，定位基准是**外层容器**而不是当前这一行。
// 实测 place(left + horizon) 会落在整页版心的垂直中心，同一页上几条旁注
// 全部叠在一处；把内容从块级的 block 换成行内的 box 也一样。所以用 grid
// 把正文与旁注并排，旁注顶边对齐段落顶边——旁注锚在段落上，而不是锚在句子上。
//
// 想要「跟着某一行走」的旁注用下面 #mnote（marginalia 的 state 机制能做到），
// pnote 仍然保留：它不依赖外部包、一条注解概括一整段时反而更稳。
//
// 这个 grid 比版心宽出「间隙 + 旁注栏宽」，向右溢出到页边距里，那正是旁注栏
// 的所在。所以带旁注的段落与不带的段落，正文断行宽度完全一致。
//
// 一条旁注配一个段落：同一段落想要两条旁注，就把段落拆成两段。
// ============================================================

// 网格单元格里的首行缩进要单独补：Typst 不给单元格内的第一个段落加缩进，
// 在单元格里写 set par(first-line-indent: …) 也不生效（两种写法都实测过），
// 只有用 par 函数显式包一层才行。pnote 的正文格靠这个。
// body 只能走 Trailing content block 的形式传——par 的 body 是位置参数，
// 写成 par(body: …) 会被拒，写成 par(…, body) 又会落到 leading 上。
#let note-par(body) = par(first-line-indent: (amount: note-par-indent, all: true))[
  #body
]

// 旁注的外观：左侧一道极浅的主题色竖线 + 小两号的灰字
// 整个函数体包在 context 里：竖线的颜色取自当前这一篇的主题色（state），
// 只有排版时才读得到。竖线 lighten 65% 之后很淡，所以颜色深浅主要看主题色
// 本身——色板里六种都够深，见 colors.typ 的 note-themes。
#let note-style(body, color: note-colors.ink.lighten(22%)) = context block(
  width: note-note-width,
  stroke: (left: 1pt + note-theme-state.get().lighten(65%)),
  inset: (left: 0.55em),
)[
  #set par(first-line-indent: 0em, justify: false, leading: 0.75em)
  #set text(size: note-note-size, fill: color, lang: "zh")
  #body
]

#let pnote(note: none, body) = {
  // 打印稿开关：隐藏旁注时退化成普通段落（正文宽度不变，版式不动）
  if note == none or note-hide-notes {
    body
  } else {
    grid(
      columns: (note-column-width, note-note-width),
      column-gutter: note-gutter,
      row-gutter: 0pt,
      align: (left + top, left + top),
      {
        // 单元格里的段落拿不到外层 set par 的首行缩进（见 note-par 的说明），
        // 用 par 函数包一层补上。
        note-par(body)
      },
      note-style(note),
    )
  }
}

// 两种偏应用：提醒（橙）与技巧（青），省得每次手写颜色
#let pnote-warn(note: none, body) = pnote(
  note: text(fill: note-colors.orange.darken(8%))[#note],
  body,
)
#let pnote-tip(note: none, body) = pnote(
  note: text(fill: note-colors.teal.darken(8%))[#note],
  body,
)

// ============================================================
// 行级旁注（mnote）
// ------------------------------------------------------------
// 在句子中间写 #mnote[旁注]，旁注跟着当前这一行走，多条自动上下避让：
//
//   ……正在读的这句话#mnote[正是这句话让我想起上次的仿真结果]后面继续读……
//
// 与 pnote 的分工：
//   #pnote   一条旁注配一个段落，顶边对齐段落顶边——锚在**段落**上
//   #mnote   一条旁注对准句子里的一个位置——锚在**位置**上，多条不重叠
// 整段的裁剪与补充用 pnote；针对某一句话的即时反应用 mnote。两者可以在
// 同一页混用：mnote 的落点由 marginalia 自己算，不会压到 pnote 那一栏上。
//
// 为什么 place 做不到、它做得到：marginalia 用 state 记录每条旁注已经占了
// 哪一段垂直空间，排版时按 clearance 互相推开；place 写在段落里时定位基准是
// 外层容器而不是当前行（见上面 pnote 的说明），所以只能整段对齐。
// 同一个 state 机制也意味着排版轮次多：极端文档上可能报
//   "document did not converge within five attempts"
// 遇到就把离得最近的一条 mnote 改回 pnote。
//
// 已知边界（都是 marginalia 的限制，不是本模板的）：
//   · 只排右侧。左边距 2.0cm 放不下注解，side 传 left / inner 会被拦下；
//   · 与 #wide 通栏块互不知情：通栏块借走了旁注栏那一列，落点靠近它的
//     mnote 不会让开，可能压到块上。用 dy 手工挪，或那条改用 pnote；
//   · 编号默认关闭（与 pnote 一样安静）。要编号并交叉引用就显式打开：
//       #mnote(counter: marginalia.notecounter)[…]<mn:x> ……见 @mn:x
//     打开后每个旁注带一枚符号锚点（●○◆…），页面上会吵一点。
// ============================================================

#let mnote(
  body,
  fill: none,
  dy: 0pt,
  side: auto,
  ..rest,
) = {
  // 打印稿开关：整条旁注连同锚点一起消失，正文照常流动
  if note-hide-notes { return none }

  assert(
    side == auto or side == "outer" or side == "right",
    message: "mnote 只排右侧旁注栏：side 传了「" + repr(side) + "」，"
      + "而本模板左边距只有 "
      + repr(calc.round(note-margin-left / 1cm * 10) / 10) + "cm，放不下注解",
  )

  // 整调用包在 context 里：block-style 的竖线要取当前这一篇的主题色（state），
  // 只有排版时才读得到。marginalia.note 自己内部也用 context，嵌套没问题。
  context marginalia.note(
    body,
    side: side,
    dy: dy,
    // counter 放前面、rest 放后面：没传时默认 none（不编号），传了以传的为准
    counter: none,
    // 外观与 note-style 对齐：小两号灰字、左侧一道极浅的主题色竖线
    text-style: (
      size: note-note-size,
      fill: if fill == none { note-colors.ink.lighten(22%) } else { fill },
    ),
    par-style: (
      first-line-indent: 0pt,
      justify: false,
      spacing: 0.6em,
      leading: 0.75em,
    ),
    block-style: (
      width: 100%,
      stroke: (left: 1pt + note-theme-state.get().lighten(65%)),
      inset: (left: 0.55em),
    ),
    ..rest,
  )
}

// 与 pnote-warn / pnote-tip 对齐的两种偏应用：提醒（橙）与技巧（青）。
// 用 ..args 整体转交，所以 dy / side / counter 等参数照样能传。
#let mnote-warn(..args) = mnote(
  fill: note-colors.orange.darken(8%),
  ..args,
)
#let mnote-tip(..args) = mnote(
  fill: note-colors.teal.darken(8%),
  ..args,
)

// ============================================================
// 通栏图（wide）
// ------------------------------------------------------------
// 正文栏只有 14.0cm——从书籍样板那边搬来的示意图往往按 16cm 的版心画的，
// 直接放会溢出到页边距里，左边被切掉一截。宽的图、表、代码用 #wide 包一层，
// 让它横跨「正文栏 + 间隙 + 旁注栏」，把这条旁注栏在需要时借给正文用：
//
//   #wide[
//     #figure(sketch(…), caption: […]) <fig:x>
//   ]
//
// 注意标签要写在内容块**里面**、紧跟在 figure 后面——写在 #wide(…) 外面的话，
// 标签会挂到外层那个块上，@fig:x 就指不到图了。
//
// 用法是「块比所在容器宽」，于是向右溢出到旁注栏里（Typst 让超宽块按左对齐
// 溢出）。旁注栏本来就空着，这是这套版式白送的一条宽度。
//
// 块内左对齐是必要的：Typst 的 figure 默认把内容居中，通栏块若不左对齐，
// 一张本来只有 10cm 宽的图会被居中到 18.0cm 的中间——看着缩在右边，
// 与正文左缘对不齐。
// ============================================================

#let note-wide-width = note-column-width + note-gutter + note-note-width

#let wide(body) = block(
  width: note-wide-width,
  above: 0.6em,
  below: 0.6em,
  align(left, body),
)
