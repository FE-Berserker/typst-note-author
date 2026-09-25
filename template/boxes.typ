// ============================================================
// 提示框与编号环境（boxes）
// ------------------------------------------------------------
// 沿用书籍样板的框体外观（细边框、极浅底、左上角挂一枚圆角标题牌），
// 图标用 Heroicons 矢量图标（可缩放、可换色、无需装字体），
// 类型可以按需自由扩充：
//   #keypoint-box[ … ]   #pitfall-box[ … ]   #example-box[ … ]
// 图标名见 https://heroicons.com/ ；要自定义时用：
//   #callout(title: [标题], icon: "rocket-launch", color: rgb("#0ea5e9"))[ … ]
//
// 配色原则：框身一律用同一种极浅中性底，颜色只出现在标题牌和一道细边上。
// 类型靠图标与标题文字区分，一页排六个框也不会变成一页彩虹。
// 三处调用点（callout / thm-env / proof）共用 box-frame()，改一处即全改。
//
// 与书籍样板版的差别：不依赖 Bookly。原版从 bookly 借用两个小工具
// （box-title 与 color-svg），这里 box-title 就地重写成三行，color-svg
// 只服务于「接管 Bookly 内置提示框」那条路径，笔记模板不需要，已删。
// ============================================================

#import "@preview/showybox:2.0.4": showybox
#import "@preview/heroic:0.1.2": hi
#import "colors.typ": note-colors

// 与旁注、笔记头、插图共用一套配色（见 colors.typ）
#let box-colors = note-colors

// ---- 统一框体 ----
#let box-body-fill = rgb("#f7f7f8") // 所有框共用的框身底色

#let box-frame(color) = (
  title-color: color,
  border-color: color.lighten(40%), // 细边比标题牌淡一档，不喧宾夺主
  body-color: box-body-fill,
  thickness: 1pt,
  radius: 3pt,
  // 顶部内边距留出标题牌的高度：标题牌挂在框线上，会向下压住框身
  body-inset: (top: 2em, left: 1em, right: 1em, bottom: 1em),
)

// 标题牌：挂在框线上，只有右下角一个圆角
#let box-tab-style = (
  boxed-style: (
    anchor: (x: left, y: horizon),
    offset: (x: -1em, y: 1.15em),
    radius: (
      top-left: 0pt,
      top-right: 0pt,
      bottom-left: 0pt,
      bottom-right: 5pt,
    ),
  ),
)

// 标题牌内容：图标 + 标题，横向排布。
// （书籍样板里这个函数来自 bookly，此处就地重写，行为一致。）
#let box-title(a, b) = grid(
  columns: 2,
  column-gutter: 0.5em,
  align: (horizon),
  a,
  b,
)

// 通用提示框：统一框体 + 矢量图标
#let callout(
  title: none,
  icon: "information-circle",
  color: box-colors.blue,
  // 短提示框默认整体不跨页：否则撞到页尾时会出现「标题留在上一页、
  // 正文跑到下一页、中间吊着空框」的难看结果。内容确实很长
  // （可能超过一页）时，显式传 breakable: true 允许跨页。
  breakable: false,
  body,
) = showybox(
  title: box-title(hi(icon, height: 1em, color: white), [*#title*]),
  title-style: box-tab-style,
  frame: box-frame(color),
  // align 走 showybox 的 body 命名参数（它会把 align 当块属性取出处理），
  // 框宽 100%，居中在版面上不改变位置；保留是为了与原样板行为一致。
  align: center,
  breakable: breakable,
)[#body]

// ---- 常用类型：中文标题 + 对应图标 ----
// 要点
#let keypoint-box = callout.with(
  title: [要点],
  icon: "light-bulb",
  color: box-colors.orange,
)
// 易错
#let pitfall-box = callout.with(
  title: [易错],
  icon: "bug-ant",
  color: box-colors.purple,
)
// 结论
#let conclusion-box = callout.with(
  title: [结论],
  icon: "flag",
  color: box-colors.teal,
)
// 公式
#let formula-box = callout.with(
  title: [公式],
  icon: "calculator",
  color: box-colors.blue,
)
// 参考
#let reference-box = callout.with(
  title: [参考],
  icon: "link",
  color: box-colors.gray,
)
// 代码（书籍样板里由 Bookly 内置 code-box 本地化而来；这里直接是一个 callout）
// icon 名修正：heroic 0.1.2 无 "code"，正确名为 "code-bracket"（此前无人用
// 到 code-box，潜伏未暴露）
#let code-box = callout.with(
  title: [代码],
  icon: "code-bracket",
  color: box-colors.purple,
  breakable: true,
)

// ============================================================
// 编号环境
// ------------------------------------------------------------
// 定义、定理、引理、推论、命题、例共用一套编号，可用 @标签 交叉引用：
//
//   #theorem[勾股定理：……]<thm:pyth>
//   由定理 @thm:pyth 可得……
//
// 编号在每篇笔记内从 1 重新开始：note.typ 的 note-header 会调用
// reset-thm-counter()。书籍样板里是全书连续编号（书只有一个计数轴），
// 笔记每篇自成一体，接着上一篇往下数反而不好引用。
// ============================================================

#let thm-kind = "theorem-env"

// 编号计数器：与 figure 共用 kind，@ 引用与 numbering 都由 Typst 维护
#let thm-counter = counter(figure.where(kind: thm-kind))

// 把编号归零。由 note-header 在每篇笔记开头调用。
#let reset-thm-counter() = thm-counter.update(0)

#let thm-env(
  body,
  supplement: [定理],
  icon: "academic-cap",
  color: box-colors.red,
  title: none,
  breakable: false,
) = figure(
  kind: thm-kind,
  supplement: supplement,
  caption: none,
  outlined: false,
  numbering: "1",
  showybox(
    title: box-title(
      hi(icon, height: 1em, color: white),
      [*#supplement #context thm-counter.get().first()*#if title != none [　#title]],
    ),
    title-style: box-tab-style,
    frame: box-frame(color),
    align: center,
    breakable: breakable,
  )[#body],
)

#let definition = thm-env.with(
  supplement: [定义],
  icon: "book-open",
  color: box-colors.blue,
)
#let theorem = thm-env.with(
  supplement: [定理],
  icon: "academic-cap",
  color: box-colors.red,
)
#let lemma = thm-env.with(
  supplement: [引理],
  icon: "puzzle-piece",
  color: box-colors.purple,
)
#let corollary = thm-env.with(
  supplement: [推论],
  icon: "arrow-path",
  color: box-colors.teal,
)
#let proposition = thm-env.with(
  supplement: [命题],
  icon: "scale",
  color: box-colors.orange,
)
#let example = thm-env.with(
  supplement: [例],
  icon: "pencil-square",
  color: box-colors.green,
)

// 证明：不编号，结尾自动加 ∎（QED 符号，靠右对齐——正文以行间公式
// 结尾时，不加 h(1fr) 的话 ∎ 会掉到下一行左端）
#let proof(body, title: none) = showybox(
  title: box-title(
    hi("check-badge", height: 1em, color: white),
    [*证明#if title != none [（#title）]*],
  ),
  title-style: box-tab-style,
  frame: box-frame(box-colors.gray),
  align: center,
  breakable: false,
)[#body #h(1fr) #sym.qed]
