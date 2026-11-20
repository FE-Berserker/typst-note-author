// ============================================================
// 几何绘图样式（geostyle）—— Byrne《欧几里得原本》1847 风格
// ------------------------------------------------------------
// SYNC: 本文件与 typst-note-author/template/geostyle.typ 逐字节相同。
// 配色固定为 Byrne 四色，不读 book-colors / note-colors，所以两端没有
// 任何允许的差异；typst-note-author/scripts/check_sync.py 会对它做
// 整体比对。改一边就必须同时改另一边。
// ------------------------------------------------------------
// 什么时候用：图里有"真几何"——点、线、圆、角、弧、多边形，而且这些
//   图元要在正文里被引用（"在 AB 上作…"／"与圆 cA 交于…"）。尺规作图、
//   几何证明、定理配图、构造性示意。
// 什么时候不用：流程图用 flow()，数据图用 chart()，随手涂鸦用 sketch()。
//   geostyle 的代价是"先登记图元再按名绘制"，一次性插图不划算。
// ------------------------------------------------------------
// 四条不变量（缺一条就不是这个风格）：
//   1. 命名图元——先 geo(...) 登记，再按名字绘制，定义与绘制分离。
//   2. 一物一色——颜色标的是"哪个对象"，不是"什么角色"。同一个圆在主图、
//      行内记号、算式里永远同色；两个同为构造物的圆可以一蓝一红。
//   3. 行内重绘——正文里的 ▬ ◯ △ 不是字体字形，是同一批图元缩到 1/3
//      重画（tok-* 系列）。所以圆记号里带着它自己的半径，三角记号带着
//      三条边各自的颜色。
//   4. 图式等式——证明写成一行一步的记号等式，一行一个推理。
// ------------------------------------------------------------
// 用法：
//
//   #import "../geostyle.typ": *
//
//   #let fig = geo(
//     points: ("A": (0, 0), "B": (1, 0), "C": (0.5, 0.8660254)),
//     lines: (
//       "AB": (a: "A", b: "B", color: "ink"),
//       "CA": (a: "C", b: "A", color: "aux"),
//     ),
//     circles: ("cA": (center: "A", through: "B", color: "built")),
//     polys: ("T3": (pts: ("C", "A", "B"), colors: ("aux", "ink", "built"))),
//     angles: ("ACB": (from: "A", at: "C", to: "B", color: "aux", style: "sector")),
//   )
//
//   #canvas 尺寸的单位长度 = 坐标里的 1 个单位
//   #align(center, geo-figure(fig, length: 15mm))
//   #align(center, geo-figure(fig, length: 15mm, els: ("cA", "AB")))   // 只画一部分
//
//   正文里的记号（与主图同源）：
//   #tok-line(fig, "AB", width: 10mm)  #tok-mini(fig, ("cA", "AB"))  #tok-angle(fig, "ACB")
//
//   图式等式（一行一步，居中）：
//   #align(center, par[
//     For #tok-line(fig, "AB") = #tok-line(fig, "CA") (def. 15);
//   ])
// ------------------------------------------------------------
// 线宽只有三档，主图与记号同宽：记号看着粗壮，是 1/3 缩放把 2pt 相对
// 放大三倍的自然结果，不是加粗。想让它细，缩小 length，别改 weight。
// ============================================================

#import "@preview/cetz:0.5.2": canvas, draw

// ---- 语义配色（Byrne 原书四色；固定，不跟主题走）----
#let gp = (
  given: rgb("#d94c1a"), // 已给 / 常用来标先出现的东西
  built: rgb("#265999"), // 构造
  aux:   rgb("#f2b31a"), // 辅助 / 被强调的那个
  ink:   rgb("#111111"), // 中性、底色、结论
)

// ---- 线宽三档（对齐 byrne.mp：2pt / 1pt / 0.5pt）----
#let gw = (reg: 2pt, thin: 1pt, hair: 0.5pt)

// ---- 向量工具 ----
#let _sub(a, b) = (a.at(0) - b.at(0), a.at(1) - b.at(1))
#let _add(a, b) = (a.at(0) + b.at(0), a.at(1) + b.at(1))
#let _mul(a, k) = (a.at(0) * k, a.at(1) * k)
#let _len(a) = calc.sqrt(a.at(0) * a.at(0) + a.at(1) * a.at(1))
#let _unit(a) = if _len(a) == 0 { (0, 0) } else { _mul(a, 1 / _len(a)) }
#let _perp(a) = (-a.at(1), a.at(0))
#let _dot(a, b) = a.at(0) * b.at(0) + a.at(1) * b.at(1)
#let _sum(xs) = { let s = 0; for x in xs { s = s + x }; s }

// ---- 注册表 ----
// points: 名 -> (x, y)，抽象坐标，1 个单位 = geo-figure 的 length
// lines:  名 -> (a:, b:, color:, width:, dash:, extend:, cap:)
// circles:名 -> (center:, through: | radius:, color:, width:)
// angles: 名 -> (from:, at:, to:, color:, style:, radius:, width:)
//          style: sector(实心扇形) | arc(弧) | dash(虚弧) | right(直角 ⌐)
// polys:  名 -> (pts:, colors: 逐边色 | (), close:, fill:, width:)
// marks:  要显示点记号 ∧ 的点名序列（默认关闭——1847 原书没有）
#let geo(
  points: (:), lines: (:), circles: (:), angles: (:), polys: (:), marks: (),
) = (points: points, lines: lines, circles: circles, angles: angles, polys: polys, marks: marks)

#let _p(g, n) = g.points.at(n)
#let _col(g, c) = if c == none { gp.ink } else if type(c) == str { gp.at(c) } else { c }
#let _w(g, w) = if w == none { gw.reg } else if type(w) == str { gw.at(w) } else { w }
#let _stroke(g, e) = (
  paint: _col(g, e.at("color", default: none)),
  thickness: _w(g, e.at("width", default: none)),
  dash: e.at("dash", default: none),
)

// ---- 扇形/弧线：显式折线，取 <=180 的那一侧 ----
#let _sector-pts(g, a, v, b, r, n: 18) = {
  let pv = _p(g, v)
  let u0 = _unit(_sub(_p(g, a), pv))
  let u1 = _unit(_sub(_p(g, b), pv))
  let th = calc.acos(calc.max(-1.0, calc.min(1.0, _dot(u0, u1))))
  if th / 1rad > 3.05 {
    // 平角：走半圆特例
    let nn = _perp(u0)
    return range(19).map(i => {
      let t = calc.pi * i / 18
      _add(pv, _add(_mul(u0, r * calc.cos(t)), _mul(nn, r * calc.sin(t))))
    })
  }
  let s = calc.sin(th)
  range(n + 1).map(i => {
    let t = i / n
    let w0 = if s == 0 { 1 - t } else { calc.sin((1 - t) * th) / s }
    let w1 = if s == 0 { t } else { calc.sin(t * th) / s }
    _add(pv, _mul(_add(_mul(u0, w0), _mul(u1, w1)), r))
  })
}

// ---- 复合折线：逐段异色 + 顶点沿角平分线斜接 ----
// 画出来是一条连续色带，不是几段长方形拼起来——接缝处按角平分线切分，
// 两侧各自上色。
#let _band(pts, colors, w) = {
  let n = pts.len()
  let res = ()
  for i in range(n - 1) {
    let a = pts.at(i); let b = pts.at(i + 1)
    let nn = _mul(_perp(_unit(_sub(b, a))), w / 2)
    res.push((pts: (_add(a, nn), _add(b, nn), _sub(b, nn), _sub(a, nn)), color: colors.at(i)))
  }
  for i in range(1, n - 1) {
    let v = pts.at(i)
    let u0 = _unit(_perp(_unit(_sub(pts.at(i), pts.at(i - 1)))))
    let u1 = _unit(_perp(_unit(_sub(pts.at(i + 1), pts.at(i)))))
    let s = _len(_add(u0, u1))
    if s > 0.05 {
      let m = _mul(_unit(_add(u0, u1)), w / s)
      for sgn in (1, -1) {
        let q0 = _add(v, _mul(u0, w / 2 * sgn))
        let q1 = _add(v, _mul(u1, w / 2 * sgn))
        let mm = _add(v, _mul(m, sgn))
        res.push((pts: (v, q0, mm), color: colors.at(i - 1)))
        res.push((pts: (v, mm, q1), color: colors.at(i)))
      }
    }
  }
  res
}

// ---- 主图 ----
#let geo-figure(
  g,
  length: 8mm,
  els: none,
  labels: false,
  label-size: 5.8pt,
  label-gap: 2.6mm,
  mark-size: 1.3mm,
  label-fill: auto,
  marks: auto,
) = {
  let want(n) = els == none or n in els
  let lf = if label-fill == auto { gp.ink } else { label-fill }
  // 图元重心：标签与点记号沿"远离重心"的方向推到外侧
  let ctr = (
    _sum(g.points.values().map(q => q.at(0))) / g.points.len(),
    _sum(g.points.values().map(q => q.at(1))) / g.points.len(),
  )
  canvas(length: length, {
    import draw: *
    // 被绘制元素引用到的点：决定标签与点记号是否出现
    let used = ()
    for (n, l) in g.lines { if want(n) { used.push(l.a); used.push(l.b) } }
    for (n, c) in g.circles {
      if want(n) {
        used.push(c.center)
        if "through" in c { used.push(c.through) }
      }
    }
    for (n, pl) in g.polys { if want(n) { for q in pl.pts { used.push(q) } } }
    for (n, a) in g.angles { if want(n) { used.push(a.from); used.push(a.at); used.push(a.to) } }
    // 圆
    for (n, c) in g.circles {
      if not want(n) { continue }
      let cc = _p(g, c.center)
      let r = c.at("radius", default: _len(_sub(_p(g, c.through), cc)))
      circle(cc, radius: r, stroke: _stroke(g, c))
    }
    // 线段
    for (n, l) in g.lines {
      if not want(n) { continue }
      let a = _p(g, l.a); let b = _p(g, l.b)
      let ext = l.at("extend", default: 0)
      if ext != 0 {
        let d = _unit(_sub(b, a))
        a = _sub(a, _mul(d, ext)); b = _add(b, _mul(d, ext))
      }
      line(a, b, stroke: _stroke(g, l), cap: l.at("cap", default: "butt"))
    }
    // 多边形：给了 colors 就走复合线斜接，否则普通描边（可填充）
    for (n, pl) in g.polys {
      if not want(n) { continue }
      let ps = pl.pts.map(q => _p(g, q))
      let cs = pl.at("colors", default: ())
      let closed = pl.at("close", default: true)
      if cs == () {
        line(..ps, close: closed, stroke: _stroke(g, pl), fill: pl.at("fill", default: none))
      } else {
        let seq = if closed { ps + (ps.at(0),) } else { ps }
        let cseq = range(seq.len() - 1).map(i => cs.at(calc.rem(i, cs.len())))
        for b in _band(seq, cseq, _w(g, pl.at("width", default: none)) / length) {
          line(..b.pts, close: true, fill: _col(g, b.color), stroke: none)
        }
      }
    }
    // 角：四态
    for (n, a) in g.angles {
      if not want(n) { continue }
      let v = _p(g, a.at)
      let r = a.at("radius", default: 0.9)
      let st = a.at("style", default: "sector")
      let col = _col(g, a.at("color", default: none))
      let w = _w(g, a.at("width", default: none))
      if st == "right" {
        let u0 = _unit(_sub(_p(g, a.from), v)); let u1 = _unit(_sub(_p(g, a.to), v))
        let k = r * 0.8
        let p1 = _add(v, _mul(u0, k))
        let p2 = _add(v, _add(_mul(u0, k), _mul(u1, k)))
        let p3 = _add(v, _mul(u1, k))
        line(p1, p2, p3, stroke: (paint: col, thickness: w))
      } else {
        let pts = _sector-pts(g, a.from, a.at, a.to, r)
        if st == "sector" {
          line(..(v,) + pts, close: true, fill: col, stroke: none)
        } else if st == "arc" {
          line(..pts, stroke: (paint: col, thickness: w))
        } else if st == "dash" {
          line(..pts, stroke: (paint: col, thickness: w, dash: "dashed"))
        }
      }
    }
    // 点记号：由点向外张开的 V（Byrne 的 ↑）；默认关闭
    let mm = if marks == auto { g.marks } else { marks }
    for n in mm {
      if els != none and n not in used { continue }
      let pa = _p(g, n)
      let d = _unit(_sub(pa, ctr))
      let u = if d == (0, 0) { (0, 1) } else { d }
      let pp = _perp(u)
      let k = mark-size / length
      line(_add(pa, _mul(u, k * 0.18)), _add(_add(pa, _mul(u, k)), _mul(pp, k * 0.62)), stroke: (paint: gp.ink, thickness: gw.thin))
      line(_add(pa, _mul(u, k * 0.18)), _add(_add(pa, _mul(u, k)), _mul(pp, -k * 0.62)), stroke: (paint: gp.ink, thickness: gw.thin))
    }
    // 标签：默认关闭（1847 原书一个字母都没有；这是 byrne-latex 依 Tufte
    // 建议加的可选图层）。需要时 labels: true。
    if labels {
      for (n, pa) in g.points {
        if els != none and n not in used { continue }
        let d = _unit(_sub(pa, ctr))
        let u = if d == (0, 0) { (0, 1) } else { d }
        content(_add(pa, _mul(u, label-gap / length)), text(size: label-size, style: "italic", fill: lf, n), anchor: "center")
      }
    }
  })
}

// ================= 行内记号（offspring picture）=================
// 全部用 box(baseline:) 咬住基线，可以直接嵌进句子。
// 注意：tok-mini 传的是"要重画哪些图元"，不是"画什么符号"。
//   #tok-mini(fig, ("cA",))        → 一个空圆环
//   #tok-mini(fig, ("cA", "AB"))   → 圆环 + 它自己的半径  ← 这才是原书的样子

#let tok-line(g, n, width: 4.4mm, rise: 0.30em, dash: auto, color: auto, weight: auto) = {
  let l = g.lines.at(n)
  let c = if color == auto { _col(g, l.at("color", default: none)) } else { _col(g, color) }
  let t = if weight == auto { _w(g, l.at("width", default: none)) } else { _w(g, weight) }
  let d = if dash == auto { l.at("dash", default: none) } else { dash }
  let body = if d == none {
    rect(width: width, height: t, fill: c)
  } else {
    canvas({
      import draw: *
      line((0pt, 0pt), (width, 0pt), stroke: (paint: c, thickness: t, dash: d))
    })
  }
  box(baseline: rise, body)
}

#let tok-mini(g, els, length: 2.2mm, rise: 0.22em, labels: false) = {
  box(baseline: rise, geo-figure(g, length: length, els: els, labels: labels, marks: ()))
}

#let tok-angle(g, n, length: 3.0mm, rise: 0.30em) = tok-mini(g, (n,), length: length, rise: rise)

#let tok-point(rise: 0.30em, size: 1.15mm) = {
  box(baseline: rise, canvas(length: size, {
    import draw: *
    line((0, 0), (0, 0.55), stroke: (paint: gp.ink, thickness: gw.thin))
    line((0, 0.55), (-0.26, 0.92), stroke: (paint: gp.ink, thickness: gw.thin))
    line((0, 0.55), (0.26, 0.92), stroke: (paint: gp.ink, thickness: gw.thin))
  }))
}

#let tok-right(rise: 0.26em, size: 1.5mm) = {
  box(baseline: rise, canvas(length: size, {
    import draw: *
    line((0, 0.9), (0, 0), (0.9, 0), stroke: (paint: gp.ink, thickness: gw.thin))
  }))
}
