// ============================================================
// 汇总出口（collection.typ）
// ------------------------------------------------------------
// 全部笔记编成一册：首页是标题 + 总目录（自动生成，页码可点），
// 之后每篇笔记各起一页，续页带书眉、页脚带页码。
//
// 用法：
//   typst compile collection.typ 我的笔记.pdf
//
// 增删笔记只改下面 include 那一段：总目录、页码、书眉都会自己跟上，
// 不需要手工维护目录。这一点与书籍样板不同——那边篇章页的小目录是现算的，
// 但「本页是否空白」这类判断要手工维护；这里只依赖各级标题，增删安全。
// ============================================================

#import "note.typ": *
#import "figstyle.typ": *

#show: note-setup

// ============================================================
// 首页：标题 + 总目录
// ============================================================
#let collection-title(
  title: "我的笔记",
  subtitle: none,
  author: none,
  date: none,
  toc-depth: 1,
) = {
  // 元数据写进 PDF 属性：标题取册名，与首页那一行同一个参数，不会对不上
  set document(title: title)

  // 首页不印书眉页脚
  set page(header: none, footer: none)
  set par(first-line-indent: 0em, justify: false)

  v(1.6em)
  rect(width: 2.4cm, height: 4pt, fill: note-colors.primary)
  v(1.1em)
  text(font: note-font-head, size: 2.5em, weight: "bold", fill: note-colors.ink)[#title]

  if subtitle != none {
    v(0.7em)
    text(font: note-font-head, size: 1.05em, fill: note-colors.muted)[#subtitle]
  }

  v(0.9em)
  line(length: 100%, stroke: 0.75pt + note-colors.hairline)
  v(0.5em)
  grid(
    columns: (1fr, auto),
    align: (left + horizon, right + horizon),
    {
      if author != none {
        text(font: note-font-head, size: 0.85em, fill: note-colors.muted)[#author]
      }
    },
    {
      if date != none {
        text(font: note-font-head, size: 0.85em, fill: note-colors.muted)[#date]
      }
    },
  )

  v(2.4em)
  text(font: note-font-head, size: 1.15em, weight: "bold")[目　录]
  v(0.5em)
  line(length: 100%, stroke: 0.75pt + note-colors.ink)
  v(0.7em)

  // 目录条目不该两端对齐：长条目被撑开后会留下孤零零的末行。
  // depth: 1 只列笔记标题；想连节标题一起列，改成 depth: 2。
  show outline.entry: set par(justify: false, leading: 0.9em)
  // 一级条目（笔记标题）用黑体，与它所指向的标题同一套字；
  // 节标题（depth: 2 时出现）保持正文字体，两级自然分开。
  show outline.entry.where(level: 1): set text(font: note-font-head, weight: "bold")
  outline(title: none, depth: toc-depth)

  v(0.7em)
  line(length: 100%, stroke: 0.75pt + note-colors.hairline)
}

#collection-title(
  title: "我的笔记",
  subtitle: "学习笔记与实操记录",
  author: none, // 想署名就改成 author: [你的名字]
  date: "2026-09-20",
)

// ============================================================
// 笔记正文：按想要的顺序 include，总目录会自动跟上
// ============================================================

#include "notes/note-format.typ"

#include "notes/marginalia.typ"
