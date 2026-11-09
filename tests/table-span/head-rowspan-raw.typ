// 回归：不经过 long-table、直接写的 #table(...) 里，表头跨行同样必须编译失败。
//
// 这条测的是 note.typ 里 `show table` 规则的守卫：章节正文里难免有人直接写裸表，
// 守卫必须在那条路径上也生效（long-table 的守卫只管它自己的 head: 参数）。
// 本文件**必须编译失败**。
#import "../../template/note.typ": *

#show: note-setup

== 裸表 + 表头跨行

#table(
  columns: (auto, 1fr, 1fr),
  table.header(
    table.cell(rowspan: 2)[项目],
    [长度 L],
    [直径 D],
  ),
  table.header([mm], [mm]),
  [试件 1], [50.0], [24.8],
)
