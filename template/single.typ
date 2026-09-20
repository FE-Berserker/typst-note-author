// ============================================================
// 单篇出口（single.typ）
// ------------------------------------------------------------
// 一篇笔记一个 PDF：没有封面、没有目录、没有页码（只有一页时），
// 打开就是内容。适合「写完就发出去 / 打印出来夹进文件夹」。
//
// 用法：把下面 include 的那一行换成你自己的笔记文件，
//       改笔记头里的标题与日期，然后编译：
//         typst compile single.typ 笔记.pdf
//
// 注意：正文只写 == 与 ===，不要用一级标题——一级标题是留给笔记头的，
// 它由 note-header 生成（版面上隐掉，汇总册的目录里才出现）。
// ============================================================

#import "note.typ": *
#import "figstyle.typ": *

#show: note-setup

// 只改这一行：指向要单独导出的那篇笔记
#include "notes/note-format.typ"

// PDF 元数据：标题取这篇笔记的笔记头标题（第一枚隐形一级标题）。
// set document 放在 context 里，才能 query 到下面 include 进来的标题。
#context {
  let heads = query(selector(heading.where(level: 1)))
  if heads.len() > 0 {
    set document(title: heads.first().body)
  }
}
