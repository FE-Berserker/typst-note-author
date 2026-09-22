// ============================================================
// 全部配色唯一来源（colors）
// ------------------------------------------------------------
// note.typ（笔记头、旁注）、boxes.typ（提示框）、figstyle.typ（插图）
// 共用这一套色值：改这里一处，全文同步。
// 各模块仍保留自己的局部别名（box-colors / palette / note-colors），
// 引用处代码不变。
//
// SYNC: 下方 note-colors-base 的色值与 typst-book-author/template/colors.typ
// 的 book-colors（那边仍叫这个名）相同，改色值要同步改那边，否则两套模板的
// 配色会悄悄漂移；scripts/check_sync.py 可机检。文件末尾的灰阶开关
// （note-monochrome / note-grayscale）是笔记模板独有的，不用往那边搬
// ——书籍样板不出复习稿。
//
// 配色原则（沿用书籍样板的做法）：框身一律用同一种极浅中性底，
// 颜色只出现在标题牌、状态点与细边上——一页上彩色元素一多，正文就被压住了。
// ============================================================

// ---- 黑白打印开关 ----
// 改成 true 重新编译，整套配色换成同亮度的灰阶。彩打的彩色底复印出来
// 会发灰发脏，灰阶能保住明暗层次；亮度按 luma 逐色换算，所以层级关系
// 与彩色版一致（红标仍是深色、提示框仍是浅底，不会糊成一片）。
// note.typ / boxes.typ / figstyle.typ import 的都是下面这个 note-colors，
// 改这一行三个模块一起跟上，不存在漏网的模块。
#let note-monochrome = false

// 逐色换算成同亮度的灰阶。写成带花括号的函数体而不是 lambda 链：Typst 的
// lambda 体到换行就结束，写成 d => d.pairs()\n  .map(…) 时后面几行会被
// 静默丢掉，函数退化成返回「键值对数组」，下游 .blue 取字段时才报
// "cannot access fields on type array"——错得离源头很远。
#let note-grayscale(d) = {
  d.pairs()
    .map(p => (p.at(0), luma(color.luma(p.at(1)))))
    .to-dict()
}

#let note-colors-base = (
  // 主题与正文
  primary: rgb("#c1002a"), // 主题红（笔记头红标、旁注竖线、强调）
  ink: rgb("#222222"), // 线条与文字
  muted: rgb("#8f8f8f"), // 次要线条、参考线、次要文字
  hairline: rgb("#d8d8d8"), // 细分隔线
  // 类型色（提示框、数据系列、切口色标共用）
  blue: rgb("#1d90d0"),
  red: rgb("#c1002a"), // 与 primary 同色
  green: rgb("#00a651"),
  orange: rgb("#e58b00"),
  purple: rgb("#9865ca"),
  teal: rgb("#0d9488"),
  gray: rgb("#6b7280"),
  // 浅底
  tint: rgb("#faf0f2"), // 主题色浅底
  tint-gray: rgb("#f2f2f2"),
  // 备用色（标签、数据系列第 5 条起、以后扩充状态色时取用）
  navy: rgb("#1e3a8a"),
  brown: rgb("#92400e"),
  rose: rgb("#be185d"),
  sky: rgb("#0ea5e9"),
  olive: rgb("#4d7c0f"),
)

// 对外出口：默认彩色，开关打开时是同一套关系的灰阶版
#let note-colors = if note-monochrome { note-grayscale(note-colors-base) } else { note-colors-base }

// ---- 每篇笔记的主题色板 ----
// 主题色不再全局一个：每篇笔记从这里挑一种（note.typ 的 note-header 负责挑，
// 挑过的不再挑）。第一种仍是原来的主题红，所以单篇导出的观感受不到变化。
// 硬条件是「够深」：3pt 的笔记头短标、lighten 65% 的旁注竖线都从它算出来，
// 浅色经这两道工序会淡到看不见。色相上刻意避开提示框的语义色
// （蓝=提示、橙=提醒、青=技巧），免得一篇青色主题的笔记里分不清哪个是框。
#let note-themes-base = (
  crimson: rgb("#c1002a"), // 主题红（默认，与 primary 同色）
  indigo: rgb("#1d4ed8"), // 靛蓝
  pine: rgb("#15803d"), // 松绿
  plum: rgb("#86198f"), // 梅紫
  ochre: rgb("#a35c00"), // 赭黄（比 orange 深，压得住细线）
  slate: rgb("#0f766e"), // 青灰
)

// 黑白开关打开时同样逐色换算成灰。实测六种的亮度：37.4 / 36.0 / 43.6 / 30.8 /
// 42.9 / 41.3（%）。红与靛、赭与青只差一档灰，黑白打印时基本分不出——
// 想靠颜色分辨前后篇，黑白稿做不到，认标题或页码。
#let note-themes = if note-monochrome { note-grayscale(note-themes-base) } else { note-themes-base }
