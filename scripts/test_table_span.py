#!/usr/bin/env python3
"""表格跨行回归：正文行的跨行要能编译，表头里的跨行要报错。

为什么需要它：Typst 0.15.1 会**静默丢弃** `table.header(...)` 里的
`table.cell(rowspan: n)`——不报错、不警告，只是让该格退回一行，后面那排表头格
整体左移一格，「单位」行就落到错误的列下面（看起来像内容全挤在一起）。模板用
守卫把这种写法变成编译错误，本脚本就是那个守卫的回归测试：

- 守卫被删掉 / 判据写宽了 → `head-rowspan.typ` 编译通过 → 红；
- 判据写窄了、误伤正文行 → `ok.typ` 编译失败 → 红；
- 报错换了别的由头（比如语法错）→ 报错里没有守卫那句话 → 红。

用法：python scripts/test_table_span.py
需要 typst 在 PATH 上，或用 TYPST=/path/to/typst 指定（CI 里已装 0.15.1）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPST = os.environ.get("TYPST") or "typst"
# 守卫报错里的一句话。判「是不是我们的守卫拦下的」，避免把别的语法错当成通过。
GUARD_MARK = "表头里不能跨行"

OK_CASE = ROOT / "tests" / "table-span" / "ok.typ"
BAD_CASE = ROOT / "tests" / "table-span" / "head-rowspan.typ"
# 裸 #table(...) 里的表头跨行由 show table 规则兜住；不是每个仓库都有这条用例
# （书的 show 规则在 main.typ 里，抽不出来单独编译），有就跑，没有就跳过。
BAD_CASE_RAW = ROOT / "tests" / "table-span" / "head-rowspan-raw.typ"


def compile_to(src: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        # 用例在 tests/ 下、模板在 template/ 下，import 要往上跳一级；
        # typst 默认把用例所在目录当项目根，跳级会被拒，所以显式给 --root。
        [TYPST, "compile", "--root", str(ROOT), str(src), str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        # typst 永远按 UTF-8 输出；Windows 上默认用 GBK 解码会在读到中文报错时炸掉。
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    missing = [str(p) for p in (OK_CASE, BAD_CASE) if not p.exists()]
    if missing:
        print("FAIL 缺回归用例：" + "、".join(missing))
        return 1

    try:
        subprocess.run([TYPST, "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        print(f"FAIL 找不到 typst（试过 {TYPST}）；装 0.15.1 或用 TYPST=… 指定")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        result = compile_to(OK_CASE, Path(tmp) / "ok.pdf")
        if result.returncode != 0:
            print("FAIL tests/table-span/ok.typ 应该能编译，但它失败了——守卫误伤了正文行的跨行")
            print(result.stderr.strip())
            return 1

        result = compile_to(BAD_CASE, Path(tmp) / "bad.pdf")
        bad_cases = [BAD_CASE] + ([BAD_CASE_RAW] if BAD_CASE_RAW.exists() else [])
        for i, bad in enumerate(bad_cases):
            result = compile_to(bad, Path(tmp) / f"bad-{i}.pdf")
            name = bad.relative_to(ROOT).as_posix()
            if result.returncode == 0:
                print(f"FAIL {name} 应该编译失败，但它成功了——表头跨行守卫失效")
                return 1
            if GUARD_MARK not in (result.stderr or ""):
                print(f"FAIL {name} 确实失败了，但不是守卫拦下的（报错里没有「表头里不能跨行」）")
                print((result.stderr or "").strip())
                return 1

    print("OK 表头跨行被守卫拦下，正文跨行正常编译")
    return 0


if __name__ == "__main__":
    sys.exit(main())
