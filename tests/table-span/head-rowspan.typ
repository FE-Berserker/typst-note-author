// 回归：表头里的 rowspan 必须编译失败。
//
// Typst 0.15.1 不会为它报错，只会把 rowspan 静默丢掉：该格只占一行，后面那排
// 表头格整体左移一格，「单位」行就落到错误的列下面——看着像内容挤在一起。
// 所以模板用守卫把它变成编译错误。本文件**必须编译失败**；若它编译通过，
// 说明守卫失效，CI 应当变红。
//
// 两种入口都覆盖：long-table 的 head: 参数、裸 table 里的 table.header(…)。
#import "../../template/note.typ": *

#show: note-setup

== long-table 的 head 里跨行

#long-table(
  columns: (auto, 1fr, 1fr),
  head: (
    table.cell(rowspan: 2)[项目],
    [长度 L],
    [直径 D],
  ),
  caption: [应当报错：表头跨行],
  [试件 1], [50.0], [24.8],
)
