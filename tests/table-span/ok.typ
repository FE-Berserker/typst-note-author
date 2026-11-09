// 回归：正文行的跨行 / 跨列是必须能用的写法。
// 这条用例若编译失败，说明守卫误伤了合法表格（判据写成「有 rowspan 就报错」了）。
//
// 对照 head-rowspan.typ（必须编译失败）。
#import "../../template/note.typ": *
#import "../../template/figstyle.typ": *

#show: note-setup

== 表头只用 colspan

#long-table(
  columns: (auto, 1fr, 1fr, auto),
  head: (
    [项目],
    [圆锥长度 L],
    [大端直径 D],
    table.cell(rowspan: 1)[锥角 α],  // rowspan: 1 等于没跨，不该报错
  ),
  caption: [表头只用 colspan，跨行放在正文第一行],
  [单位], [mm], [mm], [°],
  [试件 1], [50.0], [24.8], [2°51′],
)

== 跨行写在正文行

#figure(
  table(
    columns: (auto, 1fr, 1fr),
    table.header([类别], [内容], [值]),
    table.cell(rowspan: 2)[甲类],
    [第一行写长一点，让它折成两行以上，检验行高是否跟着长。],
    [1],
    [第二行同样写长一点，检验跨行格是否覆盖两行。],
    [2],
    [乙类], [普通行], [3],
  ),
  caption: [正文行的跨行正常],
)

== 跨行与跨列混用

#table(
  columns: (1fr, 1fr, 1fr),
  [A], [B], [C],
  [a1], table.cell(colspan: 2)[跨两列],
  table.cell(rowspan: 2)[跨两行], [b2], [c2],
  [b3], [c3],
)
