// ============================================================
// 全文图形统一样式（figstyle）
// ------------------------------------------------------------
// SYNC: 本文件与 typst-book-author/template/figstyle.typ 内容相同（仅注释
// 措辞不同），改这里要同步改那边，否则两套模板的图形样式会悄悄漂移。
// ------------------------------------------------------------
// 目标：示意图（CeTZ）、流程图（Fletcher）、数据图（Lilaq）共用
//       同一套颜色、字体与线宽，与正文排版保持同一套视觉语言。
//
// 用法：
//   #import "../figstyle.typ": *
//   #figure(flow(...), caption: [流程图]) <fig:flow>
//   #figure(sketch[...cetz 绘图代码...], caption: [示意图])
//   #figure(chart(lq.plot(..., color: series.at(0))), caption: [曲线图])
// ============================================================

#import "@preview/cetz:0.5.2": canvas, draw
#import "@preview/fletcher:0.5.8": diagram, edge, node
#import "@preview/lilaq:0.6.0" as lq
#import "@preview/tiptoe:0.4.0" as tiptoe
#import "colors.typ": note-colors

// ---- 调色板：取自主题红与提示框配色，保证插图与版式同源 ----
// （色值集中在 colors.typ，此处只是别名）
#let palette = note-colors

// 多系列数据的取色顺序：同一篇笔记内按序取用，前后一致
#let series = (palette.primary, palette.blue, palette.green, palette.purple)

// ---- 图内文字：与标题同用黑体，字号比正文小一号 ----
#let fig-font = ("New Computer Modern", "SimHei")
#let fig-size = 9pt

// ============ 1. 示意图 / 几何图（CeTZ）============
// 注意：CeTZ 的画布体必须是代码块（绘制指令是数组），所以用法是
//   #sketch({ rect(..); content(..) }, length: 12mm)
// 而不是方括号的标记内容；图内文字样式在外层作用域设置。
#let sketch(body, length: 8mm) = {
  set text(font: fig-font, size: fig-size, fill: palette.ink)
  canvas(length: length, {
    import draw: *
    set-style(
      stroke: 0.9pt + palette.ink,
      fill: none,
      mark: (end: "stealth", fill: palette.ink, scale: 0.7),
    )
    body
  })
}

// ============ 2. 流程图 / 框图（Fletcher）============
#let flow-style = (
  node-stroke: 0.9pt + palette.ink,
  node-fill: white,
  node-corner-radius: 3pt,
  node-inset: 7pt,
  edge-stroke: 0.8pt + palette.ink,
  edge-corner-radius: 4pt,
  mark-scale: 75%,
  spacing: 2.5em, // 节点间距：太小时箭头标签会挤到节点上
  label-size: 8pt, // 箭头标签比节点文字小一号
  label-sep: 2.5pt,
)

#let flow(..args) = {
  set text(font: fig-font, size: fig-size)
  diagram(..flow-style, ..args)
}

// ============ 3a. 数据图（Lilaq）：边框式坐标轴 ============
// 适合任意取值范围的数据（折线、散点、柱状……）：轴线沿绘图区边框，
// 刻度朝外，默认不加网格；需要网格时传 grid: true 或自定义 stroke。
#let chart(
  width: 7.5cm,
  legend: (position: top + right),
  xlabel: none,
  ylabel: none,
  grid: none,
  ..args,
) = {
  show: lq.set-diagram(xaxis: (label: xlabel), yaxis: (label: ylabel))
  show: lq.set-grid(stroke: if grid == true { 0.4pt + palette.tint-gray } else {
    grid
  })
  show: lq.set-tick(inset: 1.5pt, outset: 1.5pt, pad: 0.4em)
  show: set text(font: fig-font, size: fig-size, fill: palette.ink)
  lq.diagram(..args, legend: legend, width: width)
}

// ============ 3b. 函数图（Lilaq）：过原点的教材式坐标轴 ============
// 适合 $y = f(x)$ 这类经过或接近原点的曲线：轴线在原点相交、轴端带箭头
// （思路取自 Lilaq 内置的 schoolbook 主题）。
// 注意：数据范围远离原点时不要用这套样式——轴线会被推到数据区之外，
// 两轴之间出现大片空白；这类数据请用上面的 chart。
#let fn-plot(
  width: 7.5cm,
  legend: (position: top + right),
  xlabel: none,
  ylabel: none,
  ..args,
) = {
  let axis-args = (position: 0, filter: (v, d) => v != 0 and d >= 5pt)
  show: lq.set-diagram(
    xaxis: axis-args + (label: xlabel),
    yaxis: axis-args + (label: ylabel),
  )
  show: lq.set-grid(stroke: none)
  show: lq.set-tick(inset: 1.5pt, outset: 1.5pt, pad: 0.4em)
  show: lq.set-spine(tip: tiptoe.stealth)
  show: set text(font: fig-font, size: fig-size, fill: palette.ink)
  lq.diagram(..args, legend: legend, width: width)
}
