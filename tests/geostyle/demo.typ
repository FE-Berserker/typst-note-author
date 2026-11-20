// geostyle.typ 的冒烟测试兼示例：把每个 API 都走一遍。
// 编译通过 = 模块可用；版式异常 = 对照 byrne-study 里的样张。
//   typst compile --root . tests/geostyle/demo.typ tests/geostyle/demo.pdf
//
// 注意 --root .：demo 在 tests/ 下，要 import ../template/ 必须把技能根
// 目录指定为项目根，否则 Typst 报 "would escape the project root"。
#import "../../template/geostyle.typ": *

#set page(width: 160mm, height: 240mm, margin: 10mm)
#set text(size: 9pt)

// ============================================================
// 1. Book I Prop. I —— 两个圆、一个三角形的作图
// ============================================================
#let fig = geo(
  points: ("A": (0, 0), "B": (1, 0), "C": (0.5, 0.8660254)),
  lines: (
    "AB": (a: "A", b: "B", color: "ink"),
    "CA": (a: "C", b: "A", color: "aux"),
    "CB": (a: "C", b: "B", color: "given"),
  ),
  circles: (
    "cA": (center: "A", through: "B", color: "built"),
    "cB": (center: "B", through: "A", color: "given"),
  ),
  // 复合线：三条边各自一色，接缝沿角平分线斜接，仍是一条连续色带
  polys: ("T3": (pts: ("C", "A", "B"), colors: ("aux", "ink", "given"))),
  angles: ("ACB": (from: "A", at: "C", to: "B", color: "aux", style: "sector", radius: 0.3)),
)

#align(center, geo-figure(fig, length: 16mm, els: ("cA", "cB", "T3")))

// ============================================================
// 2. 角的四态：sector / arc / dash / right
// ============================================================
#let vfig(style, color) = geo(
  points: ("V": (0, 0), "A": (1, 0), "B": (0.5, 0.8660254)),
  lines: (
    "VA": (a: "V", b: "A", color: "ink"),
    "VB": (a: "V", b: "B", color: "ink"),
  ),
  angles: ("a": (from: "A", at: "V", to: "B", color: color, style: style, radius: 0.34)),
)

#align(center, grid(
  columns: (30mm,) * 4,
  align: center,
  column-gutter: 2pt,
  ..(
    ("sector", "sector 实心", "aux"),
    ("arc", "arc 弧线", "built"),
    ("dash", "dash 虚弧", "built"),
    ("right", "right 直角", "ink"),
  )
    .map(((st, cap, col)) => [
      #geo-figure(vfig(st, col), length: 11mm) \
      #text(size: 7pt)[#cap]
    ])))

// ============================================================
// 3. 线的三态：实线 / 虚线（作图辅助）/ 射线（extend）
// ============================================================
#let lfig(l) = geo(
  points: ("A": (0, 0), "B": (1, 0)),
  lines: ("AB": (a: "A", b: "B", color: "ink", ..l)),
)

#align(center, grid(
  columns: (45mm,) * 3,
  align: center,
  column-gutter: 2pt,
  ..(
    ((:), "实线", "ink"),
    ((dash: "dashed"), "虚线 = 作图辅助", "aux"),
    ((extend: 0.22), "射线 extend", "ink"),
  )
    .map(((l, cap, col)) => [
      #geo-figure(lfig((..l, color: col)), length: 11mm) \
      #text(size: 7pt)[#cap]
    ])))

// ============================================================
// 4. 行内重绘（offspring picture）：正文里的记号与主图同源
// ============================================================
Describe #tok-mini(fig, ("cA", "AB")) and #tok-mini(fig, ("cB", "AB")) (post. III);
draw #tok-line(fig, "CA") and #tok-line(fig, "CB") (post. I).
Then will #tok-mini(fig, ("T3",), length: 4.6mm) be equilateral.

// 圆记号必须带上它自己的半径 —— 只传 ("cA",) 画出来是个空环，那就退化成字形了。
// 对照：#tok-mini(fig, ("cA",))

// ============================================================
// 5. 图式等式：一行一步
// ============================================================
#align(center, par[
  For #tok-line(fig, "AB", width: 7.5mm) = #tok-line(fig, "CA", width: 7.5mm) (def. 15); \
  and #tok-line(fig, "AB", width: 7.5mm) = #tok-line(fig, "CB", width: 7.5mm) (def. 15); \
  ∴ #tok-line(fig, "CA", width: 7.5mm) = #tok-line(fig, "CB", width: 7.5mm) (ax. 1).
])

// ============================================================
// 6. 可选叠加：点记号 ∧ 与斜体标签（默认关闭，1847 原书一个都没有）
// ============================================================
#align(center, geo-figure(fig, length: 11mm, els: ("cA", "T3"), labels: true, marks: ("A", "B")))
